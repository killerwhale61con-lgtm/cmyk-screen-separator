# SPDX-License-Identifier: GPL-3.0-or-later
"""CMYK Screen Separator: unofficial, offline GIMP-based plate preparation."""
import os, sys, json, math, threading, subprocess, datetime, uuid, traceback, struct
from pathlib import Path
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GdkPixbuf, GLib
from gallery import ImageBrowser
from storage import export_job, write_pending, read_pending, clear_pending

ROOT = Path(__file__).resolve().parent
VERSION = '0.2.0-beta'
DATA_ROOT = Path(os.environ.get('CMYK_APP_DATA_DIR', str(ROOT/'data'))).resolve()
def engine_root():
    choices = [os.environ.get('CMYK_GIMP_ROOT'), ROOT/'runtime', Path(sys.executable).parent.parent]
    for candidate in choices:
        if candidate and (Path(candidate)/'bin'/'gimp-console-3.exe').is_file():
            return Path(candidate).resolve()
    raise RuntimeError('GIMP 3が見つかりません。Start.cmdから起動してください。')
GIMP = engine_root() / 'bin' / 'gimp-console-3.exe'

def round_px(mm, dpi): return int(math.floor(mm / 25.4 * dpi + 0.5))

def plan(sw, sh, mmw, mmh, dpi, ratio, fit):
    if not all(math.isfinite(v) and v > 0 for v in (mmw, mmh, dpi, ratio)):
        raise ValueError('寸法・比率・DPIは正の数で指定してください。')
    if int(dpi) != dpi or dpi > 10000: raise ValueError('DPIは1～10000の整数で指定してください。')
    w, h = round_px(mmw, dpi), round_px(mmh, dpi)
    if min(w,h)<1 or max(w,h)>30000 or w*h>400_000_000:
        raise ValueError('各辺30000 px以内、合計4億画素以内にしてください（メモリ保護）。')
    cw,ch=sw,sh
    if sw/sh > ratio: cw=max(1, min(sw, round(sh*ratio)))
    else: ch=max(1, min(sh, round(sw/ratio)))
    x,y=(sw-cw)//2,(sh-ch)//2
    scale=(min if fit else max)(w/cw,h/ch)
    dw,dh=max(1,round(cw*scale)),max(1,round(ch*scale))
    return dict(w=w,h=h,dpi=int(dpi),crop=[x,y,cw,ch],draw=[(w-dw)//2,(h-dh)//2,dw,dh],
                source=[sw,sh],ratio_crop=cw!=sw or ch!=sh,margin=dw<w or dh<h,output_crop=dw>w or dh>h)

def render(src, p, max_size=None):
    w,h=p['w'],p['h']; factor=1
    if max_size: factor=min(max_size[0]/w,max_size[1]/h,1)
    ow,oh=max(1,round(w*factor)),max(1,round(h*factor))
    dest=GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB,False,8,ow,oh);dest.fill(0xffffffff)
    x,y,cw,ch=p['crop'];image=src.new_subpixbuf(x,y,cw,ch)
    dx,dy,dw,dh=p['draw'];dx=round(dx*factor);dy=round(dy*factor);dw=max(1,round(dw*factor));dh=max(1,round(dh*factor))
    left,top=max(0,dx),max(0,dy);right,bottom=min(ow,dx+dw),min(oh,dy+dh)
    image.composite(dest,left,top,right-left,bottom-top,dx,dy,dw/cw,dh/ch,GdkPixbuf.InterpType.HYPER,255)
    return dest

def jpeg_info(path):
    data=Path(path).read_bytes(); pos=2; info={}
    if data[:2]!=b'\xff\xd8':raise ValueError('JPEG形式ではありません')
    while pos<len(data):
        if data[pos]!=255:raise ValueError('JPEGマーカーが不正です')
        while data[pos]==255:pos+=1
        marker=data[pos];pos+=1
        if marker in (0xd9,0xda):break
        if 0xd0<=marker<=0xd7:continue
        length=int.from_bytes(data[pos:pos+2],'big'); seg=data[pos+2:pos+length];pos+=length
        if marker==0xe0 and seg[:5]==b'JFIF\0':
            unit=seg[7];xx=int.from_bytes(seg[8:10],'big');yy=int.from_bytes(seg[10:12],'big')
            info['dpi']=[xx,yy] if unit==1 else [xx*2.54,yy*2.54] if unit==2 else None
        if marker in (0xc0,0xc1,0xc2):
            info.update(height=int.from_bytes(seg[1:3],'big'),width=int.from_bytes(seg[3:5],'big'),components=seg[5])
        if marker==0xdb:info.setdefault('quantization',[]).append(list(seg))
    return info

def execute_job(src,p,folder,settings,notify):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=False)
    notify('画像の寸法・比率・余白の設定を準備中',1)
    prepared=folder/'prepared.png'
    job=dict(settings,prepared=str(prepared),dpi=p['dpi'],width=p['w'],height=p['h'],geometry=p)
    jobpath=folder/'job.json';jobpath.write_text(json.dumps(job,ensure_ascii=False,indent=2),encoding='utf-8')
    profile=DATA_ROOT/'profile';profile.mkdir(parents=True,exist_ok=True)
    if not (profile/'gimprc').exists():(profile/'gimprc').write_text('(check-updates no)\n',encoding='utf-8')
    env=os.environ.copy();env['GIMP3_DIRECTORY']=str(DATA_ROOT/'profile');env['GEGL_PATH']=str(GIMP.parent.parent/'lib'/'gegl-0.4')
    code='exec(open('+repr(str(ROOT/'worker.py'))+",encoding='utf-8').read());run_job("+repr(str(jobpath))+')'
    notify('GIMPを起動しています',3)
    with (folder/'gimp.log').open('w',encoding='utf-8') as log:
        proc=subprocess.Popen([str(GIMP),'-n','-i','-d','-f','--no-splash','--batch-interpreter=python-fu-eval','-b',code,'--quit'],
                              env=env,cwd=str(ROOT),stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        while proc.poll() is None:
            try:
                status=json.loads((folder/'status.json').read_text(encoding='utf-8'));notify(status['stage'],status['progress'])
            except (OSError,ValueError):pass
            threading.Event().wait(.4)
    if proc.returncode or not (folder/'処理記録.json').exists():
        error=(folder/'error.txt').read_text(encoding='utf-8') if (folder/'error.txt').exists() else (folder/'gimp.log').read_text(encoding='utf-8')[-2500:]
        raise RuntimeError('GIMP処理に失敗しました。\n'+error)
    notify('JPEGのファイル名・寸法・DPI・白黒形式を検査中',98)
    checks={}
    for c in 'CMYK':
        info=jpeg_info(folder/(c+'.JPEG'));checks[c]=info
        if (info.get('width'),info.get('height'),info.get('components'))!=(p['w'],p['h'],1) or info.get('dpi')!=[p['dpi'],p['dpi']]:
            raise RuntimeError(c+'.JPEGの寸法・DPI・グレースケール検査に失敗しました：'+str(info))
    (folder/'JPEG検査.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
    notify('完了：4枚のJPEGを保存しました（寸法・DPI検査済み）',100)
    return folder

class Window(Gtk.Window):
    def __init__(self):
        super().__init__(title=f'CMYK網点4色分解 {VERSION} — GIMP非公式ツール')
        self.set_default_size(1000,820);self.set_border_width(20);self.source=None;self.busy=False;self.last=None;self.running=True
        self.pending=read_pending(DATA_ROOT);self.image_browser=None;self.save_dialog=None
        grid=Gtk.Grid(column_spacing=12,row_spacing=12);self.add(grid);self.grid=grid
        self.input=Gtk.Entry();self.output=Gtk.Entry(text=str(ROOT/'書き出し'))
        self.paper=self.combo(['A4（210 × 297 mm）','A3（297 × 420 mm）','任意サイズ'])
        self.width=Gtk.SpinButton.new_with_range(1,2000,.1);self.width.set_digits(2);self.width.set_value(210)
        self.height=Gtk.SpinButton.new_with_range(1,2000,.1);self.height.set_digits(2);self.height.set_value(297)
        self.ratio=self.combo(['元画像の比率','1:1','3:2','4:3','カスタム'])
        self.rw=Gtk.Entry(text='3');self.rh=Gtk.Entry(text='2');self.rw.set_width_chars(6);self.rh.set_width_chars(6)
        self.mode=self.combo(['全体を収める（白余白）','中央で切り抜く'])
        self.dpi=Gtk.ComboBoxText.new_with_entry()
        for d in ['300','600','1200']:self.dpi.append_text(d)
        self.dpi.set_active(0)
        self.addrow('入力画像（JPEG / PNG）',self.input,0);button=Gtk.Button(label='画像を選ぶ');button.connect('clicked',self.choose_image);grid.attach(button,2,0,1,1)
        self.addrow('JPEG全体の用紙サイズ',self.paper,1);swap=Gtk.Button(label='縦横を入れ替え');swap.connect('clicked',self.swap);grid.attach(swap,2,1,1,1)
        sizes=Gtk.Box(spacing=8)
        for label,control in [('幅 mm',self.width),('高さ mm',self.height)]:sizes.pack_start(Gtk.Label(label=label),False,False,0);sizes.pack_start(control,True,True,0)
        self.addrow('仕上がり寸法',sizes,2)
        self.addrow('画像の仕上げ比率',self.ratio,3)
        ratios=Gtk.Box(spacing=8)
        for item in [self.rw,Gtk.Label(label=':'),self.rh,Gtk.Label(label='比率指定時は元画像を中央で切り抜き')]:ratios.pack_start(item,False,False,0)
        self.addrow('カスタム比率（幅:高さ）',ratios,4)
        self.addrow('用紙との比率の調整',self.mode,5);self.addrow('出力解像度 DPI',self.dpi,6)
        self.addrow('出力先フォルダー',self.output,7);button=Gtk.Button(label='保存先を選ぶ');button.connect('clicked',self.choose_output);grid.attach(button,2,7,1,1)
        self.defer_save=Gtk.CheckButton(label='分解が終わってから保存先を選ぶ')
        self.defer_save.set_active(True);grid.attach(self.defer_save,0,8,3,1)
        self.info=Gtk.Label(xalign=0,yalign=0);self.info.set_line_wrap(True);self.preview=Gtk.Image()
        grid.attach(self.info,0,9,2,1);grid.attach(self.preview,2,9,1,1)
        grid.attach(Gtk.Label(label='共通設定：階調の反転 1回 → 新聞印刷 / 円形 / 周期7 px / 45° / 品質1',xalign=0),0,10,3,1)
        buttons=Gtk.Box(spacing=8)
        self.run=Gtk.Button(label='4色分解して書き出す');self.run.connect('clicked',self.start);buttons.pack_start(self.run,True,True,0)
        self.save=Gtk.Button(label='保存先を選んで保存');self.save.set_sensitive(bool(self.pending));self.save.connect('clicked',self.prompt_save);buttons.pack_start(self.save,True,True,0);grid.attach(buttons,0,11,2,1)
        self.open=Gtk.Button(label='保存先を開く');self.open.set_sensitive(False);self.open.connect('clicked',self.open_folder);grid.attach(self.open,2,11,1,1)
        self.progress=Gtk.ProgressBar(show_text=True);grid.attach(self.progress,0,12,3,1)
        self.status=Gtk.Label(label='画像を選び、出力寸法を確認してください。',xalign=0);self.status.set_line_wrap(True);self.status.set_max_width_chars(100);grid.attach(self.status,0,13,3,1)
        self.backend=Gtk.Label(label='処理エンジン：GIMP 3（既存のインストールを利用） / 元画像は読み取り専用',xalign=0);grid.attach(self.backend,0,14,3,1)
        self.input.connect('activate',self.load);self.input.connect('focus-out-event',self.load)
        self.paper.connect('changed',self.change_paper)
        for control,signal in [(self.width,'value-changed'),(self.height,'value-changed'),(self.ratio,'changed'),(self.mode,'changed'),(self.dpi,'changed'),(self.rw,'changed'),(self.rh,'changed')]:control.connect(signal,self.update)
        self.connect('delete-event',self.close);self.update()
        if self.pending:
            self.run.set_sensitive(False);self.status.set_text('未保存の4版があります。「保存先を選んで保存」から保存できます。')
    def combo(self,items):
        c=Gtk.ComboBoxText()
        for item in items:c.append_text(item)
        c.set_active(0);return c
    def addrow(self,label,widget,row):
        self.grid.attach(Gtk.Label(label=label,xalign=0),0,row,1,1);widget.set_hexpand(True);self.grid.attach(widget,1,row,1,1)
    def choose_image(self,*_):
        folder=Path(self.input.get_text()).parent if self.input.get_text() else Path(GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_PICTURES) or str(Path.home()))
        if not folder.is_dir():folder=Path.home()
        def selected(path):self.input.set_text(path);self.load()
        self.image_browser=ImageBrowser(self,folder,selected);self.image_browser.set_destroy_with_parent(True);self.image_browser.show_all()
    def choose_output(self,*_):
        d=Gtk.FileChooserDialog(title='出力先',transient_for=self,action=Gtk.FileChooserAction.SELECT_FOLDER);d.add_buttons('キャンセル',Gtk.ResponseType.CANCEL,'選択',Gtk.ResponseType.OK)
        def response(dialog,answer):
            if answer==Gtk.ResponseType.OK:self.output.set_text(dialog.get_filename())
            dialog.destroy()
        d.connect('response',response);d.set_modal(True);d.show_all()
    def load(self,*_):
        if self.busy:return
        if not self.input.get_text().strip():return
        try:
            if Path(self.input.get_text()).suffix.lower() not in ('.jpg','.jpeg','.png'):raise ValueError('JPEGまたはPNGを選んでください。')
            self.source=GdkPixbuf.Pixbuf.new_from_file(self.input.get_text()).apply_embedded_orientation();self.update();self.status.set_text('出力寸法と余白・切り抜きを確認して書き出してください。')
        except Exception as e:self.source=None;self.preview.clear();self.info.set_text('入力画像を選び直してください。');self.status.set_text('画像読み込み：'+str(e))
    def change_paper(self,*_):
        i=self.paper.get_active()
        if i<2:self.width.set_value([210,297][i]);self.height.set_value([297,420][i])
        self.update()
    def swap(self,*_):a,b=self.width.get_value(),self.height.get_value();self.width.set_value(b);self.height.set_value(a)
    def getplan(self):
        if not self.source:raise ValueError('入力画像を選んでください。')
        sw,sh=self.source.get_width(),self.source.get_height();i=self.ratio.get_active()
        if i<4:r=[sw/sh,1,1.5,4/3][i]
        else:
            a,b=float(self.rw.get_text()),float(self.rh.get_text())
            if not all(math.isfinite(v) and v>0 for v in (a,b)):raise ValueError('比率の幅と高さは正の数で指定してください。')
            r=a/b
        return plan(sw,sh,self.width.get_value(),self.height.get_value(),float(self.dpi.get_active_text()),r,self.mode.get_active()==0)
    def update(self,*_):
        if self.busy:return
        try:
            p=self.getplan();self.info.set_text(f"出力：{p['w']:,} × {p['h']:,} px / {p['dpi']} DPI\nJPEG全体：{self.width.get_value():g} × {self.height.get_value():g} mm\n元画像の比率切り抜き：{'あり（中央）' if p['ratio_crop'] else 'なし'}\n用紙との調整：{'白余白あり' if p['margin'] else '中央切り抜きあり' if p['output_crop'] else '余白・切り抜きなし'}\n白い部分を含む枠全体がJPEGになります。")
            self.preview.set_from_pixbuf(render(self.source,p,(260,160)))
        except Exception as e:self.info.set_text(str(e))
    def notify(self,text,value):
        def apply():self.status.set_text(text);self.progress.set_fraction(value/100);self.progress.set_text(f'{value}%');return False
        GLib.idle_add(apply)
    def start(self,*_):
        if self.busy or self.pending:return
        try:
            self.load()
            p=self.getplan()
            defer=self.defer_save.get_active()
            if not defer and not self.output.get_text().strip():raise ValueError('出力先フォルダーを選んでください。')
            output=self.output.get_text()
            folder=DATA_ROOT/'jobs'/uuid.uuid4().hex
            settings=dict(input=str(Path(self.input.get_text()).resolve()),width_mm=self.width.get_value(),height_mm=self.height.get_value(),ratio=self.ratio.get_active_text(),mode=self.mode.get_active_text())
            self.set_busy(True)
            def work():
                try:
                    execute_job(self.source,p,folder,settings,lambda text,value:self.notify('分解：'+text,min(90,round(value*.9))))
                    write_pending(DATA_ROOT,folder)
                    GLib.idle_add(self.separated,folder,defer,output)
                except Exception as e:
                    folder.mkdir(parents=True,exist_ok=True);(folder/'app-error.txt').write_text(traceback.format_exc(),encoding='utf-8');self.notify('失敗：'+str(e)[:600]+'（作業ログ：'+str(folder)+'）',0)
                    GLib.idle_add(self.set_busy,False)
            threading.Thread(target=work,daemon=True).start()
        except Exception as e:self.notify('入力エラー：'+str(e),0)
    def set_busy(self,value):
        self.busy=value
        for widget in self.grid.get_children():
            if self.grid.child_get_property(widget,'top-attach')<9:widget.set_sensitive(not value)
        self.run.set_sensitive(not value and not bool(self.pending))
        self.save.set_sensitive(not value and bool(self.pending))
        self.open.set_sensitive(not value and bool(self.last))
        return False
    def separated(self,folder,defer,output):
        self.pending=Path(folder);self.set_busy(False)
        self.status.set_text('4色分解が完了しました。保存先を選んでください。')
        if defer:self.prompt_save()
        else:self.save_to(output)
        return False
    def prompt_save(self,*_):
        if self.busy or not self.pending:return
        if self.save_dialog:self.save_dialog.present();return
        d=Gtk.FileChooserDialog(title='分解済みの4枚を保存するフォルダー',transient_for=self,action=Gtk.FileChooserAction.SELECT_FOLDER)
        d.add_buttons('後で保存',Gtk.ResponseType.CANCEL,'ここに4枚を保存',Gtk.ResponseType.OK)
        d.set_create_folders(True)
        if Path(self.output.get_text()).is_dir():d.set_current_folder(self.output.get_text())
        self.save_dialog=d
        def response(dialog,answer):
            folder=dialog.get_filename();self.save_dialog=None;dialog.destroy()
            if answer==Gtk.ResponseType.OK:self.output.set_text(folder);self.save_to(folder)
            else:self.status.set_text('保存を保留しました。分解済みの4枚は保持しています。「保存先を選んで保存」で再開できます。')
        d.connect('response',response);d.set_modal(True);d.show_all()
    def save_to(self,destination):
        if self.busy or not self.pending:return
        if not str(destination).strip():self.status.set_text('保存先フォルダーを選んでください。');return
        pending=self.pending
        self.set_busy(True);self.notify('分解済みの4枚を保存しています…',95)
        def work():
            try:
                job=json.loads((pending/'job.json').read_text(encoding='utf-8-sig'))
                target=export_job(pending, destination, Path(job['input']).stem)
                # Data has reached a new destination; only this app's temporary job is removed.
                try:clear_pending(DATA_ROOT,pending)
                except OSError:pass
                GLib.idle_add(self.saved,target)
            except Exception as e:
                self.notify('保存に失敗しました：'+str(e)+'。分解済みの4枚は保持しています。',90)
                GLib.idle_add(self.set_busy,False)
        threading.Thread(target=work,daemon=True).start()
    def saved(self,target):
        self.last=Path(target);self.pending=None;self.set_busy(False)
        self.output.set_text(str(self.last.parent));self.progress.set_fraction(1);self.progress.set_text('100%')
        self.status.set_text('保存完了：'+str(self.last))
        return False
    def open_folder(self,*_):
        try:
            subprocess.Popen([os.path.join(os.environ.get('WINDIR','C:/Windows'),'explorer.exe'),str(self.last)],creationflags=subprocess.CREATE_NO_WINDOW)
        except Exception as e:self.status.set_text('保存先を開けませんでした：'+str(self.last)+' / '+str(e))
    def close(self,*_):
        if self.busy:self.status.set_text('処理が完了するまでお待ちください。');return True
        self.running=False;return False

def run_loop(window):
    # GTK's Python SIGINT helper opens a loopback socket on Windows.
    # Dispatch the native GLib context directly: this offline app needs no sockets.
    context=GLib.MainContext.default()
    while window.running:context.iteration(True)

if __name__=='__main__':
    try:
        window=Window()
        if len(sys.argv)>1:window.input.set_text(str(Path(sys.argv[1]).resolve()));window.load()
        window.show_all();run_loop(window)
    except Exception:
        (ROOT/'起動エラー.txt').write_text(traceback.format_exc(),encoding='utf-8');raise

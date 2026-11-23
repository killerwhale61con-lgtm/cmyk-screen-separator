# SPDX-License-Identifier: GPL-3.0-or-later
"""Executed only inside GIMP's official python-fu-eval batch interpreter."""
import json, os, traceback, hashlib
from gi.repository import Gimp, Gio, Gegl

def run_job(job_path):
    with open(job_path, encoding='utf-8-sig') as f:
        job = json.load(f)
    folder = os.path.dirname(job_path)
    status_path = os.path.join(folder, 'status.json')
    stage = '起動'
    def status(message, progress, error=False):
        nonlocal stage
        stage = message
        tmp = status_path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(dict(stage=message, progress=progress, error=error), f, ensure_ascii=False)
        os.replace(tmp, status_path)
    def call(name, **kwargs):
        proc = Gimp.get_pdb().lookup_procedure(name)
        if proc is None:
            raise RuntimeError('APIがありません: ' + name)
        cfg = proc.create_config()
        for key, value in kwargs.items():
            if key == 'drawables':
                cfg.set_core_object_array('drawables', value)
            else:
                cfg.set_property(key.replace('_', '-'), value)
        result = proc.run(cfg)
        if result.index(0) != Gimp.PDBStatusType.SUCCESS:
            raise RuntimeError(name + ': ' + str([result.index(i) for i in range(result.length())]))
        return result
    try:
        Gegl.init(None)
        status('入力画像を読み込み（元画像は保存しません）', 5)
        image = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, Gio.File.new_for_path(job.get('input',job['prepared'])))
        if image is None:
            raise RuntimeError('入力画像を読み込めませんでした。')
        if 'geometry' in job:
            status('GIMPで比率・寸法・白余白を適用', 8)
            g=job['geometry']
            if [image.get_width(),image.get_height()] != g['source']:
                raise RuntimeError('入力画像の向きがプレビューと一致しません。画像の向きをGIMPで確定して別名保存してください。')
            Gimp.context_push()
            try:
                Gimp.context_set_background(Gegl.Color.new('white'))
                Gimp.context_set_interpolation(Gimp.InterpolationType.NOHALO)
                if image.get_base_type() != Gimp.ImageBaseType.RGB:
                    image.convert_rgb()
                image.flatten()
                x,y,cw,ch=g['crop']; dx,dy,dw,dh=g['draw']
                if (cw,ch)!=(image.get_width(),image.get_height()): image.crop(cw,ch,x,y)
                if (dw,dh)!=(image.get_width(),image.get_height()): image.scale(dw,dh)
                if (g['w'],g['h'])!=(image.get_width(),image.get_height()) or dx or dy:
                    image.resize(g['w'],g['h'],dx,dy)
                image.flatten()
            finally:
                Gimp.context_pop()
        image.set_resolution(job['dpi'], job['dpi'])
        status('CMYKチャンネル分解', 15)
        result = call('plug-in-decompose', run_mode=Gimp.RunMode.NONINTERACTIVE,
                      image=image, drawables=[image.get_layers()[0]],
                      decompose_type='cmyk', layers_mode=True, use_registration=False)
        separated = result.index(1)
        layers = separated.get_layers()
        if len(layers) != 4:
            raise RuntimeError('CMYK分解レイヤー数が4ではありません')
        report = dict(gimp_version=Gimp.version(), channels=[], job=job,
                      newsprint=dict(color_model='black-on-white', pattern='circle', period=7.0, angle=45.0, aa_samples=1),
                      invert='gimp-drawable-invert linear=False (once)')
        for index, (channel, layer) in enumerate(zip('CMYK', layers)):
            status(channel + '：階調の反転', 20 + index * 19)
            source_name = layer.get_name()
            call('gimp-drawable-invert', drawable=layer, linear=False)
            status(channel + '：新聞印刷（円形・7・45°・品質1）', 24 + index * 19)
            filt = Gimp.DrawableFilter.new(layer, 'gegl:newsprint', '新聞印刷')
            cfg = filt.get_config()
            cfg.set_property('color-model', 'black-on-white')
            cfg.set_property('pattern', 'circle')
            cfg.set_property('period', 7.0)
            cfg.set_property('angle', 45.0)
            cfg.set_property('aa-samples', 1)
            cfg.set_property('turbulence', 0.0)
            cfg.set_property('blocksize', -1.0)
            cfg.set_property('angleboost', 0.0)
            for key, expected in [('color-model','black-on-white'),('pattern','circle'),('period',7.0),('angle',45.0),('aa-samples',1)]:
                if cfg.get_property(key) != expected: raise RuntimeError('新聞印刷パラメーター検証失敗：'+key)
            filt.update()
            layer.merge_filter(filt)
            # A fresh single-layer image prevents visibility/compositing accidents.
            single = Gimp.Image.new(separated.get_width(), separated.get_height(), Gimp.ImageBaseType.GRAY)
            single.set_resolution(job['dpi'], job['dpi'])
            copy = Gimp.Layer.new_from_drawable(layer, single)
            single.insert_layer(copy, None, 0)
            copy.set_visible(True)
            if copy.has_alpha(): copy.remove_alpha()
            dest = os.path.join(folder, channel + '.JPEG')
            if os.path.exists(dest): raise FileExistsError(dest)
            status(channel + '：JPEG最高品質で保存', 30 + index * 19)
            call('file-jpeg-export', run_mode=Gimp.RunMode.NONINTERACTIVE, image=single,
                 file=Gio.File.new_for_path(dest), quality=1.0, smoothing=0.0,
                 optimize=True, progressive=False, cmyk=False, sub_sampling='sub-sampling-1x1',
                 include_exif=False, include_iptc=False, include_xmp=False,
                 include_color_profile=False, include_thumbnail=False, include_comment=False)
            report['channels'].append(dict(file=channel+'.JPEG', layer_name=source_name,
                width=single.get_width(), height=single.get_height(), dpi=job['dpi'],
                sha256=hashlib.sha256(open(dest,'rb').read()).hexdigest()))
            single.delete()
        with open(os.path.join(folder, '処理記録.json'), 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        separated.delete()
        image.delete()
        status('完了：C.JPEG / M.JPEG / Y.JPEG / K.JPEG', 100)
    except Exception:
        with open(os.path.join(folder,'error.txt'),'w',encoding='utf-8') as f: f.write(traceback.format_exc())
        status('失敗した工程：' + stage + '\n' + traceback.format_exc(), 0, True)
        raise

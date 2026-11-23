# SPDX-License-Identifier: GPL-3.0-or-later
import os, sys, time, json, shutil, hashlib, tempfile
from pathlib import Path
app_root=Path(__file__).resolve().parents[1]
scratch=Path(tempfile.mkdtemp(prefix='cmyk-smoke-')).resolve()
scratch.mkdir(parents=True,exist_ok=True)
data=scratch/('data-'+str(time.time_ns()))
os.environ['CMYK_APP_DATA_DIR']=str(data)
sys.path.insert(0,str(app_root))
import app, storage
from gi.repository import Gtk, GLib, GdkPixbuf
profile=data/'profile';profile.mkdir(parents=True)
for name in ('pluginrc','gimprc'):
 if (app_root/'profile'/name).is_file():shutil.copy2(app_root/'profile'/name,profile/name)
photos=data/'photos';photos.mkdir()
for name,color,kind in [('blue.png',0x2255ffff,'png'),('orange.JPEG',0xff8833ff,'jpeg')]:
 pix=GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB,False,8,600,400);pix.fill(color);pix.savev(str(photos/name),kind,[],[])
(photos/'broken.png').write_bytes(b'not an image')
original_hash={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in photos.iterdir()}
context=GLib.MainContext.default()
def wait(predicate,timeout=120):
 deadline=time.monotonic()+timeout
 while not predicate():
  while context.pending():context.iteration(False)
  if time.monotonic()>deadline:raise TimeoutError('GUI test timed out')
  time.sleep(.02)
 while context.pending():context.iteration(False)
w=app.Window();w.show_all()
w.input.set_text(str(photos/'blue.png'));w.load();w.choose_image()
browser=w.image_browser
wait(lambda:browser.loaded_count==3)
assert browser.photo_count==3
rows={row[1]:i for i,row in enumerate(browser.model)}
assert browser.model[rows['blue.png']][0].get_pixels()!=browser.model[rows['orange.JPEG']][0].get_pixels()
browser.icons.select_path(Gtk.TreePath.new_from_indices([rows['broken.png']]))
wait(lambda:'読み込めません' in browser.description.get_text())
assert not browser.accept_button.get_sensitive()
browser.icons.unselect_all();browser.icons.select_path(Gtk.TreePath.new_from_indices([rows['blue.png']]))
wait(lambda:browser.selected_path is not None)
assert browser.preview.get_pixbuf() is not None and browser.accept_button.get_sensitive()
browser.accept();assert Path(w.input.get_text()).resolve()==(photos/'blue.png').resolve()
assert browser.closed
print('PASS thumbnail gallery, large preview, broken image handling, photo selection',flush=True)
w.paper.set_active(2);w.width.set_value(25.4);w.height.set_value(25.4);w.dpi.get_child().set_text('300')
w.output.set_text(str(data/'must-not-save-yet'))
assert w.defer_save.get_active()
w.start();wait(lambda:not w.busy and w.pending is not None)
assert not (data/'must-not-save-yet').exists()
assert w.save_dialog is not None and all((w.pending/(c+'.JPEG')).exists() for c in 'CMYK')
pending=w.pending
plate_hash={c:hashlib.sha256((pending/(c+'.JPEG')).read_bytes()).hexdigest() for c in 'CMYK'}
w.save_dialog.response(Gtk.ResponseType.CANCEL)
assert w.pending==pending and w.save.get_sensitive() and not w.run.get_sensitive()
w.destroy();w=app.Window();w.show_all()
assert w.pending==pending
print('PASS choose destination after separation, cancel without data loss, recover pending job',flush=True)
blocked=data/'not-a-directory';blocked.write_text('keep',encoding='utf-8')
w.save_to(blocked);wait(lambda:not w.busy)
assert w.pending==pending and blocked.read_text(encoding='utf-8')=='keep'
destination=data/'user-selected-output';destination.mkdir();(destination/'C.JPEG').write_bytes(b'keep-existing')
w.save_to(destination);wait(lambda:not w.busy and w.pending is None)
assert w.last.parent==destination and (destination/'C.JPEG').read_bytes()==b'keep-existing'
for c in 'CMYK':
 path=w.last/(c+'.JPEG');info=app.jpeg_info(path)
 assert (info['width'],info['height'],info['dpi'],info['components'])==(300,300,[300,300],1)
 assert hashlib.sha256(path.read_bytes()).hexdigest()==plate_hash[c]
assert not pending.exists()
duplicate=storage.export_job(w.last,destination,'blue')
assert duplicate!=w.last and all((duplicate/(c+'.JPEG')).exists() for c in 'CMYK')
print('PASS failed save recovery, selected destination, no overwrite, unchanged plate bytes',flush=True)
w.input.set_text(str(photos/'orange.JPEG'));w.load();w.dpi.get_child().set_text('150');w.defer_save.set_active(False);w.output.set_text(str(destination))
w.start();wait(lambda:not w.busy and w.pending is None and w.last is not None and 'orange' in w.last.name)
assert w.save_dialog is None
assert app.jpeg_info(w.last/'K.JPEG')['dpi']==[150,150]
assert original_hash=={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in photos.iterdir()}
w.destroy()
report=dict(version=app.VERSION,thumbnail_gallery=True,large_preview=True,invalid_image_rejected=True,
 post_separation_destination=True,cancel_keeps_plates=True,pending_job_recovery=True,
 failed_save_can_retry=True,no_overwrite=True,export_does_not_modify_plates=True,
 png_input=True,jpeg_input=True,dimensions_300=[300,300],custom_dpi=150,source_unchanged=True,
 manual_gimp_four_plate_comparison='not completed in previous version; not claimed')
print(json.dumps(report,ensure_ascii=False,indent=2))
print('PASS all v0.2 tests',flush=True)



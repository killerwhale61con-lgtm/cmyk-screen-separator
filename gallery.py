# SPDX-License-Identifier: GPL-3.0-or-later
"""Offline thumbnail picker. Photos and thumbnail caches are never uploaded."""
import queue
import threading
from pathlib import Path
from gi.repository import Gtk, GdkPixbuf, GLib

IMAGE_SUFFIXES = {'.jpg', '.jpeg', '.png'}

def thumbnail(path, width=160, height=120):
    image = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(path), width, height, True)
    image = image.apply_embedded_orientation()
    scale = min(width / image.get_width(), height / image.get_height(), 1)
    if scale < 1:
        image = image.scale_simple(max(1, round(image.get_width()*scale)),
                                  max(1, round(image.get_height()*scale)), GdkPixbuf.InterpType.BILINEAR)
    return image

class ImageBrowser(Gtk.Window):
    def __init__(self, parent, folder, on_select):
        super().__init__(title='写真を選ぶ — サムネイル一覧')
        self.set_transient_for(parent)
        self.set_modal(True)
        self.set_default_size(1080, 680)
        self.set_border_width(14)
        self.on_select = on_select
        self.generation = 0
        self.preview_generation = 0
        self.closed = False
        self.selected_path = None
        self.loaded_count = 0
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add(outer)
        bar = Gtk.Box(spacing=8)
        outer.pack_start(bar, False, False, 0)
        up = Gtk.Button(label='上のフォルダー')
        up.connect('clicked', lambda *_: self.load_folder(self.folder.parent))
        bar.pack_start(up, False, False, 0)
        self.path = Gtk.Entry()
        self.path.connect('activate', lambda entry: self.load_folder(Path(entry.get_text())))
        bar.pack_start(self.path, True, True, 0)
        browse = Gtk.Button(label='フォルダーを選ぶ')
        browse.connect('clicked', self.choose_folder)
        bar.pack_start(browse, False, False, 0)
        body = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        body.set_position(710)
        outer.pack_start(body, True, True, 0)
        self.model = Gtk.ListStore(GdkPixbuf.Pixbuf, str, str, bool)
        self.icons = Gtk.IconView.new_with_model(self.model)
        self.icons.set_pixbuf_column(0)
        self.icons.set_text_column(1)
        self.icons.set_tooltip_column(2)
        self.icons.set_item_width(180)
        self.icons.set_margin(8)
        self.icons.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.icons.connect('selection-changed', self.selection_changed)
        self.icons.connect('item-activated', self.activated)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.add(self.icons)
        body.pack1(scroll, True, False)
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        right.set_border_width(12)
        self.preview = Gtk.Image()
        self.preview.set_size_request(280, 350)
        self.description = Gtk.Label(label='写真をクリックすると大きく表示します。', xalign=0)
        self.description.set_line_wrap(True)
        self.description.set_max_width_chars(34)
        right.pack_start(self.preview, True, True, 0)
        right.pack_start(self.description, False, False, 0)
        body.pack2(right, False, False)
        bottom = Gtk.Box(spacing=10)
        self.status = Gtk.Label(xalign=0)
        bottom.pack_start(self.status, True, True, 0)
        cancel = Gtk.Button(label='キャンセル')
        cancel.connect('clicked', lambda *_: self.destroy())
        bottom.pack_start(cancel, False, False, 0)
        self.accept_button = Gtk.Button(label='この写真を使う')
        self.accept_button.set_sensitive(False)
        self.accept_button.connect('clicked', self.accept)
        bottom.pack_start(self.accept_button, False, False, 0)
        outer.pack_start(bottom, False, False, 0)
        self.connect('destroy', self.on_destroy)
        self.load_folder(folder)

    def on_destroy(self, *_):
        self.closed = True
        self.generation += 1
        self.preview_generation += 1

    def choose_folder(self, *_):
        dialog = Gtk.FileChooserDialog(title='写真のフォルダー', transient_for=self,
                                       action=Gtk.FileChooserAction.SELECT_FOLDER)
        dialog.add_buttons('キャンセル', Gtk.ResponseType.CANCEL, 'このフォルダーを表示', Gtk.ResponseType.OK)
        dialog.set_current_folder(str(self.folder))
        def response(d, answer):
            if answer == Gtk.ResponseType.OK:
                self.load_folder(Path(d.get_filename()))
            d.destroy()
        dialog.connect('response', response)
        dialog.set_modal(True)
        dialog.show_all()

    def load_folder(self, folder):
        try:
            folder = Path(folder).expanduser().resolve()
            entries = sorted(folder.iterdir(), key=lambda p: (p.is_dir(), p.name.casefold()))
        except OSError as error:
            self.status.set_text('フォルダーを開けません：' + str(error))
            return
        self.generation += 1
        generation = self.generation
        self.folder = folder
        self.path.set_text(str(folder))
        self.model.clear()
        self.preview.clear()
        self.selected_path = None
        self.accept_button.set_sensitive(False)
        self.loaded_count = 0
        self.status.set_text('サムネイルを読み込んでいます…')
        theme = Gtk.IconTheme.get_default()
        try:
            folder_icon = theme.load_icon('folder', 96, 0)
        except GLib.Error:
            folder_icon = None
        blank = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, 160, 120)
        blank.fill(0xe5e5e5ff)
        tasks = queue.Queue()
        count = 0
        for item in entries:
            if item.is_dir():
                self.model.append([folder_icon, item.name, str(item), True])
            elif item.suffix.lower() in IMAGE_SUFFIXES:
                row = self.model.append([blank, item.name, str(item), False])
                reference = Gtk.TreeRowReference.new(self.model, self.model.get_path(row))
                tasks.put((item, reference))
                count += 1
        self.photo_count = count
        if not count:
            self.status.set_text('このフォルダーにJPEG・PNG画像はありません。')
        def deliver(reference, pixbuf):
            if self.closed or generation != self.generation:
                return False
            if reference.valid() and pixbuf is not None:
                self.model[reference.get_path()][0] = pixbuf
            self.loaded_count += 1
            self.status.set_text(f'写真 {count} 枚 / 読み込み {self.loaded_count} 枚')
            return False
        def work():
            while not self.closed and generation == self.generation:
                try:
                    path, reference = tasks.get_nowait()
                except queue.Empty:
                    return
                try:
                    pixbuf = thumbnail(path)
                except (GLib.Error, OSError):
                    pixbuf = None
                GLib.idle_add(deliver, reference, pixbuf)
        for _ in range(2):
            threading.Thread(target=work, daemon=True).start()

    def selection_changed(self, *_):
        selected = self.icons.get_selected_items()
        self.preview_generation += 1
        generation = self.preview_generation
        self.selected_path = None
        self.accept_button.set_sensitive(False)
        if not selected:
            return
        row = self.model[selected[0]]
        path = Path(row[2])
        self.preview.clear()
        self.description.set_text(path.name)
        if row[3]:
            self.description.set_text(path.name + '\nダブルクリックでフォルダーを開きます。')
            return
        def work():
            try:
                pixbuf = thumbnail(path, 360, 420)
                info = GdkPixbuf.Pixbuf.get_file_info(str(path))
                message = f'{path.name}\n{info.width:,} × {info.height:,} px'
            except (GLib.Error, OSError) as error:
                pixbuf, message = None, '画像を読み込めません：' + str(error)
            def deliver():
                if self.closed or generation != self.preview_generation:
                    return False
                self.description.set_text(message)
                if pixbuf is not None:
                    self.preview.set_from_pixbuf(pixbuf)
                    self.selected_path = path
                    self.accept_button.set_sensitive(True)
                return False
            GLib.idle_add(deliver)
        threading.Thread(target=work, daemon=True).start()

    def activated(self, _icons, tree_path):
        row = self.model[tree_path]
        if row[3]:
            self.load_folder(Path(row[2]))
        elif self.selected_path == Path(row[2]):
            self.accept()

    def accept(self, *_):
        if self.selected_path is not None:
            self.on_select(str(self.selected_path))
            self.destroy()

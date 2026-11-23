// SPDX-License-Identifier: GPL-3.0-or-later
using System;
using System.IO;
using System.Linq;
using System.Drawing;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace CmykStore {
    public sealed class Gallery : Form {
        readonly ListView list = new ListView { Dock = DockStyle.Fill, View = View.LargeIcon, MultiSelect = false, HideSelection = false };
        readonly ImageList thumbnails = new ImageList { ImageSize = new Size(160, 120), ColorDepth = ColorDepth.Depth32Bit };
        readonly PictureBox preview = new PictureBox { Dock = DockStyle.Fill, SizeMode = PictureBoxSizeMode.Zoom, BackColor = Color.WhiteSmoke };
        readonly Label detail = new Label { Dock = DockStyle.Bottom, Height = 60, AutoEllipsis = true };
        readonly Label status = new Label { Dock = DockStyle.Fill, TextAlign = ContentAlignment.MiddleLeft };
        readonly TextBox path = new TextBox { Dock = DockStyle.Fill, ReadOnly = true };
        readonly Button accept = new Button { Text = "この写真を使う", Dock = DockStyle.Right, Width = 150, Enabled = false };
        CancellationTokenSource cancellation;
        int generation;
        public string SelectedFile { get; private set; }
        public Gallery(string initial) {
            Text = "写真を選ぶ — サムネイル一覧"; ClientSize = new Size(980, 620); MinimumSize = new Size(800, 500);
            Font = new Font("Yu Gothic UI", 10); AutoScaleMode = AutoScaleMode.Dpi;
            TableLayoutPanel grid = new TableLayoutPanel { Dock = DockStyle.Fill, Padding = new Padding(12), RowCount = 3, ColumnCount = 1 };
            grid.RowStyles.Add(new RowStyle(SizeType.Absolute, 38)); grid.RowStyles.Add(new RowStyle(SizeType.Percent, 100)); grid.RowStyles.Add(new RowStyle(SizeType.Absolute, 42));
            Controls.Add(grid);
            Panel top = new Panel { Dock = DockStyle.Fill };
            Button folder = new Button { Text = "フォルダーを選ぶ", Dock = DockStyle.Right, Width = 160 };
            top.Controls.Add(path); top.Controls.Add(folder); grid.Controls.Add(top, 0, 0);
            SplitContainer split = new SplitContainer { Dock = DockStyle.Fill, Size = new Size(950, 520), SplitterDistance = 620 };
            list.LargeImageList = thumbnails; split.Panel1.Controls.Add(list);
            split.Panel2.Controls.Add(preview); split.Panel2.Controls.Add(detail); grid.Controls.Add(split, 0, 1);
            Panel bottom = new Panel { Dock = DockStyle.Fill };
            Button cancel = new Button { Text = "キャンセル", Dock = DockStyle.Right, Width = 120, DialogResult = DialogResult.Cancel };
            bottom.Controls.Add(status); bottom.Controls.Add(accept); bottom.Controls.Add(cancel); grid.Controls.Add(bottom, 0, 2);
            folder.Click += delegate { using (FolderBrowserDialog dialog = new FolderBrowserDialog { SelectedPath = path.Text, Description = "写真があるフォルダーを選んでください" }) if (dialog.ShowDialog(this) == DialogResult.OK) LoadFolder(dialog.SelectedPath); };
            accept.Click += delegate { if (SelectedFile != null) { DialogResult = DialogResult.OK; Close(); } };
            list.ItemActivate += delegate { if (accept.Enabled) accept.PerformClick(); };
            list.SelectedIndexChanged += delegate {
                accept.Enabled = false; SelectedFile = null;
                if (list.SelectedItems.Count != 1) return;
                string file = Convert.ToString(list.SelectedItems[0].Tag);
                try {
                    Bitmap image = Files.Thumbnail(file, 380, 420); Image old = preview.Image; preview.Image = image; if (old != null) old.Dispose();
                    detail.Text = Path.GetFileName(file); SelectedFile = file; accept.Enabled = true;
                } catch (Exception e) { detail.Text = "読み込めない画像です：" + e.Message; }
            };
            Shown += delegate { LoadFolder(Directory.Exists(initial) ? initial : Environment.GetFolderPath(Environment.SpecialFolder.MyPictures)); };
            FormClosed += delegate { if (cancellation != null) cancellation.Cancel(); thumbnails.Dispose(); if (preview.Image != null) preview.Image.Dispose(); };
        }
        void LoadFolder(string folder) {
            try {
                string[] photos = Directory.GetFiles(folder).Where(p => new[] { ".jpg", ".jpeg", ".png" }.Contains(Path.GetExtension(p).ToLowerInvariant())).OrderBy(p => p, StringComparer.CurrentCultureIgnoreCase).ToArray();
                if (cancellation != null) cancellation.Cancel(); cancellation = new CancellationTokenSource(); CancellationToken token = cancellation.Token;
                int current = ++generation; path.Text = folder; SelectedFile = null; accept.Enabled = false;
                list.Items.Clear(); thumbnails.Images.Clear();
                Bitmap blank = new Bitmap(160, 120); using (Graphics g = Graphics.FromImage(blank)) g.Clear(Color.LightGray); thumbnails.Images.Add(blank); blank.Dispose();
                foreach (string file in photos) list.Items.Add(new ListViewItem(Path.GetFileName(file), 0) { Tag = file });
                status.Text = "写真 " + photos.Length + " 枚 / サムネイルを読み込み中";
                Task.Run(delegate {
                    for (int i = 0; i < photos.Length && !token.IsCancellationRequested; i++) {
                        Bitmap image = null; try { image = Files.Thumbnail(photos[i], 160, 120); } catch (Exception) { }
                        int index = i; Bitmap ready = image;
                        if (IsDisposed || token.IsCancellationRequested) { if (ready != null) ready.Dispose(); return; }
                        try { BeginInvoke((Action)delegate {
                            if (IsDisposed || current != generation) { if (ready != null) ready.Dispose(); return; }
                            if (ready != null) { thumbnails.Images.Add(ready); list.Items[index].ImageIndex = thumbnails.Images.Count - 1; ready.Dispose(); }
                            status.Text = "写真 " + photos.Length + " 枚 / 読み込み " + (index + 1) + " 枚";
                        }); } catch (InvalidOperationException) { if (ready != null) ready.Dispose(); return; }
                    }
                });
            } catch (Exception e) { status.Text = "フォルダーを開けません：" + e.Message; }
        }
    }
}

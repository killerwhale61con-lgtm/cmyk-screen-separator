// SPDX-License-Identifier: GPL-3.0-or-later
using System;
using System.IO;
using System.Linq;
using System.Drawing;
using System.Diagnostics;
using System.Text;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace CmykStore {
    public sealed class MainForm : Form {
        readonly TextBox input = new TextBox(), output = new TextBox(), ratioW = new TextBox { Text = "3", Width = 60 }, ratioH = new TextBox { Text = "2", Width = 60 };
        readonly ComboBox paper = new ComboBox(), ratio = new ComboBox(), mode = new ComboBox(), dpi = new ComboBox(), engine = new ComboBox();
        readonly NumericUpDown width = new NumericUpDown(), height = new NumericUpDown();
        readonly Label info = new Label { Dock = DockStyle.Fill }, stage = new Label { Dock = DockStyle.Fill, AutoEllipsis = true };
        readonly PictureBox preview = new PictureBox { Dock = DockStyle.Fill, SizeMode = PictureBoxSizeMode.Zoom, BackColor = Color.Gainsboro };
        readonly Button run = new Button { Text = "4色分解して書き出す", Dock = DockStyle.Fill }, save = new Button { Text = "保存先を選んで保存", Dock = DockStyle.Fill }, open = new Button { Text = "保存先を開く", Dock = DockStyle.Fill };
        readonly CheckBox after = new CheckBox { Text = "分解が終わってから保存先を選ぶ", Checked = true, AutoSize = true };
        readonly ProgressBar progress = new ProgressBar { Dock = DockStyle.Fill };
        readonly TableLayoutPanel grid = new TableLayoutPanel { Dock = DockStyle.Fill, Padding = new Padding(16), ColumnCount = 3, RowCount = 14 };
        Bitmap source; bool busy; string pending, last;
        public MainForm() {
            Text = "CMYK網点4色分解 — Microsoft Store版 開発中"; Font = new Font("Yu Gothic UI", 10);
            ClientSize = new Size(1040, 660); MinimumSize = new Size(860, 600); AutoScaleMode = AutoScaleMode.Dpi; AutoScroll = true;
            grid.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 190)); grid.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100)); grid.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 150));
            for (int i = 0; i < 7; i++) grid.RowStyles.Add(new RowStyle(SizeType.Absolute, 34));
            grid.RowStyles.Add(new RowStyle(SizeType.Absolute, 28)); grid.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
            foreach (int size in new[] { 28, 42, 24, 42, 34 }) grid.RowStyles.Add(new RowStyle(SizeType.Absolute, size));
            Controls.Add(grid);
            AddRow("入力画像 JPEG / PNG", input, 0); Button choose = new Button { Text = "写真を選ぶ", Dock = DockStyle.Fill }; grid.Controls.Add(choose, 2, 0);
            choose.Click += delegate { using (Gallery gallery = new Gallery(File.Exists(input.Text) ? Path.GetDirectoryName(input.Text) : Environment.GetFolderPath(Environment.SpecialFolder.MyPictures))) if (gallery.ShowDialog(this) == DialogResult.OK) { input.Text = gallery.SelectedFile; LoadImage(); } };
            input.Leave += delegate { if (!busy && File.Exists(input.Text)) LoadImage(); };
            Configure(paper, new[] { "A4（210 × 297 mm）", "A3（297 × 420 mm）", "任意サイズ" }); AddRow("JPEG全体の用紙サイズ", paper, 1);
            Button swap = new Button { Text = "縦横を入れ替え", Dock = DockStyle.Fill }; grid.Controls.Add(swap, 2, 1);
            FlowLayoutPanel dimensions = new FlowLayoutPanel { Dock = DockStyle.Fill, WrapContents = false };
            foreach (NumericUpDown control in new[] { width, height }) { control.Minimum = 1; control.Maximum = 2000; control.DecimalPlaces = 2; control.Width = 130; control.ValueChanged += delegate { RefreshPlan(); }; }
            dimensions.Controls.Add(new Label { Text = "幅 mm", AutoSize = true }); dimensions.Controls.Add(width); dimensions.Controls.Add(new Label { Text = "高さ mm", AutoSize = true }); dimensions.Controls.Add(height); AddRow("仕上がり寸法", dimensions, 2); grid.SetColumnSpan(dimensions, 2);
            swap.Click += delegate { decimal value = width.Value; width.Value = height.Value; height.Value = value; };
            Configure(ratio, new[] { "元画像の比率", "1:1", "3:2", "4:3", "カスタム" });
            FlowLayoutPanel ratios = new FlowLayoutPanel { Dock = DockStyle.Fill, WrapContents = false }; ratio.Width = 180;
            ratios.Controls.Add(ratio); ratios.Controls.Add(ratioW); ratios.Controls.Add(new Label { Text = ":", AutoSize = true }); ratios.Controls.Add(ratioH); AddRow("画像の比率（幅:高さ）", ratios, 3); grid.SetColumnSpan(ratios, 2);
            Configure(mode, new[] { "全体を収める（白余白）", "中央で切り抜く" }); AddRow("用紙との比率の調整", mode, 4);
            dpi.Items.AddRange(new object[] { "300", "600", "1200" }); dpi.Text = "300"; AddRow("出力解像度 DPI", dpi, 5);
            output.Text = Environment.GetFolderPath(Environment.SpecialFolder.MyPictures); AddRow("保存先（後でも指定可）", output, 6);
            Button chooseOutput = new Button { Text = "保存先を選ぶ", Dock = DockStyle.Fill }; grid.Controls.Add(chooseOutput, 2, 6);
            chooseOutput.Click += delegate { using (FolderBrowserDialog dialog = new FolderBrowserDialog { SelectedPath = output.Text }) if (dialog.ShowDialog(this) == DialogResult.OK) output.Text = dialog.SelectedPath; };
            grid.Controls.Add(after, 0, 7); grid.SetColumnSpan(after, 3);
            grid.Controls.Add(info, 0, 8); grid.SetColumnSpan(info, 2); grid.Controls.Add(preview, 2, 8);
            Label settings = new Label { Text = "共通設定：階調の反転1回 → 新聞印刷 / 円形 / 周期7 px / 45° / 品質1", Dock = DockStyle.Fill }; grid.Controls.Add(settings, 0, 9); grid.SetColumnSpan(settings, 3);
            TableLayoutPanel buttons = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 2, RowCount = 1 };
            buttons.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 50)); buttons.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 50)); buttons.Controls.Add(run, 0, 0); buttons.Controls.Add(save, 1, 0); grid.Controls.Add(buttons, 0, 10); grid.SetColumnSpan(buttons, 2); grid.Controls.Add(open, 2, 10);
            grid.Controls.Add(progress, 0, 11); grid.SetColumnSpan(progress, 3); grid.Controls.Add(stage, 0, 12); grid.SetColumnSpan(stage, 3);
            engine.DropDownStyle = ComboBoxStyle.DropDownList; engine.Items.AddRange(Engine.Discover().Cast<object>().ToArray()); if (engine.Items.Count > 0) engine.SelectedIndex = 0;
            AddRow("処理に使うGIMP", engine, 13); grid.SetColumnSpan(engine, 2);
            paper.SelectedIndexChanged += delegate { if (paper.SelectedIndex < 2) { width.Value = paper.SelectedIndex == 0 ? 210 : 297; height.Value = paper.SelectedIndex == 0 ? 297 : 420; } RefreshPlan(); };
            paper.SelectedIndex = 0; width.Value = 210; height.Value = 297;
            foreach (Control control in new Control[] { ratio, ratioW, ratioH, dpi, mode }) control.TextChanged += delegate { RefreshPlan(); };
            run.Click += async delegate { await StartJob(); }; save.Click += async delegate { await SavePending(); };
            open.Click += delegate { if (last != null) try { Process.Start(new ProcessStartInfo("explorer.exe", Engine.Quote(last)) { UseShellExecute = false }); } catch (Exception e) { stage.Text = e.Message; } };
            pending = Files.Pending(); SetBusy(false); stage.Text = pending == null ? "写真を選び、出力寸法を確認してください。" : "未保存の4版があります。「保存先を選んで保存」から再開できます。";
            FormClosing += delegate(object sender, FormClosingEventArgs e) { if (busy) { e.Cancel = true; MessageBox.Show(this, "処理が完了するまでお待ちください。"); } };
        }
        void AddRow(string text, Control control, int row) { grid.Controls.Add(new Label { Text = text, Dock = DockStyle.Fill, TextAlign = ContentAlignment.MiddleLeft }, 0, row); control.Dock = DockStyle.Fill; grid.Controls.Add(control, 1, row); }
        static void Configure(ComboBox combo, string[] values) { combo.DropDownStyle = ComboBoxStyle.DropDownList; combo.Items.AddRange(values); combo.SelectedIndex = 0; }
        void LoadImage() {
            try { Bitmap image = Files.LoadImage(input.Text); if (source != null) source.Dispose(); source = image; RefreshPlan(); }
            catch (Exception e) { if (source != null) source.Dispose(); source = null; stage.Text = "画像読み込み失敗：" + e.Message; }
        }
        Geometry GetPlan() {
            if (source == null) throw new ArgumentException("入力画像を選んでください。");
            int resolution; if (!Int32.TryParse(dpi.Text, out resolution)) throw new ArgumentException("DPIは整数で指定してください。");
            double aspect = (double)source.Width / source.Height;
            if (ratio.SelectedIndex == 1) aspect = 1; if (ratio.SelectedIndex == 2) aspect = 1.5; if (ratio.SelectedIndex == 3) aspect = 4.0 / 3;
            if (ratio.SelectedIndex == 4) { double a, b; if (!Double.TryParse(ratioW.Text, out a) || !Double.TryParse(ratioH.Text, out b) || !Geometry.FinitePositive(a) || !Geometry.FinitePositive(b)) throw new ArgumentException("比率は正の数で指定してください。"); aspect = a / b; }
            return Geometry.Create(source.Width, source.Height, (double)width.Value, (double)height.Value, resolution, aspect, mode.SelectedIndex == 0);
        }
        void RefreshPlan() {
            if (busy) return;
            try {
                Geometry plan = GetPlan(); info.Text = String.Format("出力：{0:N0} × {1:N0} px / {2} DPI\nJPEG全体：{3} × {4} mm\n元画像の比率切り抜き：{5}\n用紙との調整：{6}\n白い部分を含む枠全体がJPEGです。", plan.w, plan.h, plan.dpi, width.Value, height.Value, plan.ratio_crop ? "あり（中央）" : "なし", plan.margin ? "白余白あり" : plan.output_crop ? "中央切り抜きあり" : "余白・切り抜きなし");
                Image previous = preview.Image; preview.Image = Files.Preview(source, plan); if (previous != null) previous.Dispose();
            } catch (Exception e) { info.Text = e.Message; }
        }
        void Post(string text, int percent) { if (!IsDisposed) BeginInvoke((Action)delegate { stage.Text = text; progress.Value = Math.Max(0, Math.Min(100, percent)); }); }
        void SetBusy(bool value) {
            busy = value;
            foreach (Control control in grid.Controls) if (grid.GetRow(control) < 8 || grid.GetRow(control) == 13) control.Enabled = !value;
            run.Enabled = !value && pending == null; save.Enabled = !value && pending != null; open.Enabled = !value && last != null;
        }
        async Task StartJob() {
            if (busy || pending != null) return;
            string folder = null;
            try {
                LoadImage(); Geometry plan = GetPlan(); Engine selected = engine.SelectedItem as Engine;
                if (selected == null) throw new IOException("GIMP 3をインストールしてからアプリを再起動してください。");
                if (!after.Checked && String.IsNullOrWhiteSpace(output.Text)) throw new IOException("保存先を指定してください。");
                bool chooseAfter = after.Checked; string destination = output.Text, file = Path.GetFullPath(input.Text);
                folder = Path.Combine(Files.Jobs, Guid.NewGuid().ToString("N")); SetBusy(true); progress.Value = 1;
                await Task.Run(delegate { selected.Run(folder, file, plan, Post); });
                pending = folder; Files.RememberPending(folder); SetBusy(false); stage.Text = "分解が完了しました。保存先を選んでください。";
                if (chooseAfter) await SavePending(); else await SavePending(destination);
            } catch (Exception e) {
                if (folder != null && Directory.Exists(folder)) { File.WriteAllText(Path.Combine(folder, "app-error.txt"), e.ToString(), Encoding.UTF8); last = folder; }
                stage.Text = "処理に失敗しました：" + e.Message; SetBusy(false); MessageBox.Show(this, e.Message, "処理エラー", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }
        async Task SavePending(string selectedDestination = null) {
            if (busy || pending == null) return;
            if (selectedDestination == null) {
                using (FolderBrowserDialog dialog = new FolderBrowserDialog { Description = "分解済みの4枚を保存するフォルダーを選んでください", SelectedPath = Directory.Exists(output.Text) ? output.Text : Environment.GetFolderPath(Environment.SpecialFolder.MyPictures) }) {
                    if (dialog.ShowDialog(this) != DialogResult.OK) { stage.Text = "保存を保留しました。分解済みの4枚は保持しています。"; return; }
                    selectedDestination = dialog.SelectedPath;
                }
            }
            string sourceFolder = pending;
            try {
                SetBusy(true); progress.Value = 95; stage.Text = "分解済みの4枚を保存しています…";
                string stem = Path.GetFileNameWithoutExtension(Convert.ToString(Files.ReadJson(Path.Combine(sourceFolder, "job.json"))["input"]));
                string target = await Task.Run(delegate { return Files.Export(sourceFolder, selectedDestination, stem); });
                pending = null; last = target; output.Text = selectedDestination;
                try { Files.ClearPending(sourceFolder); } catch (IOException) { }
                SetBusy(false); progress.Value = 100; stage.Text = "保存完了：" + target;
            } catch (Exception e) { pending = sourceFolder; SetBusy(false); stage.Text = "保存失敗：" + e.Message + "。4枚は保持しているため再試行できます。"; }
        }
        [STAThread] public static void Main() {
            Application.EnableVisualStyles(); Application.SetCompatibleTextRenderingDefault(false);
            try { Application.Run(new MainForm()); }
            catch (Exception e) { Directory.CreateDirectory(Files.Data); File.WriteAllText(Path.Combine(Files.Data, "startup-error.txt"), e.ToString(), Encoding.UTF8); MessageBox.Show("起動に失敗しました：" + e.Message); }
        }
    }
}

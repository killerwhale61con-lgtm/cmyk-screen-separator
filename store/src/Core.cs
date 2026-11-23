// SPDX-License-Identifier: GPL-3.0-or-later
using System;
using System.IO;
using System.Linq;
using System.Text;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Imaging;
using System.Drawing.Drawing2D;
using System.Web.Script.Serialization;

namespace CmykStore {
    public sealed class Geometry {
        public int w, h, dpi;
        public int[] source, crop, draw;
        public bool ratio_crop, margin, output_crop;
        public static Geometry Create(int sw, int sh, double mmw, double mmh, int dpi, double ratio, bool fit) {
            if (dpi < 1 || dpi > 10000 || !FinitePositive(mmw) || !FinitePositive(mmh) || !FinitePositive(ratio))
                throw new ArgumentException("寸法・比率・DPIは正の数で指定してください。");
            long width = (long)Math.Floor(mmw / 25.4 * dpi + 0.5), height = (long)Math.Floor(mmh / 25.4 * dpi + 0.5);
            if (width < 1 || height < 1 || width > 30000 || height > 30000 || width * height > 400000000)
                throw new ArgumentException("各辺30000 px・合計4億画素以内にしてください。");
            int cw = sw, ch = sh;
            if ((double)sw / sh > ratio) cw = Math.Max(1, Math.Min(sw, (int)Math.Round(sh * ratio)));
            else ch = Math.Max(1, Math.Min(sh, (int)Math.Round(sw / ratio)));
            double scale = fit ? Math.Min((double)width / cw, (double)height / ch) : Math.Max((double)width / cw, (double)height / ch);
            int dw = Math.Max(1, (int)Math.Round(cw * scale)), dh = Math.Max(1, (int)Math.Round(ch * scale));
            return new Geometry { w = (int)width, h = (int)height, dpi = dpi, source = new[] { sw, sh },
                crop = new[] { (sw - cw) / 2, (sh - ch) / 2, cw, ch },
                draw = new[] { FloorHalf((int)width - dw), FloorHalf((int)height - dh), dw, dh },
                ratio_crop = cw != sw || ch != sh, margin = dw < width || dh < height, output_crop = dw > width || dh > height };
        }
        static int FloorHalf(int value) { return (int)Math.Floor(value / 2.0); }
        public static bool FinitePositive(double value) { return value > 0 && !double.IsNaN(value) && !double.IsInfinity(value); }
    }

    public static class Files {
        public static readonly JavaScriptSerializer Json = new JavaScriptSerializer { MaxJsonLength = 20000000 };
        public static string Root { get { return AppDomain.CurrentDomain.BaseDirectory; } }
        public static string Data { get { return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "CMYKScreenSeparator"); } }
        public static string Jobs { get { return Path.Combine(Data, "jobs"); } }
        public static void WriteJson(string path, object value) { File.WriteAllText(path, Json.Serialize(value), new UTF8Encoding(false)); }
        public static Dictionary<string, object> ReadJson(string path) { return Json.Deserialize<Dictionary<string, object>>(File.ReadAllText(path, Encoding.UTF8)); }
        public static Bitmap LoadImage(string path) {
            string suffix = Path.GetExtension(path).ToLowerInvariant();
            if (suffix != ".jpg" && suffix != ".jpeg" && suffix != ".png") throw new ArgumentException("JPEGまたはPNGを選んでください。");
            using (Image image = Image.FromFile(path, true)) {
                if (image.PropertyIdList.Contains(0x112)) {
                    int orientation = image.GetPropertyItem(0x112).Value[0];
                    RotateFlipType[] transforms = { RotateFlipType.RotateNoneFlipNone, RotateFlipType.RotateNoneFlipNone,
                        RotateFlipType.RotateNoneFlipX, RotateFlipType.Rotate180FlipNone, RotateFlipType.Rotate180FlipX,
                        RotateFlipType.Rotate90FlipX, RotateFlipType.Rotate90FlipNone, RotateFlipType.Rotate270FlipX, RotateFlipType.Rotate270FlipNone };
                    if (orientation >= 1 && orientation <= 8) image.RotateFlip(transforms[orientation]);
                }
                return new Bitmap(image);
            }
        }
        public static Bitmap Thumbnail(string path, int width, int height) {
            using (Bitmap source = LoadImage(path)) {
                double scale = Math.Min((double)width / source.Width, (double)height / source.Height);
                Bitmap result = new Bitmap(width, height);
                using (Graphics g = Graphics.FromImage(result)) {
                    g.Clear(Color.WhiteSmoke); g.InterpolationMode = InterpolationMode.HighQualityBicubic;
                    int w = Math.Max(1, (int)(source.Width * scale)), h = Math.Max(1, (int)(source.Height * scale));
                    g.DrawImage(source, (width - w) / 2, (height - h) / 2, w, h);
                }
                return result;
            }
        }
        public static Bitmap Preview(Bitmap source, Geometry plan) {
            double scale = Math.Min(340.0 / plan.w, 180.0 / plan.h);
            int width = Math.Max(1, (int)Math.Round(plan.w * scale)), height = Math.Max(1, (int)Math.Round(plan.h * scale));
            Bitmap result = new Bitmap(width, height);
            using (Graphics g = Graphics.FromImage(result)) {
                g.Clear(Color.White); g.InterpolationMode = InterpolationMode.HighQualityBicubic;
                g.DrawImage(source, new Rectangle((int)Math.Round(plan.draw[0] * scale), (int)Math.Round(plan.draw[1] * scale),
                    Math.Max(1, (int)Math.Round(plan.draw[2] * scale)), Math.Max(1, (int)Math.Round(plan.draw[3] * scale))),
                    new Rectangle(plan.crop[0], plan.crop[1], plan.crop[2], plan.crop[3]), GraphicsUnit.Pixel);
            }
            return result;
        }
        public static void VerifyJpegs(string folder, Geometry plan) {
            foreach (char channel in "CMYK") {
                string path = Path.Combine(folder, channel + ".JPEG");
                byte[] data = File.ReadAllBytes(path); int pos = 2, w = 0, h = 0, components = 0, dx = 0, dy = 0, unit = 0;
                if (data.Length < 4 || data[0] != 255 || data[1] != 216) throw new IOException(channel + "版がJPEGではありません。");
                while (pos < data.Length - 4) {
                    if (data[pos++] != 255) throw new IOException("JPEGマーカーが不正です。");
                    while (data[pos] == 255) pos++;
                    int marker = data[pos++]; if (marker == 218 || marker == 217) break;
                    int size = data[pos] * 256 + data[pos + 1], start = pos + 2;
                    if (size < 2 || pos + size > data.Length) throw new IOException("JPEGセグメントが不正です。");
                    if (marker == 224 && size >= 16 && Encoding.ASCII.GetString(data, start, 5) == "JFIF\0") {
                        unit = data[start + 7]; dx = data[start + 8] * 256 + data[start + 9]; dy = data[start + 10] * 256 + data[start + 11];
                    }
                    if (marker == 192 || marker == 193 || marker == 194) {
                        h = data[start + 1] * 256 + data[start + 2]; w = data[start + 3] * 256 + data[start + 4]; components = data[start + 5];
                    }
                    pos += size;
                }
                if (w != plan.w || h != plan.h || components != 1 || unit != 1 || dx != plan.dpi || dy != plan.dpi)
                    throw new IOException(channel + ".JPEGの寸法・DPI・白黒形式の検査に失敗しました。");
            }
        }
        public static string Export(string source, string destination, string stem) {
            foreach (char c in "CMYK") if (!File.Exists(Path.Combine(source, c + ".JPEG"))) throw new IOException("4枚がそろっていません。");
            Directory.CreateDirectory(destination);
            foreach (char c in Path.GetInvalidFileNameChars()) stem = stem.Replace(c, '_');
            if (stem.Length > 90) stem = stem.Substring(0, 90);
            string target = Path.Combine(destination, stem + "_" + DateTime.Now.ToString("yyyyMMdd_HHmmss") + "_" + Guid.NewGuid().ToString("N").Substring(0, 8));
            string staging = Path.Combine(destination, ".cmyk-saving-" + Guid.NewGuid().ToString("N"));
            if (Directory.Exists(target)) throw new IOException("保存先が既に存在します。");
            Directory.CreateDirectory(staging);
            try {
                foreach (string file in Directory.GetFiles(source)) File.Copy(file, Path.Combine(staging, Path.GetFileName(file)), false);
                Directory.Move(staging, target);
            } catch {
                if (Path.GetDirectoryName(Path.GetFullPath(staging)) == Path.GetFullPath(destination) && Directory.Exists(staging)) Directory.Delete(staging, true);
                throw;
            }
            return target;
        }
        public static void RememberPending(string folder) { Directory.CreateDirectory(Data); WriteJson(Path.Combine(Data, "pending.json"), new { folder = folder }); }
        public static string Pending() {
            try {
                string folder = Convert.ToString(ReadJson(Path.Combine(Data, "pending.json"))["folder"]);
                if (Path.GetDirectoryName(Path.GetFullPath(folder)) != Path.GetFullPath(Jobs)) return null;
                if ("CMYK".All(c => File.Exists(Path.Combine(folder, c + ".JPEG")))) return folder;
            } catch (Exception) { }
            return null;
        }
        public static void ClearPending(string folder) {
            if (Path.GetDirectoryName(Path.GetFullPath(folder)) != Path.GetFullPath(Jobs)) throw new IOException("作業フォルダーの範囲外です。");
            string record = Path.Combine(Data, "pending.json"); if (File.Exists(record)) File.Delete(record);
            if (Directory.Exists(folder)) Directory.Delete(folder, true);
        }
    }
}

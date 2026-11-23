// SPDX-License-Identifier: GPL-3.0-or-later
using System;
using System.IO;
using System.Text;
using System.Collections.Generic;
using System.Diagnostics;
using System.Threading;
using System.Threading.Tasks;
using System.Runtime.InteropServices;
using System.Xml.Linq;
using Microsoft.Win32;

namespace CmykStore {
    public sealed class Engine {
        public string DisplayName, Executable, AppUserModelId;
        public override string ToString() { return DisplayName; }
        public static List<Engine> Discover() {
            List<Engine> found = new List<Engine>();
            const string packages = @"Software\Classes\Local Settings\Software\Microsoft\Windows\CurrentVersion\AppModel\Repository\Packages";
            using (RegistryKey root = Registry.CurrentUser.OpenSubKey(packages)) {
                if (root != null) foreach (string name in root.GetSubKeyNames()) {
                    if (!name.StartsWith("GIMP.", StringComparison.OrdinalIgnoreCase)) continue;
                    try {
                        using (RegistryKey key = root.OpenSubKey(name)) {
                            string location = Convert.ToString(key.GetValue("PackageRootFolder"));
                            XDocument manifest = XDocument.Load(Path.Combine(location, "AppxManifest.xml"));
                            XNamespace ns = "http://schemas.microsoft.com/appx/manifest/foundation/windows10";
                            XElement application = manifest.Root.Element(ns + "Applications").Element(ns + "Application");
                            string[] parts = name.Split('_');
                            string family = parts[0] + "_" + parts[parts.Length - 1];
                            found.Add(new Engine { DisplayName = "Microsoft Store版GIMP（正式なアプリ起動API）", AppUserModelId = family + "!" + (string)application.Attribute("Id") });
                        }
                    } catch (Exception) { }
                }
            }
            string[] roots = { Environment.GetEnvironmentVariable("CMYK_GIMP_ROOT"),
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Programs", "GIMP 3"),
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), "AppData", "Local", "Programs", "GIMP 3"),
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), "GIMP 3"),
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), "GIMP 3.2") };
            HashSet<string> paths = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            foreach (string root in roots) {
                if (String.IsNullOrEmpty(root)) continue;
                string exe = Path.Combine(root, "bin", "gimp-console-3.exe");
                if (File.Exists(exe) && paths.Add(Path.GetFullPath(exe))) found.Add(new Engine { DisplayName = "通常版GIMP — " + root, Executable = Path.GetFullPath(exe) });
            }
            return found;
        }
        public static string Quote(string text) {
            StringBuilder value = new StringBuilder("\""); int slashes = 0;
            foreach (char c in text) {
                if (c == '\\') { slashes++; continue; }
                if (c == '"') { value.Append('\\', slashes * 2 + 1); value.Append(c); }
                else { value.Append('\\', slashes); value.Append(c); }
                slashes = 0;
            }
            value.Append('\\', slashes * 2); value.Append('"'); return value.ToString();
        }
        public void Run(string folder, string input, Geometry geometry, Action<string, int> progress) {
            Directory.CreateDirectory(folder);
            string job = Path.Combine(folder, "job.json"), worker = Path.Combine(Files.Root, "worker.py");
            Files.WriteJson(job, new { input = input, prepared = "", dpi = geometry.dpi, width = geometry.w, height = geometry.h, geometry = geometry });
            string profile = Path.Combine(Files.Data, "gimp-profile"); Directory.CreateDirectory(profile);
            string gimprc = Path.Combine(profile, "gimprc");
            if (!File.Exists(gimprc)) File.WriteAllText(gimprc, "(check-updates no)\n", Encoding.UTF8);
            string code = "exec(open(" + Files.Json.Serialize(worker.Replace('\\', '/')) + ",encoding='utf-8').read());run_job(" + Files.Json.Serialize(job.Replace('\\', '/')) + ")";
            string arguments = "-n -i -d -f --no-splash --gimprc " + Quote(gimprc) + " --batch-interpreter=python-fu-eval -b " + Quote(code) + " --quit";
            Process process = null; Task<string> stdout = null, stderr = null;
            string log = Path.Combine(folder, "gimp-launch.log");
            try {
                progress("GIMPを起動しています", 3);
                if (AppUserModelId != null) {
                    IApplicationActivationManager manager = (IApplicationActivationManager)new ApplicationActivationManager();
                    uint pid; int result = manager.ActivateApplication(AppUserModelId, arguments, 0, out pid);
                    Marshal.ThrowExceptionForHR(result);
                    File.WriteAllText(log, "Store activation requested. PID=" + pid + "\n" + AppUserModelId, Encoding.UTF8);
                    Marshal.ReleaseComObject(manager);
                } else {
                    ProcessStartInfo info = new ProcessStartInfo(Executable, arguments) {
                        UseShellExecute = false, CreateNoWindow = true, RedirectStandardOutput = true, RedirectStandardError = true,
                        WorkingDirectory = Files.Root, StandardOutputEncoding = Encoding.UTF8, StandardErrorEncoding = Encoding.UTF8 };
                    info.EnvironmentVariables["GIMP3_DIRECTORY"] = profile;
                    process = Process.Start(info); stdout = process.StandardOutput.ReadToEndAsync(); stderr = process.StandardError.ReadToEndAsync();
                }
                DateTime deadline = DateTime.UtcNow.AddMinutes(45);
                DateTime startupDeadline = DateTime.UtcNow.AddMinutes(10);
                while (true) {
                    if (DateTime.UtcNow > deadline) throw new IOException("GIMPの処理が制限時間を超えました。既存のGIMPは強制終了していません。");
                    try {
                        Dictionary<string, object> status = Files.ReadJson(Path.Combine(folder, "status.json"));
                        string stage = Convert.ToString(status["stage"]); int percent = Convert.ToInt32(status["progress"]);
                        progress(stage, Math.Min(90, percent * 9 / 10));
                        if (Convert.ToBoolean(status["error"])) throw new GimpJobException(stage);
                        if (percent == 100) break;
                    } catch (FileNotFoundException) { }
                    catch (ArgumentException) { }
                    if (process != null && process.HasExited) {
                        try {
                            Dictionary<string, object> final = Files.ReadJson(Path.Combine(folder, "status.json"));
                            if (!Convert.ToBoolean(final["error"]) && Convert.ToInt32(final["progress"]) == 100) break;
                        } catch (Exception) { }
                        File.WriteAllText(log, stdout.Result + "\n" + stderr.Result, Encoding.UTF8);
                        throw new IOException("GIMPが分解完了前に終了しました。作業ログ：" + log);
                    }
                    if (!File.Exists(Path.Combine(folder, "status.json")) && DateTime.UtcNow > startupDeadline)
                        throw new IOException("GIMPのバッチ開始を確認できませんでした。GIMPは強制終了していません。作業ログ：" + log);
                    Thread.Sleep(500);
                }
                Files.VerifyJpegs(folder, geometry);
                if (process != null) {
                    process.WaitForExit(10000);
                    if (process.HasExited) File.WriteAllText(log, stdout.Result + "\n" + stderr.Result, Encoding.UTF8);
                }
            } finally { if (process != null) process.Dispose(); }
        }
    }
    public sealed class GimpJobException : IOException { public GimpJobException(string message) : base(message) { } }
    [ComImport, Guid("45BA127D-10A8-46EA-8AB7-56EA9078943C")]
    public class ApplicationActivationManager { }
    [ComImport, Guid("2e941141-7f97-4756-ba1d-9decde894a3d"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    public interface IApplicationActivationManager {
        [PreserveSig] int ActivateApplication([MarshalAs(UnmanagedType.LPWStr)] string id, [MarshalAs(UnmanagedType.LPWStr)] string arguments, uint options, out uint processId);
        [PreserveSig] int ActivateForFile(IntPtr id, IntPtr items, IntPtr verb, out uint processId);
        [PreserveSig] int ActivateForProtocol(IntPtr id, IntPtr items, out uint processId);
    }
}

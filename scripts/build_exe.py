"""Generate multi-size Windows icon and build standalone SayanClicker.exe via PyInstaller."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = ROOT / "assets"
SPRITES_DIR = ASSETS_DIR / "sprites"
SOUNDS_DIR = ASSETS_DIR / "sounds"
ICON_PATH = ASSETS_DIR / "sayan_icon.ico"
DIST_DIR = ROOT / "dist"
BUILD_DIR = ROOT / "build"

LAUNCHER_CS_TEMPLATE = r'''using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Text;
using System.Threading;
using System.Windows.Forms;

internal static class SayanLauncher
{
    private const string BuildId = "__BUILD_ID__";
    private const string CoreExeName = "SayanClickerCore.exe";
    private const string ResourceName = "SayanClicker.app.zip";

    [STAThread]
    private static int Main(string[] args)
    {
        var errors = new List<string>();
        string exeLocation = Assembly.GetExecutingAssembly().Location;
        string exeDir = string.IsNullOrEmpty(exeLocation) ? Environment.CurrentDirectory : Path.GetDirectoryName(exeLocation);

        string[] candidates = new[]
        {
            CombineIfValid(Environment.GetEnvironmentVariable("LOCALAPPDATA"), "SayanClicker"),
            CombineIfValid(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "SayanClicker"),
            CombineIfValid(Environment.GetEnvironmentVariable("APPDATA"), "SayanClicker"),
            CombineIfValid(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "SayanClicker"),
            CombineIfValid(Path.GetTempPath(), "SayanClicker"),
            CombineIfValid(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), ".sayan_clicker"),
            CombineIfValid(exeDir, ".sayan_cache"),
        };

        var tried = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (string baseDir in candidates)
        {
            if (string.IsNullOrEmpty(baseDir) || !tried.Add(baseDir))
            {
                continue;
            }
            try
            {
                string coreExe = EnsureExtracted(baseDir);
                return LaunchCore(coreExe, args);
            }
            catch (Exception ex)
            {
                errors.Add(baseDir + " -> " + ex.GetType().Name + ": " + ex.Message);
            }
        }

        MessageBox.Show(
            "Не удалось распаковать и запустить «Кот Саян».\n\nПопробованы папки:\n" + string.Join("\n", errors),
            "Кот Саян — Ошибка запуска",
            MessageBoxButtons.OK,
            MessageBoxIcon.Error
        );
        return 1;
    }

    private static string CombineIfValid(string root, string child)
    {
        if (string.IsNullOrWhiteSpace(root))
        {
            return null;
        }
        return Path.Combine(root, child);
    }

    private static void VerifyWritable(string dir)
    {
        Directory.CreateDirectory(dir);
        string probe = Path.Combine(dir, ".probe_" + Process.GetCurrentProcess().Id + "_" + Guid.NewGuid().ToString("N").Substring(0, 6));
        File.WriteAllBytes(probe, new byte[] { 83, 65, 89, 65, 78 });
        File.Delete(probe);
    }

    private static string EnsureExtracted(string baseDir)
    {
        VerifyWritable(baseDir);
        string targetDir = Path.Combine(baseDir, "app-" + BuildId);
        string coreExe = Path.Combine(targetDir, CoreExeName);

        using (var mutex = new Mutex(false, "Local\\SayanClickerExtract_" + BuildId))
        {
            bool acquired = false;
            try
            {
                try
                {
                    acquired = mutex.WaitOne(TimeSpan.FromSeconds(45));
                }
                catch (AbandonedMutexException)
                {
                    acquired = true;
                }

                if (!File.Exists(coreExe))
                {
                    string stagingDir = Path.Combine(baseDir, "_staging_" + BuildId + "_" + Guid.NewGuid().ToString("N").Substring(0, 8));
                    Directory.CreateDirectory(stagingDir);
                    try
                    {
                        using (Stream resStream = Assembly.GetExecutingAssembly().GetManifestResourceStream(ResourceName))
                        {
                            if (resStream == null)
                            {
                                throw new InvalidOperationException("Embedded payload missing: " + ResourceName);
                            }
                            using (var archive = new ZipArchive(resStream, ZipArchiveMode.Read))
                            {
                                string fullStagingRoot = Path.GetFullPath(stagingDir) + Path.DirectorySeparatorChar;
                                foreach (ZipArchiveEntry entry in archive.Entries)
                                {
                                    string relPath = entry.FullName.Replace('/', Path.DirectorySeparatorChar);
                                    string destPath = Path.GetFullPath(Path.Combine(stagingDir, relPath));
                                    if (!destPath.StartsWith(fullStagingRoot, StringComparison.OrdinalIgnoreCase))
                                    {
                                        throw new InvalidDataException("Invalid archive entry path: " + entry.FullName);
                                    }
                                    if (string.IsNullOrEmpty(entry.Name))
                                    {
                                        Directory.CreateDirectory(destPath);
                                        continue;
                                    }
                                    string parent = Path.GetDirectoryName(destPath);
                                    if (!string.IsNullOrEmpty(parent))
                                    {
                                        Directory.CreateDirectory(parent);
                                    }
                                    entry.ExtractToFile(destPath, true);
                                }
                            }
                        }

                        string stagedExe = Path.Combine(stagingDir, CoreExeName);
                        if (!File.Exists(stagedExe))
                        {
                            throw new FileNotFoundException("Extracted executable not found", stagedExe);
                        }

                        if (Directory.Exists(targetDir))
                        {
                            Directory.Delete(targetDir, true);
                        }
                        Directory.Move(stagingDir, targetDir);
                    }
                    finally
                    {
                        try
                        {
                            if (Directory.Exists(stagingDir))
                            {
                                Directory.Delete(stagingDir, true);
                            }
                        }
                        catch
                        {
                        }
                    }
                }

                CleanupOldVersions(baseDir, "app-" + BuildId);
            }
            finally
            {
                if (acquired)
                {
                    try
                    {
                        mutex.ReleaseMutex();
                    }
                    catch
                    {
                    }
                }
            }
        }

        return coreExe;
    }

    private static void CleanupOldVersions(string baseDir, string keepFolderName)
    {
        try
        {
            foreach (string dir in Directory.GetDirectories(baseDir))
            {
                string name = Path.GetFileName(dir);
                if (name == null)
                {
                    continue;
                }
                if ((name.StartsWith("app-", StringComparison.OrdinalIgnoreCase) && !string.Equals(name, keepFolderName, StringComparison.OrdinalIgnoreCase))
                    || name.StartsWith("_staging_", StringComparison.OrdinalIgnoreCase))
                {
                    try
                    {
                        Directory.Delete(dir, true);
                    }
                    catch
                    {
                    }
                }
            }
        }
        catch
        {
        }
    }

    private static int LaunchCore(string coreExe, string[] args)
    {
        var psi = new ProcessStartInfo
        {
            FileName = coreExe,
            WorkingDirectory = Path.GetDirectoryName(coreExe) ?? Environment.CurrentDirectory,
            Arguments = JoinArguments(args),
            UseShellExecute = false,
            CreateNoWindow = true,
        };
        using (Process proc = Process.Start(psi))
        {
            if (proc == null)
            {
                throw new InvalidOperationException("Process.Start returned null for " + coreExe);
            }
            proc.WaitForExit();
            return proc.ExitCode;
        }
    }

    private static string JoinArguments(string[] args)
    {
        if (args == null || args.Length == 0)
        {
            return string.Empty;
        }
        var sb = new StringBuilder();
        foreach (string arg in args)
        {
            if (sb.Length > 0)
            {
                sb.Append(' ');
            }
            sb.Append('"').Append(arg.Replace("\"", "\\\"")).Append('"');
        }
        return sb.ToString();
    }
}
'''


def generate_app_icon() -> Path:
    """Create a warm peach-badge Windows .ico from curious Sayan sprite."""
    curious_png = SPRITES_DIR / "curious.png"
    if not curious_png.is_file():
        raise FileNotFoundError(f"Missing sprite for app icon: {curious_png}")

    base_size = 512
    badge = Image.new("RGBA", (base_size, base_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(badge)
    draw.rounded_rectangle(
        (20, 20, base_size - 20, base_size - 20),
        radius=128,
        fill=(255, 240, 234, 255),
        outline=(255, 122, 80, 255),
        width=20,
    )

    with Image.open(curious_png) as cat_im:
        cat_rgba = cat_im.convert("RGBA")
        bbox = cat_rgba.getbbox()
        if bbox:
            cat_rgba = cat_rgba.crop(bbox)
        cat_rgba.thumbnail((420, 420), Image.Resampling.LANCZOS)
        ox = (base_size - cat_rgba.width) // 2
        oy = (base_size - cat_rgba.height) // 2 + 10
        badge.paste(cat_rgba, (ox, oy), cat_rgba)

    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    badge.save(ICON_PATH, format="ICO", sizes=sizes)
    print(f"Generated app icon -> {ICON_PATH} ({ICON_PATH.stat().st_size} bytes)")
    return ICON_PATH


def _find_csc_exe() -> Path:
    """Locate .NET Framework 4.x x64 C# compiler built into Windows 10/11."""
    candidates = [
        Path(os.environ.get("WINDIR", r"C:\Windows"))
        / "Microsoft.NET"
        / "Framework64"
        / "v4.0.30319"
        / "csc.exe",
        Path(os.environ.get("WINDIR", r"C:\Windows"))
        / "Microsoft.NET"
        / "Framework"
        / "v4.0.30319"
        / "csc.exe",
    ]
    for c in candidates:
        if c.is_file():
            return c
    raise FileNotFoundError("Could not locate .NET Framework 4.x csc.exe")


def _zip_directory(src_dir: Path, zip_path: Path) -> str:
    """Create a deterministic ZIP of src_dir contents and return 12-char SHA256 build ID."""
    if zip_path.exists():
        zip_path.unlink()
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in src_dir.rglob("*") if p.is_file())
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for file_path in files:
            rel = file_path.relative_to(src_dir).as_posix()
            info = zipfile.ZipInfo(rel, date_time=(2026, 11, 12, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, file_path.read_bytes())

    h = hashlib.sha256()
    with zip_path.open("rb") as fh:
        while True:
            chunk = fh.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()[:12]


def build_exe() -> Path:
    """Build PyInstaller --onedir core and wrap it into a single standalone GUI .exe launcher."""
    generate_app_icon()

    onedir_dist = BUILD_DIR / "onedir_dist"
    onedir_work = BUILD_DIR / "onedir_work"
    shutil.rmtree(onedir_dist, ignore_errors=True)
    shutil.rmtree(onedir_work, ignore_errors=True)
    DIST_DIR.mkdir(parents=True, exist_ok=True)

    pyi_cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--windowed",
        "--noconsole",
        "--noupx",
        "--name",
        "SayanClickerCore",
        "--distpath",
        str(onedir_dist),
        "--workpath",
        str(onedir_work),
        "--specpath",
        str(BUILD_DIR),
        "--icon",
        str(ICON_PATH),
        "--add-data",
        f"{SPRITES_DIR};assets/sprites",
        "--add-data",
        f"{SOUNDS_DIR};assets/sounds",
        "--add-data",
        f"{ICON_PATH};assets",
        "--exclude-module",
        "numpy",
        "--exclude-module",
        "matplotlib",
        "--exclude-module",
        "playwright",
        "--exclude-module",
        "pytest",
        str(ROOT / "main.py"),
    ]
    print("Running PyInstaller core build:", " ".join(pyi_cmd))
    subprocess.run(pyi_cmd, cwd=str(ROOT), check=True)

    core_dir = onedir_dist / "SayanClickerCore"
    if not (core_dir / "SayanClickerCore.exe").is_file():
        raise FileNotFoundError(f"Missing core exe in {core_dir}")

    payload_zip = BUILD_DIR / "SayanClickerCore.zip"
    build_id = _zip_directory(core_dir, payload_zip)
    print(f"Packed payload ZIP -> {payload_zip} ({payload_zip.stat().st_size} bytes, id={build_id})")

    csc_exe = _find_csc_exe()
    fx_dir = csc_exe.parent
    cs_path = BUILD_DIR / "SayanLauncher.cs"
    cs_path.write_text(LAUNCHER_CS_TEMPLATE.replace("__BUILD_ID__", build_id), encoding="utf-8-sig")

    exe_path = DIST_DIR / "SayanClicker.exe"
    if exe_path.exists():
        exe_path.unlink()

    csc_cmd = [
        str(csc_exe),
        "/nologo",
        "/target:winexe",
        "/platform:x64",
        "/optimize+",
        "/codepage:65001",
        f"/win32icon:{ICON_PATH}",
        "/reference:System.dll",
        "/reference:System.Windows.Forms.dll",
        f"/reference:{fx_dir / 'System.IO.Compression.dll'}",
        f"/reference:{fx_dir / 'System.IO.Compression.FileSystem.dll'}",
        f"/resource:{payload_zip},SayanClicker.app.zip",
        f"/out:{exe_path}",
        str(cs_path),
    ]
    print("Compiling native single-file launcher:", " ".join(csc_cmd))
    subprocess.run(csc_cmd, cwd=str(ROOT), check=True)

    if not exe_path.is_file():
        raise FileNotFoundError(f"Expected built exe not found: {exe_path}")
    print(f"Built standalone EXE -> {exe_path} ({exe_path.stat().st_size} bytes)")
    return exe_path


if __name__ == "__main__":
    build_exe()

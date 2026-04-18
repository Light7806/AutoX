import ctypes
import json
import os
import shutil
import subprocess
import threading
import time
import hashlib
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import customtkinter as ctk
import google.generativeai as genai

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
LOCALAPPDATA = os.getenv("LOCALAPPDATA", "")
DEFAULT_CHROME_USER_DATA_DIR = str(Path(LOCALAPPDATA) / "Google" / "Chrome" / "User Data") if LOCALAPPDATA else ""
CHROME_USER_DATA_DIR = os.getenv("CHROME_USER_DATA_DIR", DEFAULT_CHROME_USER_DATA_DIR).strip()
CHROME_PROFILE_NAME = os.getenv("CHROME_PROFILE_NAME", "Default").strip() or "Default"
REMOTE_DEBUGGING_PORT = int(os.getenv("CHROME_DEBUG_PORT", "9222"))

GEMINI_API_KEY = os.getenv("", "").strip()
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    GEMINI_MODEL = genai.GenerativeModel("gemini-2.5-flash")
else:
    GEMINI_MODEL = None

# ─────────────────────────────────────────────
# SITE MAPS
# ─────────────────────────────────────────────
KNOWN_SITES = {
    "amazon":   "https://www.amazon.in",
    "flipkart": "https://www.flipkart.com",
    "zepto":    "https://www.zeptonow.com",
    "gumroad":  "https://gumroad.com",
    "youtube":  "https://www.youtube.com",
    "gemini":   "https://gemini.google.com",
    "claude":   "https://claude.ai",
    "chatgpt":  "https://chatgpt.com",
    "openai":   "https://openai.com",
    "gmail":    "https://mail.google.com",
    "calendar": "https://calendar.google.com",
}

DELIVERY_SITES = {
    "amazon":   {"label": "Amazon",   "search_url": "https://www.amazon.in/s?k={query}"},
    "flipkart": {"label": "Flipkart", "search_url": "https://www.flipkart.com/search?q={query}"},
}

PRODUCT_HINTS = {
    "shoe", "shoes", "sneaker", "sneakers", "milk", "bottle", "bottles",
    "keyboard", "mouse", "phone", "laptop", "charger", "bag", "watch",
    "headphones", "earbuds", "shirt", "tshirt", "pant", "rice", "soap",
    "groceries", "grocery", "book", "books",
}

# ─────────────────────────────────────────────
# FILE ORGANIZER — TASK 2
# ─────────────────────────────────────────────
FILE_CATEGORIES = {
    "PDFs":        [".pdf"],
    "Images":      [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".ico"],
    "Videos":      [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm"],
    "Audio":       [".mp3", ".wav", ".aac", ".flac", ".ogg", ".m4a"],
    "Documents":   [".doc", ".docx", ".txt", ".odt", ".rtf", ".pages"],
    "Sheets":      [".xls", ".xlsx", ".csv", ".ods", ".numbers"],
    "Slides":      [".ppt", ".pptx", ".odp", ".key"],
    "Archives":    [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"],
    "Code":        [".py", ".js", ".ts", ".html", ".css", ".json", ".xml", ".sh", ".bat", ".java", ".c", ".cpp"],
    "Executables": [".exe", ".msi", ".dmg", ".apk"],
    "Others":      [],
}

ARCHIVED_FOLDER_NAME = "Archived"

SKIP_FOLDERS = {
    "node_modules", ".git", ".svn", "__pycache__",
    "venv", ".venv", "env", ".env",
    "AppData", "System Volume Information",
    "$RECYCLE.BIN", "Windows", "Program Files",
}


def get_downloads_folder():
    home = Path.home()
    for candidate in [home / "Downloads", home / "Download"]:
        if candidate.exists():
            return candidate
    return home / "Downloads"


def organize_downloads(log_callback, target_folder: Path = None):
    folder = target_folder or get_downloads_folder()
    if not folder.exists():
        log_callback(f"Folder not found: {folder}")
        return

    files = [f for f in folder.iterdir() if f.is_file()]
    if not files:
        subfolders = [d for d in folder.iterdir() if d.is_dir()]
        if subfolders:
            log_callback(f"Downloads is already organised into {len(subfolders)} folder(s).")
            log_callback("Say 'undo organize' to restore.")
        else:
            log_callback("No files found. Nothing to organise.")
        return

    log_callback(f"Scanning {folder}  ({len(files)} file(s) found)...")
    moved = {}
    skipped = []

    for file in files:
        ext = file.suffix.lower()
        dest_category = "Others"
        for category, extensions in FILE_CATEGORIES.items():
            if ext in extensions:
                dest_category = category
                break

        dest_dir = folder / dest_category
        dest_dir.mkdir(exist_ok=True)
        dest_path = dest_dir / file.name

        if dest_path.exists():
            stem, counter = file.stem, 1
            while dest_path.exists():
                dest_path = dest_dir / f"{stem}_{counter}{file.suffix}"
                counter += 1

        try:
            shutil.move(str(file), str(dest_path))
            moved.setdefault(dest_category, []).append(file.name)
        except Exception as e:
            skipped.append(f"{file.name} ({e})")

    if moved:
        log_callback("── Organised ──────────────────────────")
        for category, names in sorted(moved.items()):
            log_callback(f"  {category}/  ← {len(names)} file(s)")
        log_callback(f"Total moved: {sum(len(v) for v in moved.values())} file(s)")
    if skipped:
        log_callback(f"Skipped {len(skipped)} file(s).")
    log_callback("Done. Your Downloads folder is organised!")


def undo_organize_downloads(log_callback, target_folder: Path = None):
    folder = target_folder or get_downloads_folder()
    if not folder.exists():
        log_callback(f"Folder not found: {folder}")
        return

    restored = 0
    for category in FILE_CATEGORIES:
        cat_dir = folder / category
        if not cat_dir.is_dir():
            continue
        for file in cat_dir.iterdir():
            if file.is_file():
                dest = folder / file.name
                if dest.exists():
                    stem, counter = file.stem, 1
                    while dest.exists():
                        dest = folder / f"{stem}_{counter}{file.suffix}"
                        counter += 1
                shutil.move(str(file), str(dest))
                restored += 1
        try:
            cat_dir.rmdir()
        except Exception:
            pass

    if restored:
        log_callback(f"Restored {restored} file(s) back to Downloads/")
    else:
        log_callback("Nothing to undo — no organised sub-folders found.")


# ─────────────────────────────────────────────
# T2 EXTRA FEATURES
# ─────────────────────────────────────────────

def collect_by_type(ext_filter: str, dest_name: str, log_callback, source_folder: Path = None):
    folder = source_folder or get_downloads_folder()
    if not folder.exists():
        log_callback(f"Folder not found: {folder}")
        return
    dest_dir = folder / dest_name
    dest_dir.mkdir(exist_ok=True)
    matches = list(folder.rglob(f"*{ext_filter}"))
    if not matches:
        log_callback(f"No {ext_filter} files found under {folder.name}/")
        return
    log_callback(f"Found {len(matches)} {ext_filter} file(s). Copying to {dest_name}/…")
    copied = 0
    for src in matches:
        if src.parent == dest_dir:
            continue
        dst = dest_dir / src.name
        counter = 1
        while dst.exists():
            dst = dest_dir / f"{src.stem}_{counter}{src.suffix}"
            counter += 1
        shutil.copy2(str(src), str(dst))
        copied += 1
    log_callback(f"Copied {copied} {ext_filter} file(s) → {dest_dir}")


def search_files(keyword: str, log_callback, source_folder: Path = None):
    folder = source_folder or get_downloads_folder()
    if not folder.exists():
        log_callback(f"Folder not found: {folder}")
        return
    kw = keyword.lower().strip()
    if not kw:
        log_callback("No keyword provided.")
        return
    log_callback(f"Searching for '{keyword}' in {folder.name}/…")
    file_matches   = [f for f in folder.rglob("*") if f.is_file() and kw in f.name.lower()]
    folder_matches = [f for f in folder.rglob("*") if f.is_dir()  and kw in f.name.lower()]
    if not file_matches and not folder_matches:
        log_callback(f"No results for '{keyword}'.")
        return
    log_callback(f"Found {len(file_matches)} file(s) and {len(folder_matches)} folder(s):")
    for f in folder_matches[:15]:
        log_callback(f"  📁 {f.relative_to(folder)}/")
    for f in file_matches[:30]:
        log_callback(f"  📄 {f.relative_to(folder)}  ({f.stat().st_size/1024:.1f} KB)")
    total = len(file_matches) + len(folder_matches)
    if total > 45:
        log_callback(f"  … and {total - 45} more.")


def _send_to_trash(path: Path) -> bool:
    try:
        import send2trash
        send2trash.send2trash(str(path))
        return True
    except Exception:
        return False


def _md5_file(fpath: Path, chunk_size: int = 65536):
    h = hashlib.md5()
    try:
        with open(fpath, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
    except (OSError, PermissionError):
        return None


def _iter_downloads_files(folder: Path):
    for f in folder.iterdir():
        if f.is_file():
            yield f
    for sub in folder.iterdir():
        if not sub.is_dir() or sub.name in SKIP_FOLDERS:
            continue
        for f in sub.iterdir():
            if f.is_file():
                yield f


def delete_duplicates(log_callback, target_folder: Path = None):
    folder = target_folder or get_downloads_folder()
    if not folder.exists():
        log_callback(f"Folder not found: {folder}")
        return

    try:
        import send2trash  # noqa: F401
    except ImportError:
        log_callback("⚠  'send2trash' not installed. Run: pip install send2trash")
        return

    log_callback(f"Scanning {folder.name}/ (root + 1 level deep)…")
    all_files = list(_iter_downloads_files(folder))
    total = len(all_files)
    if total == 0:
        log_callback("No files found.")
        return

    log_callback(f"Checking {total} file(s) for duplicates…")
    hash_map: dict[str, Path] = {}
    duplicates: list[tuple[Path, int]] = []
    skipped = 0

    for i, fpath in enumerate(all_files, 1):
        if i % 50 == 0 or i == total:
            log_callback(f"  Progress: {i}/{total}")
        md5 = _md5_file(fpath)
        if md5 is None:
            skipped += 1
            continue
        if md5 in hash_map:
            try:
                duplicates.append((fpath, fpath.stat().st_size))
            except OSError:
                skipped += 1
        else:
            hash_map[md5] = fpath

    if skipped:
        log_callback(f"  Skipped {skipped} unreadable file(s).")
    if not duplicates:
        log_callback("✅ No duplicates found. You're clean!")
        return

    log_callback(f"Found {len(duplicates)} duplicate(s) → sending to Recycle Bin…")
    freed = trashed = 0
    for dup, size in duplicates:
        if _send_to_trash(dup):
            freed += size
            trashed += 1
            log_callback(f"  ♻  {dup.name}")
        else:
            log_callback(f"  ⚠  Skipped: {dup.name}")
    log_callback(f"✅ Done. {trashed} removed  |  {freed/(1024*1024):.2f} MB freed.")
    log_callback("Files are in Recycle Bin — recoverable if needed.")


def find_old_files(months: int, log_callback, result_callback, target_folder: Path = None):
    folder = target_folder or get_downloads_folder()
    if not folder.exists():
        log_callback(f"Folder not found: {folder}")
        return

    cutoff = time.time() - (months * 30.44 * 24 * 3600)
    log_callback(f"Scanning for files untouched for {months}+ month(s)…")

    results = []
    all_files = list(_iter_downloads_files(folder))

    for fpath in all_files:
        try:
            stat = fpath.stat()
            last_touched = max(stat.st_mtime, stat.st_atime)
            if last_touched < cutoff:
                age_months = (time.time() - last_touched) / (30.44 * 24 * 3600)
                results.append({
                    "path":       fpath,
                    "name":       fpath.name,
                    "rel":        str(fpath.relative_to(folder)),
                    "size_kb":    stat.st_size / 1024,
                    "months_old": age_months,
                })
        except Exception:
            continue

    if not results:
        log_callback(f"✅ No files older than {months} month(s). You're clean!")
        return

    results.sort(key=lambda x: x["months_old"], reverse=True)
    log_callback(f"Found {len(results)} file(s) untouched for {months}+ month(s):")
    result_callback(results)


def find_largest_files(top_n: int, log_callback, result_callback, target_folder: Path = None):
    folder = target_folder or get_downloads_folder()
    if not folder.exists():
        log_callback(f"Folder not found: {folder}")
        return

    log_callback(f"Scanning for top {top_n} largest files…")
    all_files = list(_iter_downloads_files(folder))
    if not all_files:
        log_callback("No files found.")
        return

    sized = []
    for fpath in all_files:
        try:
            size = fpath.stat().st_size
            sized.append({
                "path":    fpath,
                "name":    fpath.name,
                "rel":     str(fpath.relative_to(folder)),
                "size_kb": size / 1024,
                "size_mb": size / (1024 * 1024),
            })
        except Exception:
            continue

    sized.sort(key=lambda x: x["size_kb"], reverse=True)
    top = sized[:top_n]
    log_callback(f"Top {len(top)} largest files in Downloads/:")
    result_callback(top)


def do_rename_file(fpath: Path, new_name: str, log_callback):
    dest = fpath.parent / new_name
    if dest.exists():
        log_callback(f"⚠ '{new_name}' already exists. Skipped.")
        return False
    try:
        fpath.rename(dest)
        log_callback(f"✏ Renamed: {fpath.name} → {new_name}")
        return True
    except Exception as e:
        log_callback(f"⚠ Could not rename {fpath.name}: {e}")
        return False


def do_delete_file(fpath: Path, log_callback):
    try:
        import send2trash
        send2trash.send2trash(str(fpath))
        log_callback(f"♻ Deleted: {fpath.name}")
        return True
    except ImportError:
        log_callback("⚠  'send2trash' not installed. Run: pip install send2trash")
        return False
    except Exception as e:
        log_callback(f"⚠ Could not delete {fpath.name}: {e}")
        return False


# ─────────────────────────────────────────────
# RESULT PANEL
# ─────────────────────────────────────────────

class ResultPanel(ctk.CTkScrollableFrame):
    ROW_BG       = "#1A1A24"
    ROW_BG_ALT   = "#16161E"
    BTN_DELETE   = "#E53935"
    BTN_RENAME   = "#F59E0B"
    BTN_CONFIRM  = "#7C5CFC"
    TEXT_PRIMARY = "#E8E6F0"
    TEXT_DIM     = "#6B6880"

    def __init__(self, parent, log_callback, **kwargs):
        super().__init__(parent, fg_color="#13131A", corner_radius=8, **kwargs)
        self._log  = log_callback
        self._rows = []

    def clear(self):
        for row in self._rows:
            try:
                row.destroy()
            except Exception:
                pass
        self._rows.clear()

    def show_file_results(self, results: list, mode: str):
        self.clear()
        hdr = ctk.CTkLabel(
            self,
            text=f"  {'File':<36} {'Size':>9}  {'Info':>12}",
            font=("Consolas", 10), text_color=self.TEXT_DIM, anchor="w",
        )
        hdr.pack(fill="x", padx=6, pady=(6, 2))
        self._rows.append(hdr)
        for i, item in enumerate(results):
            bg = self.ROW_BG if i % 2 == 0 else self.ROW_BG_ALT
            self._build_file_row(item, bg, mode)

    def _build_file_row(self, item: dict, bg: str, mode: str):
        row = ctk.CTkFrame(self, fg_color=bg, corner_radius=6)
        row.pack(fill="x", padx=6, pady=2)
        self._rows.append(row)

        ext  = Path(item["name"]).suffix.lower()
        icon = (
            "🖼" if ext in {".jpg",".jpeg",".png",".gif",".bmp",".svg",".webp"} else
            "🎬" if ext in {".mp4",".mkv",".avi",".mov"} else
            "🎵" if ext in {".mp3",".wav",".aac",".flac"} else
            "📦" if ext in {".zip",".rar",".7z",".tar",".gz"} else
            "⚙"  if ext in {".exe",".msi"} else
            "📄"
        )

        size_str = f"{item['size_kb']:.0f} KB" if item["size_kb"] < 1024 else f"{item['size_kb']/1024:.1f} MB"
        info_str = f"{item.get('months_old',0):.1f} mo" if mode == "old_files" else f"{item.get('size_mb', item['size_kb']/1024):.1f} MB"

        display = item["rel"]
        if len(display) > 28:
            display = "…" + display[-26:]

        # Top line: filename
        top = ctk.CTkFrame(row, fg_color="transparent")
        top.pack(fill="x", padx=8, pady=(6, 0))

        ctk.CTkLabel(
            top, text=f"{icon} {display}",
            font=("Consolas", 10), text_color=self.TEXT_PRIMARY,
            anchor="w",
        ).pack(side="left")

        ctk.CTkLabel(
            top, text=f"{size_str}  {info_str}",
            font=("Consolas", 10), text_color=self.TEXT_DIM,
            anchor="e",
        ).pack(side="right")

        # Bottom line: buttons
        bot = ctk.CTkFrame(row, fg_color="transparent")
        bot.pack(anchor="e", padx=8, pady=(2, 6))

        fpath = item["path"]

        ctk.CTkButton(bot, text="🗑 Delete", width=80, height=26, corner_radius=4,
                      fg_color=self.BTN_DELETE, hover_color="#FF6B6B",
                      text_color="white", font=("Consolas", 10, "bold"),
                      command=lambda p=fpath, r=row: self._delete_file(p, r)).pack(side="left", padx=(0, 6))

        ctk.CTkButton(bot, text="✏ Rename", width=80, height=26, corner_radius=4,
                      fg_color=self.BTN_RENAME, hover_color="#FBBF24",
                      text_color="white", font=("Consolas", 10, "bold"),
                      command=lambda p=fpath, r=row, n=item["name"]: self._inline_rename(p, r, n)).pack(side="left")

    def _inline_rename(self, fpath: Path, row: ctk.CTkFrame, current_name: str):
        for w in row.winfo_children():
            w.destroy()
        row.configure(height=42)

        inner = ctk.CTkFrame(row, fg_color="transparent")
        inner.pack(fill="x", padx=8, pady=4)

        entry = ctk.CTkEntry(inner, width=250, height=28,
                             fg_color="#1E1E2A", border_color="#F59E0B",
                             border_width=1, text_color="#E8E6F0", font=("Consolas", 11))
        entry.insert(0, current_name)
        entry.pack(side="left", padx=(0, 6))
        entry.focus()

        def confirm():
            new_name = entry.get().strip()
            if new_name and new_name != current_name:
                if do_rename_file(fpath, new_name, self._log):
                    row.destroy()
            else:
                row.destroy()

        ctk.CTkButton(inner, text="✓", width=30, height=28, corner_radius=4,
                      fg_color=self.BTN_CONFIRM, hover_color="#9B7FFF",
                      text_color="white", font=("Consolas", 12, "bold"),
                      command=confirm).pack(side="left", padx=2)

        ctk.CTkButton(inner, text="✕", width=26, height=28, corner_radius=4,
                      fg_color="#2A2A38", hover_color="#3A3A50",
                      text_color="#6B6880", font=("Consolas", 11),
                      command=row.destroy).pack(side="left", padx=2)

        entry.bind("<Return>", lambda e: confirm())
        entry.bind("<Escape>", lambda e: row.destroy())

    def _delete_file(self, fpath: Path, row: ctk.CTkFrame):
        if do_delete_file(fpath, self._log):
            row.destroy()


# ─────────────────────────────────────────────
# T3 — APP & WINDOW CONTROLLER
# ─────────────────────────────────────────────

def _press_keys(*keys):
    VK = {
        "vol_mute": 0xAD, "vol_up": 0xAF, "vol_down": 0xAE,
        "win": 0x5B, "ctrl": 0x11, "alt": 0x12, "shift": 0x10,
        "l": 0x4C, "d": 0x44, "prtsc": 0x2C, "escape": 0x1B,
    }
    user32 = ctypes.windll.user32
    KEYEVENTF_KEYUP = 0x0002
    codes = [VK[k] for k in keys if k in VK]
    for c in codes:
        user32.keybd_event(c, 0, 0, 0)
    time.sleep(0.05)
    for c in reversed(codes):
        user32.keybd_event(c, 0, KEYEVENTF_KEYUP, 0)


def t3_screenshot(log_callback):
    try:
        import PIL.ImageGrab as ImageGrab
    except ImportError:
        log_callback("⚠  Pillow not installed. Run: pip install Pillow")
        return
    desktop  = Path.home() / "Desktop"
    desktop.mkdir(exist_ok=True)
    filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    ImageGrab.grab().save(str(desktop / filename))
    log_callback(f"📸 Screenshot saved → Desktop/{filename}")


def t3_lock_screen(log_callback):
    ctypes.windll.user32.LockWorkStation()
    log_callback("🔒 Screen locked.")


def t3_sleep_pc(log_callback):
    log_callback("💤 Putting PC to sleep…")
    subprocess.Popen(["rundll32.exe", "powrprof.dll,SetSuspendState", "0", "1", "0"])


def t3_mute_toggle(log_callback):
    _press_keys("vol_mute")
    log_callback("🔇 Mute toggled.")


def t3_volume_up(log_callback):
    for _ in range(5):
        _press_keys("vol_up")
        time.sleep(0.02)
    log_callback("🔊 Volume up.")


def t3_volume_down(log_callback):
    for _ in range(5):
        _press_keys("vol_down")
        time.sleep(0.02)
    log_callback("🔉 Volume down.")


def t3_open_task_manager(log_callback):
    subprocess.Popen(["taskmgr.exe"])
    log_callback("📊 Task Manager opened.")


def t3_restart_explorer(log_callback):
    log_callback("🔄 Restarting Windows Explorer…")
    subprocess.call(["taskkill", "/f", "/im", "explorer.exe"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    subprocess.Popen(["explorer.exe"])
    log_callback("✅ Explorer restarted.")


def t3_close_app(app_name: str, log_callback):
    if not app_name.strip():
        log_callback("No app name provided.")
        return
    aliases = {
        "chrome": "chrome.exe", "firefox": "firefox.exe", "edge": "msedge.exe",
        "spotify": "Spotify.exe", "discord": "Discord.exe", "notepad": "notepad.exe",
        "explorer": "explorer.exe", "vlc": "vlc.exe", "teams": "Teams.exe",
        "zoom": "Zoom.exe", "slack": "slack.exe", "word": "WINWORD.EXE",
        "excel": "EXCEL.EXE", "powerpoint": "POWERPNT.EXE",
    }
    target = aliases.get(app_name.lower().strip(), app_name.strip())
    result = subprocess.call(["taskkill", "/f", "/im", target],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if result == 0:
        log_callback(f"❌ Closed {app_name}.")
    else:
        log_callback(f"⚠  Could not find '{app_name}' running.")


def parse_t3_subcommand(text: str) -> dict:
    lowered = text.lower().strip()
    if any(w in lowered for w in ["screenshot", "screen shot", "capture screen", "snap"]):
        return {"sub": "screenshot"}
    if any(w in lowered for w in ["lock", "lock screen", "lock pc", "lock computer"]):
        return {"sub": "lock"}
    if any(w in lowered for w in ["sleep", "sleep pc", "sleep computer", "hibernate"]):
        return {"sub": "sleep"}
    if any(w in lowered for w in ["mute", "unmute", "toggle mute", "silence"]):
        return {"sub": "mute"}
    if any(w in lowered for w in ["volume up", "vol up", "louder", "increase volume", "turn up"]):
        return {"sub": "volume_up"}
    if any(w in lowered for w in ["volume down", "vol down", "quieter", "decrease volume", "turn down", "lower volume"]):
        return {"sub": "volume_down"}
    if any(w in lowered for w in ["task manager", "taskmgr", "processes", "open task"]):
        return {"sub": "task_manager"}
    if any(w in lowered for w in ["restart explorer", "explorer crash", "fix taskbar", "reload explorer"]):
        return {"sub": "restart_explorer"}
    for trigger in ["close ", "kill ", "quit "]:
        if trigger in lowered:
            return {"sub": "close_app", "app": lowered.split(trigger)[-1].strip()}
    return {"sub": "unknown"}


def execute_t3(decision: dict, log_callback):
    sub = decision.get("sub", "unknown")
    if sub == "screenshot":         t3_screenshot(log_callback)
    elif sub == "lock":             t3_lock_screen(log_callback)
    elif sub == "sleep":            t3_sleep_pc(log_callback)
    elif sub == "mute":             t3_mute_toggle(log_callback)
    elif sub == "volume_up":        t3_volume_up(log_callback)
    elif sub == "volume_down":      t3_volume_down(log_callback)
    elif sub == "task_manager":     t3_open_task_manager(log_callback)
    elif sub == "restart_explorer": t3_restart_explorer(log_callback)
    elif sub == "close_app":        t3_close_app(decision.get("app", ""), log_callback)
    else:
        log_callback("T3 — didn't understand that command.")
        log_callback("Try: screenshot · lock · sleep · mute · volume up/down")
        log_callback("     task manager · restart explorer · close chrome")


# ─────────────────────────────────────────────
# CHROME HELPERS
# ─────────────────────────────────────────────

def get_screen_size():
    try:
        user32 = ctypes.windll.user32
        return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    except Exception:
        return 1600, 900


def _enum_windows():
    windows = []
    user32  = ctypes.windll.user32

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def callback(hwnd, lparam):
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            buf    = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            if buf.value:
                windows.append((hwnd, buf.value))
        return True

    user32.EnumWindows(callback, 0)
    return windows


def find_window_by_title(fragment):
    fl = fragment.lower()
    for hwnd, title in _enum_windows():
        if fl in title.lower():
            return hwnd, title
    return None, ""


def tile_window_by_title(fragment, x, y, width, height, log_callback, timeout_seconds=8):
    user32   = ctypes.windll.user32
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        hwnd, title = find_window_by_title(fragment)
        if hwnd:
            user32.ShowWindow(hwnd, 9)
            user32.SetForegroundWindow(hwnd)
            user32.MoveWindow(hwnd, x, y, width, height, True)
            log_callback(f"Tiled '{title}' → {x},{y}  {width}×{height}")
            return True
        time.sleep(0.3)
    log_callback(f"Could not find Chrome window with '{fragment}'.")
    return False


def find_chrome_executable():
    candidates = [
        shutil.which("chrome"),
        shutil.which("chrome.exe"),
        os.path.join(os.getenv("PROGRAMFILES",      ""), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.getenv("PROGRAMFILES(X86)", ""), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.getenv("LOCALAPPDATA",      ""), "Google", "Chrome", "Application", "chrome.exe"),
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return ""


def open_in_chrome(url, log_callback, title_fragment="", x=None, y=None, width=None, height=None):
    chrome_path = find_chrome_executable()
    if not chrome_path:
        raise RuntimeError("Chrome executable not found.")
    args = [
        chrome_path,
        f"--profile-directory={CHROME_PROFILE_NAME}",
        f"--remote-debugging-port={REMOTE_DEBUGGING_PORT}",
        "--new-window", url,
    ]
    if CHROME_USER_DATA_DIR:
        args.insert(1, f"--user-data-dir={CHROME_USER_DATA_DIR}")
    if x is not None and y is not None:
        args.insert(-1, f"--window-position={x},{y}")
    if width is not None and height is not None:
        args.insert(-1, f"--window-size={width},{height}")
    subprocess.Popen(args)
    log_callback(f"Opened Chrome → {url}")
    if title_fragment and None not in (x, y, width, height):
        tile_window_by_title(title_fragment, x, y, width, height, log_callback)


# ─────────────────────────────────────────────
# ROUTING
# ─────────────────────────────────────────────

def looks_like_domain(text):
    c = text.strip().lower()
    return "." in c and " " not in c


def is_explicit_open_command(text):
    l = text.lower().strip()
    return l.startswith("open ") or l.startswith("go to ") or l.startswith("visit ")


def seems_like_product_query(text):
    l = text.lower().strip()
    tokens = l.replace("-", " ").split()
    if any(w in l for w in ["buy ", "price", "cheapest", "order ", "add to cart", "purchase"]):
        return True
    return any(t in PRODUCT_HINTS for t in tokens)


def parse_t2_subcommand(text: str) -> dict:
    lowered = text.lower().strip()

    if any(w in lowered for w in ["undo", "restore", "revert", "put back"]):
        return {"sub": "undo"}

    if any(w in lowered for w in ["duplicate", "duplicates", "dupe", "identical", "same file", "delete copies"]):
        return {"sub": "duplicates"}

    if any(w in lowered for w in [
        "old files", "old file", "haven't touched", "not touched", "untouched",
        "unused", "stale", "older than", "not accessed", "months old", "months ago",
        "month old", "month ago", "haven't opened", "not opened",
    ]):
        return {"sub": "old_files"}

    if any(w in lowered for w in [
        "largest", "biggest", "large files", "big files",
        "heavy", "top 10", "top 5", "most space", "taking space", "disk space",
    ]):
        return {"sub": "largest"}

    if any(w in lowered for w in ["collect", "copy all", "gather all", "move all", "find all", "get all"]):
        for category, exts in FILE_CATEGORIES.items():
            for ext in exts:
                if ext.lstrip(".") in lowered or category.lower().rstrip("s") in lowered:
                    return {"sub": "collect", "ext": ext, "dest": category}
        return {"sub": "collect", "ext": ".pdf", "dest": "PDFs"}

    for trigger in ["search for", "search ", "find file", "look for", "locate"]:
        if trigger in lowered:
            keyword = lowered.split(trigger)[-1].strip()
            for noise in ["in downloads", "in my downloads", "file", "files"]:
                keyword = keyword.replace(noise, "").strip()
            if keyword:
                return {"sub": "search", "keyword": keyword}

    return {"sub": "organize"}


def heuristic_route(user_input):
    lowered    = user_input.lower().strip()
    normalized = lowered
    for prefix in ["open ", "search ", "go to ", "visit ", "find "]:
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):].strip()
            break

    t3_triggers = [
        "screenshot", "lock screen", "lock pc", "sleep pc", "sleep computer",
        "mute", "unmute", "volume up", "volume down", "vol up", "vol down",
        "task manager", "taskmgr", "restart explorer", "close chrome",
        "close spotify", "close firefox", "close edge", "close discord",
        "close ", "kill ", "louder", "quieter", "turn up", "turn down",
        "lock computer", "hibernate", "snap screen",
    ]
    if any(t in lowered for t in t3_triggers):
        sub = parse_t3_subcommand(lowered)
        return {"action": "window_control", **sub, "router_source": "heuristic"}

    t2_triggers = [
        "organise", "organize", "sort my downloads", "clean downloads",
        "undo organize", "restore files", "duplicate", "identical",
        "old files", "old file", "largest", "biggest", "collect all", "search for",
    ]
    if any(w in lowered for w in t2_triggers):
        sub = parse_t2_subcommand(lowered)
        return {"action": "file_organize", **sub, "router_source": "heuristic"}

    if looks_like_domain(normalized) or normalized.startswith("www "):
        return {"action": "website_open", "site_name": normalized.replace("www ", "").strip(), "router_source": "heuristic"}

    if is_explicit_open_command(lowered):
        site_guess = lowered
        for prefix in ["open ", "go to ", "visit "]:
            if site_guess.startswith(prefix):
                site_guess = site_guess[len(prefix):].strip()
                break
        return {"action": "website_open", "site_name": site_guess, "router_source": "heuristic"}

    if seems_like_product_query(normalized):
        return {"action": "delivery_search", "query": normalized, "sites": ["amazon", "flipkart"], "router_source": "heuristic"}

    return {"action": "web_search", "query": normalized or lowered, "router_source": "heuristic"}


def get_decision(user_input):
    system_prompt = """
You are the intent router for an AI Chief of Staff.
Classify the user's request into exactly one action and return strict raw JSON only.

Actions:
1. "delivery_search" — buying/shopping → open Amazon & Flipkart.
   Return: {"action":"delivery_search","query":"...","sites":["amazon","flipkart"]}

2. "website_open" — open a website.
   Return: {"action":"website_open","site_name":"..."}

3. "web_search" — general Google search.
   Return: {"action":"web_search","query":"..."}

4. "file_organize" — anything about Downloads folder.
   Return: {"action":"file_organize","sub":"..."}
   sub values: organize, undo, duplicates, old_files, largest, collect, search

5. "window_control" — system/app control.
   Return: {"action":"window_control","sub":"...","app":"..."}
   sub values: screenshot, lock, sleep, mute, volume_up, volume_down, task_manager, restart_explorer, close_app

Examples:
{"action":"file_organize","sub":"organize"}
{"action":"file_organize","sub":"undo"}
{"action":"file_organize","sub":"duplicates"}
{"action":"file_organize","sub":"old_files"}
{"action":"file_organize","sub":"largest"}
{"action":"window_control","sub":"screenshot"}
{"action":"window_control","sub":"close_app","app":"chrome"}
{"action":"delivery_search","query":"sneakers","sites":["amazon","flipkart"]}
{"action":"website_open","site_name":"youtube"}
{"action":"web_search","query":"python tutorials"}
""".strip()

    if not GEMINI_MODEL:
        return heuristic_route(user_input)

    try:
        response = GEMINI_MODEL.generate_content(
            f"{system_prompt}\n\nCommand: {user_input}",
            generation_config={"temperature": 0, "response_mime_type": "application/json"},
        )
        start = response.text.find("{")
        end   = response.text.rfind("}")
        if start == -1 or end == -1:
            raise ValueError("No JSON in response.")
        decision = json.loads(response.text[start:end + 1])
        decision["router_source"] = "gemini"
        return decision
    except Exception as exc:
        fallback = heuristic_route(user_input)
        fallback["router_fallback_reason"] = str(exc)
        return fallback


# ─────────────────────────────────────────────
# TASK EXECUTORS
# ─────────────────────────────────────────────

def open_known_or_search_website(site_name, log_callback):
    cleaned = site_name.strip().lower()
    if not cleaned:
        log_callback("No website name provided.")
        return
    if cleaned in KNOWN_SITES:
        open_in_chrome(KNOWN_SITES[cleaned], log_callback, title_fragment=cleaned)
        return
    if "." in cleaned and not cleaned.startswith("http"):
        open_in_chrome(f"https://{cleaned}", log_callback, title_fragment=cleaned)
        return
    if cleaned.startswith("http://") or cleaned.startswith("https://"):
        open_in_chrome(cleaned, log_callback, title_fragment=cleaned)
        return
    open_in_chrome(f"https://www.google.com/search?q={quote(site_name)}", log_callback, title_fragment=site_name)


def execute_web_search(query, log_callback):
    if not query.strip():
        log_callback("No search query provided.")
        return
    open_in_chrome(f"https://www.google.com/search?q={quote(query)}", log_callback, title_fragment=query)


def execute_delivery_search(query, sites, log_callback):
    filtered = [s for s in sites if s in DELIVERY_SITES]
    if not filtered:
        log_callback("No supported delivery sites selected.")
        return
    sw, sh  = get_screen_size()
    win_w   = max(sw // len(filtered), 600)
    win_h   = max(sh - 120, 700)
    log_callback(f"Opening {', '.join(filtered)} side-by-side for '{query}'…")
    for i, site in enumerate(filtered):
        cfg = DELIVERY_SITES[site]
        url = cfg["search_url"].format(query=quote(query))
        open_in_chrome(url, log_callback, title_fragment=cfg["label"],
                       x=i * win_w, y=0, width=win_w, height=win_h)


# ─────────────────────────────────────────────
# FLOATING WIDGET UI
# ─────────────────────────────────────────────
WIDGET_W            = 420
WIDGET_H_COLLAPSED  = 52
WIDGET_H_EXPANDED   = 560

ACCENT       = "#7C5CFC"
ACCENT_HOVER = "#9B7FFF"
BG_DARK      = "#0E0E12"
BG_PANEL     = "#16161E"
BG_INPUT     = "#1E1E2A"
TEXT_PRIMARY = "#E8E6F0"
TEXT_DIM     = "#6B6880"
T1_COLOR     = "#3A8EFF"
T2_COLOR     = "#22C98A"
T3_COLOR     = "#FF7043"


class FloatingWidget(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.97)
        self.configure(fg_color=BG_DARK)

        self._expanded    = False
        self._drag_x      = 0
        self._drag_y      = 0
        self._active_task = None

        sw, sh = get_screen_size()
        x = sw - WIDGET_W - 24
        y = sh - WIDGET_H_COLLAPSED - 60
        self.geometry(f"{WIDGET_W}x{WIDGET_H_COLLAPSED}+{x}+{y}")

        self._build_ui()

    def _build_ui(self):
        self.header = ctk.CTkFrame(self, fg_color=BG_PANEL, corner_radius=12, height=52)
        self.header.pack(fill="x")
        self.header.pack_propagate(False)
        self.header.bind("<ButtonPress-1>", self._drag_start)
        self.header.bind("<B1-Motion>",     self._drag_move)

        lbl = ctk.CTkLabel(self.header, text="⚡ Chief of Staff",
                            font=("Consolas", 13, "bold"), text_color=TEXT_PRIMARY, cursor="fleur")
        lbl.pack(side="left", padx=14)
        lbl.bind("<ButtonPress-1>", self._drag_start)
        lbl.bind("<B1-Motion>",     self._drag_move)

        bf = ctk.CTkFrame(self.header, fg_color="transparent")
        bf.pack(side="left", padx=6)
        self._task_btn(bf, "T1", T1_COLOR, lambda: self._select_task("T1")).pack(side="left", padx=3)
        self._task_btn(bf, "T2", T2_COLOR, lambda: self._select_task("T2")).pack(side="left", padx=3)
        self._task_btn(bf, "T3", T3_COLOR, lambda: self._select_task("T3")).pack(side="left", padx=3)

        self.toggle_btn = ctk.CTkButton(
            self.header, text="▲", width=32, height=28,
            fg_color="transparent", hover_color=BG_INPUT,
            text_color=TEXT_DIM, font=("Consolas", 11),
            command=self._toggle_expand,
        )
        self.toggle_btn.pack(side="right", padx=6)

        ctk.CTkButton(
            self.header, text="✕", width=28, height=28,
            fg_color="transparent", hover_color="#3A0010",
            text_color=TEXT_DIM, font=("Consolas", 11),
            command=self.destroy,
        ).pack(side="right", padx=2)

        self.body = ctk.CTkFrame(self, fg_color=BG_DARK, corner_radius=0)

        self.hint_label = ctk.CTkLabel(
            self.body, text="Select T1 / T2 / T3 or just type a command",
            font=("Consolas", 11), text_color=TEXT_DIM, wraplength=390, justify="left",
        )
        self.hint_label.pack(anchor="w", padx=14, pady=(10, 4))

        input_row = ctk.CTkFrame(self.body, fg_color="transparent")
        input_row.pack(fill="x", padx=10, pady=(0, 6))

        self.input_box = ctk.CTkEntry(
            input_row, height=36, fg_color=BG_INPUT, border_color=ACCENT,
            border_width=1, text_color=TEXT_PRIMARY, font=("Consolas", 12),
            placeholder_text="Type a command…",
        )
        self.input_box.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.input_box.bind("<Return>", self._on_enter)

        ctk.CTkButton(
            input_row, text="→", width=40, height=36,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            text_color="white", font=("Consolas", 14, "bold"),
            command=self._on_enter,
        ).pack(side="right")

        self.log_box = ctk.CTkTextbox(
            self.body, height=150, fg_color=BG_INPUT,
            text_color=TEXT_PRIMARY, font=("Consolas", 11),
            border_width=0, state="disabled",
        )
        self.log_box.pack(fill="x", padx=10, pady=(0, 4))

        self.result_panel = ResultPanel(
            self.body, log_callback=self._log, height=220,
        )

        router_mode = "Gemini" if GEMINI_MODEL else "Heuristic"
        self._log(f"Ready  |  Router: {router_mode}")
        self._log("─" * 44)

    def _task_btn(self, parent, label, color, command):
        return ctk.CTkButton(
            parent, text=label, width=38, height=28,
            fg_color=color, hover_color=color,
            text_color="white", font=("Consolas", 11, "bold"),
            corner_radius=6, command=command,
        )

    def _drag_start(self, event):
        self._drag_x = event.x_root - self.winfo_x()
        self._drag_y = event.y_root - self.winfo_y()

    def _drag_move(self, event):
        self.geometry(f"+{event.x_root - self._drag_x}+{event.y_root - self._drag_y}")

    def _toggle_expand(self):
        self._expanded = not self._expanded
        if self._expanded:
            self.geometry(f"{WIDGET_W}x{WIDGET_H_EXPANDED}")
            self.body.pack(fill="both", expand=True)
            self.toggle_btn.configure(text="▼")
            self.input_box.focus()
        else:
            self.body.pack_forget()
            self.geometry(f"{WIDGET_W}x{WIDGET_H_COLLAPSED}")
            self.toggle_btn.configure(text="▲")

    def _select_task(self, task_id):
        self._active_task = task_id
        hints = {
            "T1": "T1 — Website / Search  |  'open youtube'  'search sneakers'",
            "T2": "T2 — Files  |  organise · undo · delete duplicates · old files 6 months · largest files",
            "T3": "T3 — System  |  screenshot · lock · sleep · mute · volume up/down · task manager · close chrome",
        }
        self.hint_label.configure(text=hints.get(task_id, ""))
        if not self._expanded:
            self._toggle_expand()
        self.input_box.focus()

    def _log(self, msg):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", msg + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _show_result_panel(self):
        if not self.result_panel.winfo_ismapped():
            self.result_panel.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def _hide_result_panel(self):
        self.result_panel.pack_forget()
        self.result_panel.clear()

    def _on_enter(self, event=None):
        text = self.input_box.get().strip()
        if not text:
            return
        self.input_box.delete(0, "end")
        self._log(f"\n> {text}")
        if not self._expanded:
            self._toggle_expand()
        threading.Thread(target=self._run_agent, args=(text,), daemon=True).start()

    def _run_agent(self, user_text):

        if self._active_task == "T3":
            sub = parse_t3_subcommand(user_text)
            if sub.get("sub") != "unknown":
                decision = {"action": "window_control", **sub, "router_source": "T3_local"}
            else:
                decision = get_decision(user_text)
                if decision.get("action") != "window_control":
                    decision = {"action": "window_control", "sub": "unknown", "router_source": "T3_fallback"}

        elif self._active_task == "T2":
            sub_decision = parse_t2_subcommand(user_text)
            decision = {"action": "file_organize", **sub_decision, "router_source": "T2_local"}

        else:
            self._log("Thinking…")
            decision = get_decision(user_text)

        self._log(f"→ {decision.get('action')}  [{decision.get('router_source', '?')}]")
        action = decision.get("action")

        if action == "website_open":
            self._hide_result_panel()
            open_known_or_search_website(decision.get("site_name", ""), self._log)

        elif action == "delivery_search":
            self._hide_result_panel()
            execute_delivery_search(
                query=decision.get("query", user_text),
                sites=decision.get("sites", ["amazon", "flipkart"]),
                log_callback=self._log,
            )

        elif action == "web_search":
            self._hide_result_panel()
            execute_web_search(decision.get("query", user_text), self._log)

        elif action == "file_organize":
            sub = decision.get("sub", "organize")

            if sub == "organize":
                self._hide_result_panel()
                organize_downloads(self._log)

            elif sub == "undo":
                self._hide_result_panel()
                undo_organize_downloads(self._log)

            elif sub == "duplicates":
                self._hide_result_panel()
                delete_duplicates(self._log)

            elif sub == "old_files":
                m      = re.search(r"(\d+)", user_text)
                months = int(m.group(1)) if m else 6

                def on_old_results(results):
                    self._show_result_panel()
                    self.result_panel.show_file_results(results, mode="old_files")

                self._log(f"Looking for files untouched for {months}+ month(s)…")
                find_old_files(months, self._log, on_old_results)

            elif sub == "largest":
                m     = re.search(r"(\d+)", user_text)
                top_n = int(m.group(1)) if m else 10

                def on_largest_results(results):
                    self._show_result_panel()
                    self.result_panel.show_file_results(results, mode="largest")

                self._log(f"Finding top {top_n} largest files…")
                find_largest_files(top_n, self._log, on_largest_results)

            elif sub == "collect":
                self._hide_result_panel()
                collect_by_type(
                    ext_filter=decision.get("ext", ".pdf"),
                    dest_name=decision.get("dest", "Collected"),
                    log_callback=self._log,
                )

            elif sub == "search":
                self._hide_result_panel()
                search_files(
                    keyword=decision.get("keyword", user_text),
                    log_callback=self._log,
                )

            else:
                self._log(f"Unknown T2 command: '{sub}' — try rephrasing.")

        elif action == "window_control":
            self._hide_result_panel()
            execute_t3(decision, self._log)

        else:
            self._log("Unsupported action — try rephrasing.")


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    app = FloatingWidget()
    app.mainloop()

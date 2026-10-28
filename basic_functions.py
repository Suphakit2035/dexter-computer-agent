"""Common Windows desktop and file operations for Dexter."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import List

import mouse_event as mouse


def open_program(name: str) -> str:
    """Open an app through the Windows Start search using Win, type, Enter."""
    name = name.strip()
    if not name:
        raise ValueError("กรุณาระบุชื่อโปรแกรม")
    mouse.press_key("win")
    time.sleep(0.4)
    mouse.type_text(name)
    time.sleep(0.4)
    mouse.press_key("enter")
    return f"ส่งคำสั่งเปิดโปรแกรม '{name}' ผ่าน Start search แล้ว; ตรวจภาพหน้าจอเพื่อยืนยันว่าเปิดสำเร็จ"


def minimize_all() -> str:
    mouse.hotkey("win", "m")
    return "ส่งคำสั่งย่อหน้าต่างทั้งหมดแล้ว"


def restore_minimized() -> str:
    mouse.hotkey("win", "shift", "m")
    return "ส่งคำสั่งคืนหน้าต่างที่ย่อไว้แล้ว"


def switch_window() -> str:
    mouse.hotkey("alt", "tab")
    return "สลับไปยังหน้าต่างก่อนหน้าแล้ว"


def close_active_window() -> str:
    mouse.hotkey("alt", "f4")
    return "ส่งคำสั่งปิดหน้าต่างที่กำลังใช้งานอยู่แล้ว"


def open_file(path: str) -> str:
    target = Path(path).expanduser()
    if not target.exists():
        raise FileNotFoundError(f"ไม่พบไฟล์หรือโฟลเดอร์: {target}")
    if not target.is_file() and not target.is_dir():
        raise ValueError(f"เปิดรายการนี้ไม่ได้: {target}")
    if not hasattr(os, "startfile"):
        raise RuntimeError("การเปิดไฟล์ด้วยแอปเริ่มต้นรองรับเฉพาะ Windows")
    os.startfile(str(target.resolve()))
    return f"สั่งเปิดด้วยแอปเริ่มต้นแล้ว: {target.resolve()}"


def search_files(name: str, root: str = "", limit: int = 20) -> str:
    """Search file and folder names under root (defaults to the user's home)."""
    query = name.strip().casefold()
    if not query:
        raise ValueError("กรุณาระบุชื่อหรือส่วนหนึ่งของชื่อไฟล์")
    base = Path(root).expanduser() if root.strip() else Path.home()
    if not base.exists() or not base.is_dir():
        raise NotADirectoryError(f"ไม่พบโฟลเดอร์สำหรับค้นหา: {base}")

    ignored = {".git", "node_modules", "__pycache__", "venv", ".venv", "appdata", "$recycle.bin"}
    matches: List[str] = []
    visited = 0
    max_entries = 200_000
    for current, dirs, files in os.walk(base, onerror=lambda _error: None):
        dirs[:] = [d for d in dirs if d.casefold() not in ignored and not d.startswith(".")]
        for item in [*dirs, *files]:
            visited += 1
            if query in item.casefold():
                matches.append(str(Path(current, item)))
                if len(matches) >= max(1, min(int(limit), 50)):
                    break
            if visited >= max_entries:
                break
        if len(matches) >= max(1, min(int(limit), 50)) or visited >= max_entries:
            break

    if not matches:
        suffix = " (หยุดเมื่อครบขีดจำกัดการค้นหา)" if visited >= max_entries else ""
        return f"ไม่พบรายการที่มีชื่อ '{name}' ภายใต้ {base}{suffix}"
    lines = [f"พบ {len(matches)} รายการที่ตรงกับ '{name}' ภายใต้ {base}:", *matches]
    if visited >= max_entries:
        lines.append("หยุดค้นหาเมื่อครบขีดจำกัด 200,000 รายการ")
    return "\n".join(lines)

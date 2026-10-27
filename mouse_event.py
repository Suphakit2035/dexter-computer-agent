"""
โมดูลสำหรับควบคุมเมาส์ด้วย PyAutoGUI
ออกแบบสำหรับ Computer Agent ให้เรียกใช้ฟังก์ชันการทำงานของเมาส์ได้อย่างสะดวกและปลอดภัย
"""

import sys
from typing import Tuple, Optional
import pyautogui

# ตั้งค่า stdout/stderr ให้รองรับ UTF-8 บน Windows console
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# การตั้งค่าความปลอดภัยเริ่มต้นของ PyAutoGUI
# FAILSAFE: เมื่อลากเมาส์ไปที่มุมซ้ายบนสุดของจอ (0, 0) จะหยุดการทำงานทันทีเพื่อความปลอดภัย
pyautogui.FAILSAFE = True
# PAUSE: ระยะเวลาหน่วงสั้นๆ หลังจบแต่ละคำสั่ง (วินาที)
pyautogui.PAUSE = 0.1


# ==============================================================================
# ฟังก์ชันข้อมูลหน้าจอและพิกัด (Screen & Coordinate Functions)
# ==============================================================================

def get_screen_size() -> Tuple[int, int]:
    """
    คืนค่าขนาดหน้าจอหลัก (ความกว้าง, ความสูง) เป็นพิกเซล เช่น (1920, 1080)
    """
    size = pyautogui.size()
    return size.width, size.height


def get_position() -> Tuple[int, int]:
    """
    คืนค่าพิกัดปัจจุบันของเคอร์เซอร์เมาส์ (x, y)
    """
    pos = pyautogui.position()
    return pos.x, pos.y


def is_on_screen(x: int, y: int) -> bool:
    """
    ตรวจสอบว่าพิกัด (x, y) อยู่ภายในขอบเขตหน้าจอหรือไม่
    """
    return pyautogui.onScreen(x, y)


def set_pause(seconds: float) -> None:
    """
    ตั้งค่าระยะเวลาหน่วงระหว่างการสั่งการเมาส์แต่ละคำสั่ง (วินาที)
    """
    pyautogui.PAUSE = max(0.0, seconds)


def set_failsafe(enabled: bool) -> None:
    """
    เปิด/ปิดระบบความปลอดภัย FailSafe (หยุดโปรแกรมเมื่อเลื่อนเมาส์ไปมุมซ้ายบนสุด)
    """
    pyautogui.FAILSAFE = enabled


# ==============================================================================
# ฟังก์ชันการเคลื่อนที่ของเมาส์ (Movement Functions)
# ==============================================================================

def move_to(x: int, y: int, duration: float = 0.2) -> None:
    """
    เลื่อนเคอร์เซอร์เมาส์ไปยังพิกัดเป้าหมาย (x, y)

    Parameters:
        x (int): พิกัดแนวนอน
        y (int): พิกัดแนวตั้ง
        duration (float): ระยะเวลาในการเคลื่อนที่ (วินาที) ค่าเริ่มต้น 0.2
    """
    pyautogui.moveTo(x, y, duration=duration)


def move_rel(x_offset: int, y_offset: int, duration: float = 0.2) -> None:
    """
    เลื่อนเคอร์เซอร์เมาส์สัมพัทธ์จากตำแหน่งปัจจุบัน

    Parameters:
        x_offset (int): ขยับแกน x (บวกไปขวา, ลบไปซ้าย)
        y_offset (int): ขยับแกน y (บวกเลื่อนลง, ลบเลื่อนขึ้น)
        duration (float): ระยะเวลาในการเคลื่อนที่ (วินาที)
    """
    pyautogui.moveRel(x_offset, y_offset, duration=duration)


# ==============================================================================
# ฟังก์ชันการคลิกเมาส์ (Clicking Functions)
# ==============================================================================

def click(
    x: Optional[int] = None,
    y: Optional[int] = None,
    button: str = "left",
    clicks: int = 1,
    interval: float = 0.1,
) -> None:
    """
    คลิกเมาส์ (หากไม่ระบุ x, y จะคลิกที่ตำแหน่งปัจจุบัน)

    Parameters:
        x (int, optional): พิกัด x ที่ต้องการคลิก
        y (int, optional): พิกัด y ที่ต้องการคลิก
        button (str): ปุ่มที่ใช้คลิก ('left', 'middle', 'right')
        clicks (int): จำนวนครั้งที่คลิก
        interval (float): ระยะเวลาระหว่างการคลิกแต่ละครั้ง (กรณี clicks > 1)
    """
    pyautogui.click(x=x, y=y, clicks=clicks, interval=interval, button=button)


def double_click(
    x: Optional[int] = None,
    y: Optional[int] = None,
    button: str = "left",
) -> None:
    """
    ดับเบิลคลิกเมาส์ (หากไม่ระบุ x, y จะดับเบิลคลิกที่ตำแหน่งปัจจุบัน)

    Parameters:
        x (int, optional): พิกัด x
        y (int, optional): พิกัด y
        button (str): ปุ่มที่คลิก ('left', 'right')
    """
    pyautogui.doubleClick(x=x, y=y, button=button)


def triple_click(
    x: Optional[int] = None,
    y: Optional[int] = None,
    button: str = "left",
) -> None:
    """
    ทริปเปิลคลิก (คลิก 3 ครั้งติด มักใช้เลือกทั้งย่อหน้าหรือทั้งบรรทัด)

    Parameters:
        x (int, optional): พิกัด x
        y (int, optional): พิกัด y
        button (str): ปุ่มที่คลิก
    """
    pyautogui.tripleClick(x=x, y=y, button=button)


def right_click(x: Optional[int] = None, y: Optional[int] = None) -> None:
    """
    คลิกขวา (เปิดเมนู Context menu)
    """
    pyautogui.rightClick(x=x, y=y)


def middle_click(x: Optional[int] = None, y: Optional[int] = None) -> None:
    """
    คลิกปุ่มกลางของเมาส์ (Scroll wheel click)
    """
    pyautogui.middleClick(x=x, y=y)


# ==============================================================================
# ฟังก์ชันการกดค้าง ปล่อย และลากเมาส์ (Hold, Release & Drag Functions)
# ==============================================================================

def mouse_down(
    x: Optional[int] = None,
    y: Optional[int] = None,
    button: str = "left",
) -> None:
    """
    กดปุ่มเมาส์ค้างไว้ (ยังไม่ปล่อย)
    """
    pyautogui.mouseDown(x=x, y=y, button=button)


def mouse_up(
    x: Optional[int] = None,
    y: Optional[int] = None,
    button: str = "left",
) -> None:
    """
    ปล่อยปุ่มเมาส์ที่กำลังกดค้างอยู่
    """
    pyautogui.mouseUp(x=x, y=y, button=button)


def drag_to(
    x: int,
    y: int,
    duration: float = 0.5,
    button: str = "left",
) -> None:
    """
    ลากเมาส์จากตำแหน่งปัจจุบันไปยังพิกัดเป้าหมาย (x, y)

    Parameters:
        x (int): พิกัดปลายทางแกน x
        y (int): พิกัดปลายทางแกน y
        duration (float): ระยะเวลาในการลาก (วินาที)
        button (str): ปุ่มที่กดค้างขณะลาก ('left', 'right')
    """
    pyautogui.dragTo(x, y, duration=duration, button=button)


def drag(
    start_x: int,
    start_y: int,
    end_x: int,
    end_y: int,
    duration: float = 0.5,
    button: str = "left",
) -> None:
    """
    ลากเมาส์จากจุดเริ่มต้น (start_x, start_y) ไปยังจุดปลายทาง (end_x, end_y)

    Parameters:
        start_x (int): จุดเริ่มต้นแกน x
        start_y (int): จุดเริ่มต้นแกน y
        end_x (int): จุดสิ้นสุดแกน x
        end_y (int): จุดสิ้นสุดแกน y
        duration (float): ระยะเวลาในการลาก (วินาที)
        button (str): ปุ่มที่ใช้ลาก ('left', 'right')
    """
    pyautogui.moveTo(start_x, start_y, duration=0.1)
    pyautogui.dragTo(end_x, end_y, duration=duration, button=button)


# ==============================================================================
# ฟังก์ชันการเลื่อนลูกกลิ้งเมาส์ (Scrolling Functions)
# ==============================================================================

def scroll(
    clicks: int,
    x: Optional[int] = None,
    y: Optional[int] = None,
) -> None:
    """
    เลื่อนลูกกลิ้งเมาส์ในแนวตั้ง

    Parameters:
        clicks (int): ค่าบวก = เลื่อนขึ้น (scroll up), ค่าลบ = เลื่อนลง (scroll down)
        x (int, optional): พิกัด x ที่จะไปเลื่อน
        y (int, optional): พิกัด y ที่จะไปเลื่อน
    """
    pyautogui.scroll(clicks, x=x, y=y)


def hscroll(
    clicks: int,
    x: Optional[int] = None,
    y: Optional[int] = None,
) -> None:
    """
    เลื่อนลูกกลิ้งเมาส์ในแนวนอน (Horizontal scroll)

    Parameters:
        clicks (int): ค่าบวก = เลื่อนไปขวา, ค่าลบ = เลื่อนไปซ้าย
        x (int, optional): พิกัด x
        y (int, optional): พิกัด y
    """
    pyautogui.hscroll(clicks, x=x, y=y)


# ==============================================================================
# ฟังก์ชันการพิมพ์และกดคีย์บอร์ด (Keyboard Functions)
# ==============================================================================

import ctypes
from ctypes import wintypes
import time

class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_ulonglong),
    ]

class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_ulonglong),
    ]

class _HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]

class _INPUT(ctypes.Structure):
    class _INPUT_UNION(ctypes.Union):
        _fields_ = [
            ("mi", _MOUSEINPUT),
            ("ki", _KEYBDINPUT),
            ("hi", _HARDWAREINPUT),
        ]
    _anonymous_ = ("_u",)
    _fields_ = [("type", wintypes.DWORD), ("_u", _INPUT_UNION)]

_KEYEVENTF_UNICODE = 0x0004
_KEYEVENTF_KEYUP = 0x0002
_INPUT_KEYBOARD = 1


def _send_unicode_text(text: str, interval: float = 0.05) -> None:
    """
    พิมพ์ตัวอักษรโดยใช้ Windows Unicode SendInput
    ช่วยให้พิมพ์ได้ถูกต้อง 100% ทั้งภาษาไทยและอังกฤษ โดยไม่ขึ้นกับว่าแป้นพิมพ์กำลังเปิดโหมดภาษา TH หรือ EN อยู่
    """
    u32 = ctypes.windll.user32
    for ch in text:
        code = ord(ch)
        # Key down
        down = _INPUT(type=_INPUT_KEYBOARD)
        down.ki = _KEYBDINPUT(wVk=0, wScan=code, dwFlags=_KEYEVENTF_UNICODE, time=0, dwExtraInfo=0)
        # Key up
        up = _INPUT(type=_INPUT_KEYBOARD)
        up.ki = _KEYBDINPUT(wVk=0, wScan=code, dwFlags=_KEYEVENTF_UNICODE | _KEYEVENTF_KEYUP, time=0, dwExtraInfo=0)

        events = (_INPUT * 2)(down, up)
        u32.SendInput(2, ctypes.byref(events), ctypes.sizeof(_INPUT))
        if interval > 0:
            time.sleep(interval)


def press_key(key: str) -> None:
    """
    กดปุ่มคีย์บอร์ด 1 ครั้ง เช่น 'win', 'enter', 'esc', 'space', 'backspace'
    """
    pyautogui.press(key)
    # หน่วงเวลาเล็กน้อยหลังกดปุ่มระบบ เช่น win เพื่อให้ UI ขยายและพร้อมรับคำสั่ง
    if key.lower() in ("win", "windows", "tab", "enter"):
        time.sleep(0.3)


def type_text(text: str, interval: float = 0.04) -> None:
    """
    พิมพ์ข้อความอย่างแม่นยำ ไม่ตกหล่น และรองรับทั้งภาษาไทยและอังกฤษ
    แม้ระบบแป้นพิมพ์จะอยู่ในภาษาไทย (TH) ก็ตาม
    """
    try:
        _send_unicode_text(text, interval=interval)
    except Exception:
        pyautogui.write(text, interval=interval)


def hotkey(*keys: str) -> None:
    """
    กดปุ่มคีย์ลัดผสม เช่น hotkey('ctrl', 'c'), hotkey('win', 'r')
    """
    pyautogui.hotkey(*keys)
    time.sleep(0.2)


# ==============================================================================
# ตัวอย่างการทดสอบใช้งาน (เมื่อรันไฟล์นี้โดยตรง)
# ==============================================================================
if __name__ == "__main__":
    w, h = get_screen_size()
    cur_x, cur_y = get_position()
    print("=== ทดสอบโมดูล mouse_event.py ===")
    print(f"ขนาดหน้าจอ: {w} x {h} พิกเซล")
    print(f"ตำแหน่งเมาส์ปัจจุบัน: X={cur_x}, Y={cur_y}")
    print("\nฟังก์ชันที่พร้อมใช้งาน:")
    print(" - move_to(x, y, duration=0.2)")
    print(" - move_rel(x_offset, y_offset)")
    print(" - click(x, y, button='left')")
    print(" - double_click(x, y)")
    print(" - triple_click(x, y)")
    print(" - right_click(x, y)")
    print(" - middle_click(x, y)")
    print(" - drag(start_x, start_y, end_x, end_y)")
    print(" - drag_to(x, y)")
    print(" - mouse_down(button='left'), mouse_up(button='left')")
    print(" - scroll(clicks), hscroll(clicks)")
    print(" - get_position(), get_screen_size(), is_on_screen(x, y)")
    print("\n* ข้อควรระวัง: หากต้องการหยุดฉุกเฉิน ให้เลื่อนเมาส์ไปที่มุมซ้ายบนสุดของจอ (0, 0)")


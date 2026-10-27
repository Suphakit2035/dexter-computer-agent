"""
โมดูลสำหรับจับภาพหน้าจอ (Screen Capture)
ใช้สำหรับบันทึกภาพหน้าจอปัจจุบันเพื่อส่งให้ AI วิเคราะห์
"""

import sys
from pathlib import Path
from typing import Optional, Tuple, Union
from PIL import Image, ImageGrab
import pyautogui

# ตั้งค่า stdout/stderr ให้รองรับ UTF-8 บน Windows console
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def get_screen_resolution() -> Tuple[int, int]:
    """
    คืนค่าความละเอียดของหน้าจอ (width, height)
    """
    size = pyautogui.size()
    return size.width, size.height


def capture_screen(
    save_path: Optional[Union[str, Path]] = "current_screen.jpg",
    all_screens: bool = False,
    quality: int = 70,
) -> Image.Image:
    """
    ถ่ายภาพหน้าจอทั้งหมดและบันทึกเป็นไฟล์ภาพ JPEG บีบอัด เพื่อให้ส่งผ่าน API ได้อย่างรวดเร็ว

    Parameters:
        save_path (str | Path, optional): พาธไฟล์ที่ต้องการบันทึกภาพ (ค่าเริ่มต้น: 'current_screen.jpg')
        all_screens (bool): ถ่ายทุกหน้าจอพร้อมกัน หรือไม่
        quality (int): คุณภาพของภาพ JPEG (1-100, ค่าเริ่มต้น 70 เพื่อขนาดไฟล์ที่เล็กและเร็ว)

    Returns:
        PIL.Image.Image: ภาพหน้าจอที่ถ่ายได้
    """
    screenshot = ImageGrab.grab(all_screens=all_screens).convert("RGB")

    if save_path:
        out_path = Path(save_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        screenshot.save(str(out_path), format="JPEG", quality=quality, optimize=True)

    return screenshot


def capture_region(
    bbox: Tuple[int, int, int, int],
    save_path: Optional[Union[str, Path]] = None,
) -> Image.Image:
    """
    ถ่ายภาพหน้าจอเฉพาะพื้นที่ที่กำหนด (Bounding Box)

    Parameters:
        bbox (tuple): (left, top, right, bottom)
        save_path (str | Path, optional): พาธไฟล์ที่ต้องการบันทึก

    Returns:
        PIL.Image.Image: ภาพเฉพาะส่วนที่ถูกตัดมา
    """
    screenshot = ImageGrab.grab(bbox=bbox)

    if save_path:
        out_path = Path(save_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        screenshot.convert("RGB").save(str(out_path), format="PNG")

    return screenshot


if __name__ == "__main__":
    w, h = get_screen_resolution()
    print(f"กำลังทดสอบถ่ายภาพหน้าจอ (ความละเอียด {w}x{h})...")
    test_path = "test_screenshot.png"
    img = capture_screen(test_path)
    print(f"ถ่ายภาพสำเร็จ ขนาดภาพ: {img.size}, บันทึกที่: {test_path}")


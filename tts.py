"""
โมดูลแปลงข้อความเป็นเสียงพูด (Text to Speech - TTS)
ใช้ edge-tts ร่วมกับ pygame เพื่อพูดโต้ตอบเป็นภาษาไทย
"""

import sys
import asyncio
import threading
from pathlib import Path
import edge_tts
import pygame

# ตั้งค่า stdout/stderr ให้รองรับ UTF-8 บน Windows console
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# กำหนดเสียงเริ่มต้น (th-TH-NiwatNeural หรือ th-TH-AcharaNeural)
DEFAULT_VOICE = "th-TH-NiwatNeural"
TEMP_AUDIO = "tts_response.mp3"


async def _generate_audio_file(
    text: str,
    output_file: str,
    voice: str = DEFAULT_VOICE,
    rate: str = "+0%",
    pitch: str = "+0Hz",
) -> None:
    """
    สร้างไฟล์เสียงด้วย edge-tts
    """
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    await communicate.save(output_file)


def _run_tts_generation(text: str, output_file: str, voice: str) -> None:
    """Run edge-tts safely even when speak() is called from an asyncio loop."""
    coroutine = _generate_audio_file(text, output_file, voice=voice)
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(coroutine)
        return

    errors: list[BaseException] = []

    def run_in_thread() -> None:
        try:
            asyncio.run(coroutine)
        except BaseException as exc:
            errors.append(exc)

    worker = threading.Thread(target=run_in_thread, name="dexter-tts", daemon=True)
    worker.start()
    worker.join()
    if errors:
        raise errors[0]


def speak(
    text: str,
    voice: str = DEFAULT_VOICE,
    wait: bool = True,
    temp_file: str = TEMP_AUDIO,
) -> None:
    """
    ฟังก์ชันพูดข้อความออกลำโพง

    Parameters:
        text (str): ข้อความที่ต้องการให้ AI พูด
        voice (str): เสียงพากย์ (เช่น 'th-TH-NiwatNeural', 'th-TH-AcharaNeural')
        wait (bool): รอให้พูดจบก่อนทำคำสั่งถัดไปหรือไม่ (ค่าเริ่มต้น: True)
        temp_file (str): ชื่อไฟล์เสียงชั่วคราว
    """
    if not text or not text.strip():
        return

    clean_text = text.strip()
    print(f"🤖 [AI พูด]: {clean_text}")

    # 1. สร้างไฟล์เสียงผ่าน edge-tts
    try:
        _run_tts_generation(clean_text, temp_file, voice)
    except Exception as e:
        print(f"เกิดข้อผิดพลาดในการแปลงข้อความเป็นเสียง (TTS): {e}")
        return

    # 2. เล่นไฟล์เสียงผ่าน pygame
    try:
        pygame.mixer.init()
        pygame.mixer.music.load(temp_file)
        pygame.mixer.music.play()

        if wait:
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)

        pygame.mixer.quit()
    except Exception as e:
        print(f"เกิดข้อผิดพลาดในการเล่นเสียง: {e}")


if __name__ == "__main__":
    msg = input("พิมพ์ข้อความที่ต้องการให้ AI พูด (กด Enter เพื่อใช้ข้อความตัวอย่าง): ")
    if not msg.strip():
        msg = "สวัสดีครับ ระบบสั่งการด้วยเสียงพร้อมทำงานแล้วครับ"
    speak(msg)

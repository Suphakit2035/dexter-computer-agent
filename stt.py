"""
โมดูลแปลงเสียงพูดเป็นข้อความ (Speech to Text - STT)
ใช้ Whisper ในการถอดความเสียงภาษาไทย และ sounddevice สำหรับบันทึกเสียงจากไมโครโฟน
"""

import sys
import os
from typing import Optional
from pathlib import Path
import numpy as np

# ตั้งค่า stdout/stderr ให้รองรับ UTF-8 บน Windows console
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

_whisper_model = None


def get_whisper_model(model_name: str = "medium"):
    """
    โหลดโมเดล Whisper แบบแคชไว้ เพื่อไม่ต้องโหลดซ้ำทุกครั้ง
    """
    global _whisper_model
    if _whisper_model is None:
        import whisper
        print(f"🎙️ กำลังโหลดโมเดล Whisper ({model_name})...")
        _whisper_model = whisper.load_model(model_name)
    return _whisper_model


def record_audio(
    output_file: str = "recorded_command.wav",
    duration: float = 5.0,
    sample_rate: int = 16000,
) -> str:
    """
    บันทึกเสียงจากไมโครโฟนตามเวลาที่กำหนด (วินาที)
    """
    try:
        import sounddevice as sd
        from scipy.io import wavfile
    except ImportError as e:
        raise ImportError(f"ต้องติดตั้ง sounddevice และ scipy เพื่ออัดเสียงจากไมโครโฟน: {e}")

    print(f"🎙️ กำลังบันทึกเสียง {duration} วินาที... (พูดคำสั่งได้เลย)")
    audio_data = sd.rec(
        int(duration * sample_rate),
        samplerate=sample_rate,
        channels=1,
        dtype="int16",
    )
    sd.wait()  # รอจนกว่าจะอัดเสียงเสร็จ
    print("⏹️ บันทึกเสียงเสร็จสิ้น")

    wavfile.write(output_file, sample_rate, audio_data)
    return output_file


def transcribe_with_gemini(audio_file: str) -> str:
    """
    ถอดความเสียงด้วย Gemini 3.8 Flash (ใช้เป็นตัวสำรองกรณี Whisper มีปัญหา)
    """
    try:
        from gemini_ai import get_gemini_client
        from google.genai import types

        client = get_gemini_client()
        with open(audio_file, "rb") as f:
            audio_bytes = f.read()

        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=[
                types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav"),
                "ช่วยถอดความเสียงพูดภาษาไทยในคลิปเสียงนี้ออกมาเป็นข้อความคำสั่งอย่างแม่นยำ โดยพิมพ์เฉพาะข้อความที่ได้ยินเท่านั้น ไม่ต้องใส่คำอธิบายเพิ่มเติม",
            ],
        )
        return (response.text or "").strip()
    except Exception as e:
        print(f"⚠️ ไม่สามารถถอดความด้วย Gemini ได้: {e}")
        return ""


def transcribe_audio(
    audio_file: str,
    model_name: str = "medium",
    language: str = "en", # th
) -> str:
    """
    ถอดความเสียงจากไฟล์เป็นข้อความ (ลอง Whisper ก่อน หากติดขัดจะสลับไปใช้ Gemini อัตโนมัติ)
    """
    if not Path(audio_file).exists():
        raise FileNotFoundError(f"ไม่พบไฟล์เสียง: {audio_file}")

    try:
        model = get_whisper_model(model_name=model_name)
        print(f"⏳ กำลังแปลงเสียงเป็นข้อความด้วย Whisper จาก: {audio_file}...")
        result = model.transcribe(audio_file, language=language)
        text = result.get("text", "").strip()
        if text:
            return text
    except Exception as e:
        print(f"⚠️ เกิดปัญหาขณะถอดเสียงด้วย Whisper ({e}) กำลังสลับไปใช้ Gemini STT...")

    # สำรอง: ใช้ Gemini ถอดความเสียง
    return transcribe_with_gemini(audio_file)


def listen_command(
    duration: float = 5.0,
    model_name: str = "medium",
    temp_file: str = "command.wav",
) -> str:
    """
    ฟังก์ชันแบบครบวงจร: อัดเสียงจากไมค์ -> ถอดความเป็นข้อความ
    """
    audio_path = record_audio(output_file=temp_file, duration=duration)
    text = transcribe_audio(audio_path, model_name=model_name, language="th")
    print(f"📝 ได้รับคำสั่ง: '{text}'")
    return text


if __name__ == "__main__":
    choice = input("เลือก: 1) อัดเสียงจากไมค์ 2) ถอดเสียงจากไฟล์ (rubik-test.mp4): ")
    if choice == "2":
        f = "rubik-test.mp4"
        if Path(f).exists():
            res = transcribe_audio(f)
            print("ข้อความ:", res)
        else:
            print(f"ไม่พบไฟล์ {f}")
    else:
        sec = float(input("กำหนดเวลาอัดเสียง (วินาที) [ค่าเริ่มต้น 5]: ") or "5")
        res = listen_command(duration=sec)
        print("ข้อความที่ได้:", res)

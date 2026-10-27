"""
โมดูลแปลงเสียงพูดเป็นข้อความ (Speech to Text - STT)
ใช้ Whisper ในการถอดความเสียงภาษาไทย และ sounddevice สำหรับบันทึกเสียงจากไมโครโฟน
"""

import sys
import queue
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
    sample_rate: int = 16000,
    silence_duration: float = 1.2,
    silence_threshold: float = 500.0,
    pre_roll_duration: float = 0.3,
) -> str:
    """
    ฟังเสียงต่อเนื่องและหยุดเมื่อมีเสียงพูดแล้วเงียบต่อเนื่องตามเวลาที่กำหนด
    """
    try:
        import sounddevice as sd
        from scipy.io import wavfile
    except ImportError as e:
        raise ImportError(f"ต้องติดตั้ง sounddevice และ scipy เพื่ออัดเสียงจากไมโครโฟน: {e}")

    block_duration = 0.05
    block_size = int(sample_rate * block_duration)
    pre_roll_blocks = max(1, int(pre_roll_duration / block_duration))
    audio_queue: queue.Queue = queue.Queue()
    recent_audio = []
    recorded_audio = []
    speech_detected = False
    quiet_seconds = 0.0
    noise_floor = 100.0

    def enqueue_audio(indata, frames, time_info, status):
        if status:
            print(f"⚠️ สถานะไมโครโฟน: {status}")
        audio_queue.put(indata.copy())

    print("🎙️ กำลังฟังอยู่ พูดคำสั่งได้เลย... (จะหยุดเมื่อเงียบต่อเนื่อง)")
    try:
        with sd.InputStream(
            samplerate=sample_rate,
            channels=1,
            dtype="int16",
            blocksize=block_size,
            callback=enqueue_audio,
        ):
            while True:
                chunk = audio_queue.get()
                rms = float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))
                threshold = max(silence_threshold, noise_floor * 2.5)
                is_speech = rms >= threshold

                if not speech_detected:
                    if is_speech:
                        speech_detected = True
                        recorded_audio.extend(recent_audio)
                        recorded_audio.append(chunk)
                        print("🗣️ ตรวจพบเสียงพูด กำลังฟังต่อ...")
                    else:
                        recent_audio.append(chunk)
                        if len(recent_audio) > pre_roll_blocks:
                            recent_audio.pop(0)
                        noise_floor = noise_floor * 0.95 + rms * 0.05
                    continue

                recorded_audio.append(chunk)
                if is_speech:
                    quiet_seconds = 0.0
                else:
                    quiet_seconds += len(chunk) / sample_rate
                    noise_floor = noise_floor * 0.95 + rms * 0.05

                if quiet_seconds >= silence_duration:
                    break
    except KeyboardInterrupt:
        if not speech_detected:
            raise

    if not speech_detected or not recorded_audio:
        print("⚠️ ยังไม่ได้รับเสียงพูด")
        wavfile.write(output_file, sample_rate, np.zeros((0, 1), dtype=np.int16))
        return output_file

    audio_data = np.concatenate(recorded_audio, axis=0)
    wavfile.write(output_file, sample_rate, audio_data)
    print(f"⏹️ หยุดฟังหลังเงียบ {silence_duration:.1f} วินาที")
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
    model_name: str = "medium",
    temp_file: str = "command.wav",
    silence_duration: float = 1.2,
) -> str:
    """
    ฟังก์ชันแบบครบวงจร: อัดเสียงจากไมค์ -> ถอดความเป็นข้อความ
    """
    audio_path = record_audio(output_file=temp_file, silence_duration=silence_duration)
    from scipy.io import wavfile
    _, audio_data = wavfile.read(audio_path)
    if audio_data.size == 0:
        print("📝 ไม่พบคำสั่งเสียง")
        return ""
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
        res = listen_command()
        print("ข้อความที่ได้:", res)

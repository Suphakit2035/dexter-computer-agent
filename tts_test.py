import asyncio
import edge_tts
import pygame

# กำหนดเสียงภาษาไทย (เลือกเสียงที่ชอบได้ เช่น th-TH-NiwatNeural หรือ th-TH-AcharaNeural)
VOICE = "th-TH-NiwatNeural"
TEMP_AUDIO = "response.mp3"


async def _generate_audio(text):
  communicate = edge_tts.Communicate(text, VOICE)
  await communicate.save(TEMP_AUDIO)


def speak(text):
  print(f"🤖 กำลังพูด: {text}")
  # 1. สร้างไฟล์เสียงจาก edge-tts (รันผ่าน async)
  asyncio.run(_generate_audio(text))

  # 2. เล่นเสียงทันทีด้วย pygame
  pygame.mixer.init()
  pygame.mixer.music.load(TEMP_AUDIO)
  pygame.mixer.music.play()

  # รอจนกว่าจะพูดจบ
  while pygame.mixer.music.get_busy():
    pygame.time.Clock().tick(10)

  pygame.mixer.quit()


# --- ทดลองใช้งาน ---
# speak("เปิดเบราว์เซอร์ Google Chrome ให้เรียบร้อยแล้วครับ")
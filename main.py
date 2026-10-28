"""
Dexter Computer Agent - Main Controller
ระบบควบคุมคอมพิวเตอร์อัตโนมัติด้วยเสียงและวิชัน AI (Gemini + Whisper + Edge-TTS + PyAutoGUI)
"""

import os
import sys
import time
import json
import re
import io
from pathlib import Path
from typing import Dict, Any, List, Optional
from PIL import Image

# ตั้งค่า stdout/stderr ให้รองรับ UTF-8 บน Windows console
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# โหลด Environment Variables (.env)
from dotenv import load_dotenv
load_dotenv()

# นำเข้าโมดูลย่อยของโปรเจกต์
import mouse_event as mouse
import screen_capture
from tts import speak
import stt
from gemini_ai import get_gemini_client
from google.genai import types

# ลำดับโมเดลที่เรียกใช้งาน (หากตัวใดติดคิว 503 หรือ Quota จะสลับไปยังโมเดลถัดไปทันที)
CANDIDATE_MODELS = [
    "gemini-flash-lite-latest",
    "gemini-3.5-flash",
    "gemini-3.8-flash",
    "gemini-flash-latest",
]

SYSTEM_INSTRUCTION = """คุณคือ Computer Control Agent ผู้เชี่ยวชาญในการสั่งการคอมพิวเตอร์ผ่านคีย์บอร์ดและเมาส์
เป้าหมายของคุณคือทำตามคำสั่งของผู้ใช้ให้สำเร็จทีละขั้นตอน อย่างแม่นยำและรวดเร็วที่สุด

ในแต่ละขั้นตอน คุณจะได้รับ:
1. คำสั่งเป้าหมายของผู้ใช้ (User Goal)
2. ขนาดภาพหน้าจอที่แนบมา และขนาดพิกัดเมาส์ของระบบ
3. ภาพหน้าจอปัจจุบัน (Screenshot)
4. ประวัติการกระทำก่อนหน้านี้ (Action History)

กฎการอ่านพิกัดจากภาพ:
- พิกัด x,y และ end_x,end_y ต้องอ้างอิงจากภาพหน้าจอที่แนบมา โดยมุมซ้ายบนคือ (0,0) และ x เพิ่มไปทางขวา, y เพิ่มลงล่าง
- ใช้ความกว้างและความสูงของภาพที่ระบุในข้อความเป็นขอบเขตพิกัด ห้ามใช้ขนาดที่คาดเดาเอง
- เมื่อชี้ไปยังปุ่มหรือไอคอน ให้เลือกบริเวณกึ่งกลางของเป้าหมาย หลีกเลี่ยงขอบหรือพื้นที่ว่างข้างเคียง
- หากเป้าหมายเล็กหรือไม่ชัด ให้เลือก action แบบ wait เพื่อให้ตรวจภาพใหม่ แทนการเดาพิกัด

============================================================
กฎสำคัญในการเลือกวิธีสั่งการ (Action Priority Rules):
============================================================
1. 【สำคัญที่สุด: ใช้คีย์ลัดหรือคีย์บอร์ดเป็นอันดับแรก (Keyboard / Shortcut First)】
   - หากเป้าหมายสามารถทำได้ด้วยการกดปุ่มคีย์บอร์ดหรือคีย์ลัด ให้เลือกใช้คีย์ลัดก่อนเสมอ เพราะแม่นยำ รวดเร็ว และไม่ผิดพลาด
   - ตัวอย่างการใช้คีย์ลัดเป็นหลัก:
     * ต้องการเปิด Start Menu หรือค้นหาบน Windows -> ให้ใช้ "press_key" ด้วย "key": "win" ก่อนเสมอ (แทนการเอาเมาส์ไปคลิกปุ่ม Start)
     * ต้องการเปิดแอป/โปรแกรม -> ให้กด "win" แล้ว "type" ชื่อโปรแกรม เช่น "chrome" หรือ "terminal" แล้วกด "enter"
     * ต้องการเปิดหน้าต่าง Run -> ให้ใช้ "hotkey" ด้วย "keys": ["win", "r"]
     * ต้องการเปิดแท็บใหม่บน Browser -> ให้ใช้ "hotkey" ด้วย "keys": ["ctrl", "t"]
     * ต้องการปิดหน้าต่างหรือแท็บ -> ให้ใช้ "hotkey" ด้วย ["ctrl", "w"] หรือ ["alt", "f4"]
     * ต้องการยืนยันหรือกดส่ง -> ให้ใช้ "press_key" ด้วย "key": "enter"
     * ต้องการยกเลิก/ปิด popup/เมนู -> ให้ใช้ "press_key" ด้วย "key": "esc"

2. 【ใช้การคลิกเมาส์เป็นวิธีรอง (Mouse as Secondary / Fallback)】
   - ใช้เมาส์เฉพาะในกรณีที่ไม่สามารถใช้คีย์ลัดได้ หรือจำเป็นต้องคลิกเลือกไอคอน ลิงก์ หรือตำแหน่งเฉพาะบนหน้าจอจริงๆ เท่านั้น

3. 【ตรวจสอบภาพหน้าจอก่อนกดทุกครั้ง (Inspect Screen Before Action)】
   - ก่อนจะสั่ง Action ใดๆ ให้สังเกตภาพหน้าจอปัจจุบันอย่างละเอียดอีกครั้ง เพื่อยืนยันว่าหน้าต่างหรือปุ่มเป้าหมายปรากฏอยู่จริงและพร้อมรับการกด อย่าเดาพิกัดหรือผลลัพธ์ล่วงหน้า

4. 【อย่าเดาว่าคำสั่งสำเร็จแล้ว ให้ดูสิ่งที่ปรากฏบนจอจริง (Verify Actual Visual Feedback)】
   - อย่าเชื่อประวัติ (Action History) เพียงอย่างเดียว! ให้ดูสิ่งที่เกิดขึ้นจริงบนภาพหน้าจอเสมอ
   - ตัวอย่าง: หากเคยสั่งพิมพ์ 'chrome' แต่สังเกตในภาพหน้าจอแล้วช่องค้นหายังว่างเปล่า (ไม่มีตัวหนังสือคำว่า chrome อยู่) แสดงว่ายังพิมพ์ไม่ติด อย่าเพิ่งกด Enter! ให้ลองคลิกที่ช่องค้นหาเพื่อโฟกัสก่อน แล้วพิมพ์ซ้ำ
   - หากเห็นไอคอนโปรแกรมที่ต้องการอยู่บนหน้าจอ (เช่น ไอคอน Chrome บน Desktop หรือ Taskbar) สามารถคลิกโดยตรงได้เช่นกัน

5. 【กฎการจบภารกิจ (Done Criteria)】
   - จะตั้ง "action": "finish" และ "done": true ได้ก็ต่อเมื่อเห็นผลลัพธ์ตามเป้าหมายของผู้ใช้ปรากฏขึ้นบนหน้าจอจริงแล้วเท่านั้น!
   - เช่น ผู้ใช้สั่ง "ช่วยเปิด google chrome" -> จะจบภารกิจได้ก็ต่อเมื่อเห็นหน้าต่างโปรแกรม Google Chrome เปิดขึ้นมาบนหน้าจอแล้วจริงๆ หากยังไม่เห็นหน้าต่างโปรแกรมเปิดขึ้นมา ห้ามตั้ง done: true เด็ดขาด ให้ทำตามขั้นตอนต่อไปจนกว่าหน้าต่างจะเปิดขึ้นมาสำเร็จ

============================================================
ประเภทของ Action ที่สามารถสั่งได้:
============================================================
1. "press_key" - กดปุ่มคีย์บอร์ด 1 ปุ่ม เช่น "win" (เปิด Start menu), "enter", "esc", "space", "tab" ระบุใน "key" (แนะนำให้ใช้เป็นอันดับแรก)
2. "hotkey" - กดปุ่มลัดผสม เช่น ["ctrl", "c"] หรือ ["win", "r"] หรือ ["alt", "tab"] ระบุใน "keys" (แนะนำให้ใช้เป็นอันดับแรก)
3. "type" - พิมพ์ข้อความ ระบุใน "text"
4. "click" - คลิกเมาส์ซ้ายที่พิกัด (x, y) (ใช้เป็นวิธีรอง)
5. "double_click" - ดับเบิลคลิกที่ (x, y)
6. "right_click" - คลิกขวาที่ (x, y)
7. "move" - เลื่อนเมาส์ไปที่ (x, y)
8. "drag" - ลากเมาส์จาก (x, y) ไปยัง (end_x, end_y)
9. "scroll" - เลื่อนลูกกลิ้ง ("scroll_clicks": บวก=ขึ้น, ลบ=ลง)
10. "wait" - หน่วงเวลารอโปรแกรมตอบสนอง ระบุใน "wait_seconds"
11. "finish" - เมื่อเป้าหมายสำเร็จครบถ้วนแล้ว ให้ตั้ง "action": "finish" และ "done": true

โครงสร้าง JSON ที่ต้องตอบกลับเท่านั้น:
{
  "thought": "อธิบายสิ่งที่เห็นบนจอ ตรวจสอบหน้าจอก่อนกด และเหตุผลในการเลือกใช้คีย์ลัดหรือเมาส์",
  "action": "press_key | hotkey | type | click | double_click | right_click | move | drag | scroll | wait | finish",
  "x": พิกัดแนวนอน หรือ null,
  "y": พิกัดแนวตั้ง หรือ null,
  "end_x": พิกัด x ปลายทาง (สำหรับ drag) หรือ null,
  "end_y": พิกัด y ปลายทาง (สำหรับ drag) หรือ null,
  "scroll_clicks": จำนวนคลิก scroll หรือ null,
  "key": "ชื่อปุ่ม (สำหรับ press_key เช่น 'win', 'enter') หรือ null",
  "text": "ข้อความที่พิมพ์ (สำหรับ type) หรือ null",
  "keys": ["ปุ่ม1", "ปุ่ม2"] (สำหรับ hotkey) หรือ null,
  "wait_seconds": วินาทีที่รอ หรือ null,
  "done": true/false,
  "summary": "ข้อความสรุปสั้นๆ แจ้งความคืบหน้าหรือผลลัพธ์"
}
"""


def _map_image_coordinate(value: Any, image_size: int, screen_size: int) -> Optional[int]:
    """แปลงพิกัดจากภาพที่ AI เห็นไปยังพิกัดจริงที่ PyAutoGUI ใช้"""
    if value is None:
        return None
    try:
        coordinate = int(round(float(value)))
    except (TypeError, ValueError):
        print(f"⚠️ ข้ามพิกัดที่ไม่ใช่ตัวเลข: {value!r}")
        return None

    if image_size <= 0 or screen_size <= 0:
        return None
    bounded = max(0, min(image_size - 1, coordinate))
    if bounded != coordinate:
        print(f"⚠️ พิกัด {coordinate} อยู่นอกภาพ จึงจำกัดให้อยู่ในช่วง 0 ถึง {image_size - 1}")
    if image_size == screen_size:
        return bounded
    return round(bounded * (screen_size - 1) / (image_size - 1)) if image_size > 1 else 0


def execute_action(
    action_data: Dict[str, Any],
    screen_w: int,
    screen_h: int,
    image_w: Optional[int] = None,
    image_h: Optional[int] = None,
) -> bool:
    """
    แปลงคำสั่ง JSON จาก AI เป็นการควบคุมเมาส์และคีย์บอร์ดจริง
    คืนค่า True หากถึงขั้นตอนสิ้นสุด (done)
    """
    action = action_data.get("action", "").lower()
    image_w = image_w or screen_w
    image_h = image_h or screen_h
    x = _map_image_coordinate(action_data.get("x"), image_w, screen_w)
    y = _map_image_coordinate(action_data.get("y"), image_h, screen_h)
    done = action_data.get("done", False)

    print(f"👉 กำลังดำเนินการ: {action} (image=({action_data.get('x')}, {action_data.get('y')}), screen=({x}, {y}))")

    def log_actual_position() -> None:
        actual_x, actual_y = mouse.get_position()
        print(f"📍 ตำแหน่งเมาส์จริง: ({actual_x}, {actual_y})")

    if action == "click":
        if x is not None and y is not None:
            print(f"👀 เลื่อนเคอร์เซอร์ไปที่ ({x}, {y}) เพื่อตรวจสอบตำแหน่งหน้าจอก่อนกด...")
            mouse.move_to(x, y, duration=0.25)
            log_actual_position()
            time.sleep(0.2)  # หยุดดูภาพหน้าจอตรงตำแหน่งเคอร์เซอร์ก่อนกด
            print(f"🖱️ ทำการคลิกซ้ายที่ ({x}, {y})")
            mouse.click(x, y)
        else:
            mouse.click()

    elif action == "double_click":
        if x is not None and y is not None:
            print(f"👀 เลื่อนเคอร์เซอร์ไปที่ ({x}, {y}) ก่อนดับเบิลคลิก...")
            mouse.move_to(x, y, duration=0.25)
            log_actual_position()
            time.sleep(0.2)
            print(f"🖱️ ทำการดับเบิลคลิกที่ ({x}, {y})")
            mouse.double_click(x, y)
        else:
            mouse.double_click()

    elif action == "right_click":
        if x is not None and y is not None:
            print(f"👀 เลื่อนเคอร์เซอร์ไปที่ ({x}, {y}) ก่อนคลิกขวา...")
            mouse.move_to(x, y, duration=0.25)
            log_actual_position()
            time.sleep(0.2)
            print(f"🖱️ ทำการคลิกขวาที่ ({x}, {y})")
            mouse.right_click(x, y)
        else:
            mouse.right_click()

    elif action == "move":
        if x is not None and y is not None:
            print(f"👀 เลื่อนเมาส์ไปที่ ({x}, {y})")
            mouse.move_to(x, y, duration=0.25)
            log_actual_position()

    elif action == "drag":
        end_x = _map_image_coordinate(action_data.get("end_x", action_data.get("x")), image_w, screen_w)
        end_y = _map_image_coordinate(action_data.get("end_y", action_data.get("y")), image_h, screen_h)
        if x is not None and y is not None and end_x is not None and end_y is not None:
            print(f"🖱️ ลากเมาส์จาก ({x}, {y}) ไปยัง ({end_x}, {end_y})")
            mouse.drag(x, y, int(end_x), int(end_y), duration=0.5)
            log_actual_position()

    elif action == "scroll":
        clicks = int(action_data.get("scroll_clicks", -3))
        print(f"📜 เลื่อนลูกกลิ้ง {clicks} สเต็ป")
        mouse.scroll(clicks, x=x, y=y)

    elif action == "press_key":
        key = action_data.get("key", "")
        if key:
            print(f"⌨️ สั่งการด้วยคีย์บอร์ด: กดปุ่ม '{key}'")
            time.sleep(0.1)
            mouse.press_key(key)

    elif action == "type":
        text = action_data.get("text", "")
        if text:
            print(f"⌨️ สั่งการด้วยคีย์บอร์ด: พิมพ์ข้อความ '{text}'")
            time.sleep(0.1)
            mouse.type_text(text)

    elif action == "hotkey":
        keys = action_data.get("keys", [])
        if keys:
            print(f"⌨️ สั่งการด้วยคีย์ลัด: {keys}")
            time.sleep(0.1)
            mouse.hotkey(*keys)

    elif action == "wait":
        sec = float(action_data.get("wait_seconds", 1.0))
        time.sleep(sec)

    elif action == "finish":
        return True

    return done


def parse_ai_response(response_text: str) -> Dict[str, Any]:
    """
    แปลงข้อความตอบกลับจาก Gemini ให้เป็น Dict JSON
    """
    text = response_text.strip()
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        text = match.group(1)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        print(f"⚠️ คำตอบจาก AI ไม่ใช่รูปแบบ JSON ปกติ: {text[:100]}...")
        return {
            "thought": "ไม่สามารถแปลง JSON ได้ กำลังวิเคราะห์ใหม่",
            "action": "wait",
            "wait_seconds": 1.0,
            "done": False,
            "summary": "กำลังวิเคราะห์หน้าจอใหม่...",
        }


def prepare_image_part(image_path: str) -> types.Part:
    """
    อ่านไฟล์ภาพและแปลงเป็น Part แบบ JPEG ขนาดเล็ก เพื่อส่งผ่าน API ได้อย่างรวดเร็ว
    """
    with open(image_path, "rb") as f:
        data = f.read()
    return types.Part.from_bytes(data=data, mime_type="image/jpeg")


def query_gemini_with_fallback(client, contents: list) -> str:
    """
    เรียก Gemini API โดยมีระบบหมุนเวียนโมเดลสำรองอัตโนมัติ หากเจอ 503 หรือ Error
    """
    last_error = None
    for model_name in CANDIDATE_MODELS:
        print(f"🧠 กำลังเรียกโมเดล: {model_name}...")
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    response_mime_type="application/json",
                    temperature=0.2,
                ),
            )
            print(f"✅ ได้รับคำตอบจาก {model_name}")
            return response.text or "{}"
        except Exception as e:
            err_str = str(e)
            print(f"⚠️ โมเดล {model_name} ไม่สามารถใช้งานได้ ({err_str[:80]}...) กำลังลองโมเดลถัดไป...")
            last_error = e
            time.sleep(1.0)

    raise RuntimeError(f"ทุกโมเดลไม่สามารถตอบกลับได้ในขณะนี้ ข้อผิดพลาดล่าสุด: {last_error}")


def run_agent_loop(goal: str, max_steps: int = 15) -> str:
    """
    ลูปการทำงานหลัก: ถ่ายภาพหน้าจอ -> ส่งให้ Gemini -> ควบคุมเมาส์/คีย์บอร์ด -> ทำซ้ำจนเสร็จ
    """
    client = get_gemini_client()
    screen_w, screen_h = screen_capture.get_screen_resolution()
    history: List[str] = []
    final_summary = "ดำเนินการเสร็จสิ้นเรียบร้อยแล้วครับ"

    print(f"\n🚀 เริ่มต้นภารกิจ: '{goal}'")
    print(f"🖥️ ขนาดหน้าจอ: {screen_w} x {screen_h} พิกเซล (จำกัดสูงสุด {max_steps} ขั้นตอน)")

    screenshot_path = "current_screen.jpg"

    for step in range(1, max_steps + 1):
        print(f"\n--- [ขั้นตอนที่ {step}/{max_steps}] ---")

        # 1. ถ่ายภาพหน้าจอแบบบีบอัด JPEG (ขนาดไฟล์ ~100KB ส่งไวมาก)
        print("📸 ถ่ายภาพหน้าจอปัจจุบัน...")
        # เพิ่มคุณภาพ JPEG เพื่อรักษาขอบปุ่มและไอคอนขนาดเล็กที่ AI ใช้กะพิกัด
        screenshot = screen_capture.capture_screen(save_path=screenshot_path, quality=90)
        image_w, image_h = screenshot.size
        img_part = prepare_image_part(screenshot_path)

        # 2. จัดเตรียม Prompt สำหรับ Gemini
        history_str = "\n".join([f"- {h}" for h in history]) if history else "ยังไม่มีการกระทำก่อนหน้านี้ (เพิ่งเริ่มต้น)"
        prompt = f"""
เป้าหมายของผู้ใช้ (User Goal): "{goal}"
ขนาดภาพที่แนบให้วิเคราะห์: กว้าง {image_w} x สูง {image_h} พิกเซล
ขนาดพิกัดเมาส์ของระบบ: กว้าง {screen_w} x สูง {screen_h} พิกเซล
พิกัดทุกค่าที่ตอบกลับต้องอ้างอิงจากภาพ {image_w}x{image_h}; ระบบจะแปลงไปยังพิกัดเมาส์ให้อัตโนมัติ
ประวัติการกระทำก่อนหน้านี้:
{history_str}

ดูภาพหน้าจอที่แนบมานี้ แล้วตัดสินใจเลือก Action ถัดไปในรูปแบบ JSON:
"""

        # 3. ส่งภาพและคำถามให้ Gemini ด้วยระบบหมุนเวียนโมเดลสำรอง
        try:
            raw_text = query_gemini_with_fallback(client, contents=[img_part, prompt])
        except Exception as e:
            print(f"❌ เกิดข้อผิดพลาดในการเรียก Gemini API: {e}")
            final_summary = f"เกิดข้อผิดพลาดในการเชื่อมต่อกับ Gemini: {e}"
            break

        # 4. แปลงคำตอบเป็นโครงสร้าง Action
        action_data = parse_ai_response(raw_text)
        thought = action_data.get("thought", "")
        summary = action_data.get("summary", "")
        print(f"💭 ความคิด AI: {thought}")
        if summary:
            print(f"📢 แจ้งสถานะ: {summary}")

        # 5. สั่งควบคุมเมาส์ / คีย์บอร์ด
        is_done = execute_action(action_data, screen_w, screen_h, image_w, image_h)

        # บันทึกประวัติ
        action_name = action_data.get("action")
        act_desc = f"Step {step}: {action_name} - {thought}"
        history.append(act_desc)

        # ตรวจสอบการเสร็จสิ้น
        if is_done:
            final_summary = summary or f"ดำเนินการ '{goal}' สำเร็จเรียบร้อยแล้วครับ"
            print(f"\n🎉 ภารกิจสำเร็จในขั้นตอนที่ {step}!")
            break

        # หน่วงเวลาสั้นๆ เพื่อให้หน้าจอแสดงผลการเปลี่ยนแปลงหลังคลิก
        time.sleep(1.0)
    else:
        final_summary = f"ครบกำหนด {max_steps} ขั้นตอนแล้ว ระบบหยุดการทำงานครับ"
        print(f"\n⚠️ สิ้นสุดการทำงานเนื่องจากครบจำนวนขั้นตอนสูงสุด ({max_steps} steps)")

    return final_summary


def get_user_command() -> str:
    """
    รับคำสั่งจากผู้ใช้ผ่านเสียง (STT) หรือการพิมพ์
    """
    print("\n" + "=" * 50)
    print("🤖 ยินดีต้อนรับสู่ Dexter Computer Agent")
    print("=" * 50)
    print("กรุณาเลือกวิธีสั่งการ:")
    print(" 1) พูดคำสั่งผ่านไมโครโฟน (Voice Command - Whisper STT)")
    print(" 2) พิมพ์คำสั่ง (Keyboard Text Input)")
    print("=" * 50)

    choice = input("เลือกรูปแบบ (1 หรือ 2, กด Enter เพื่อเลือก 1): ").strip()

    if choice == "2":
        cmd = input("\n⌨️ พิมพ์คำสั่งที่ต้องการให้ควบคุมคอมพิวเตอร์: ").strip()
        return cmd
    else:
        speak("สวัสดีครับ พร้อมรับคำสั่งแล้วครับ กรุณาพูดคำสั่งได้เลยครับ")
        try:
            print("\n🎙️ กำลังเตรียมฟังเสียง...")
            cmd = stt.listen_command()
            return cmd
        except Exception as e:
            print(f"⚠️ เกิดข้อผิดพลาดในการฟังเสียง ({e}) สลับเป็นโหมดพิมพ์ข้อความแทน:")
            cmd = input("⌨️ พิมพ์คำสั่งของคุณ: ").strip()
            return cmd


def main():
    # ตรวจสอบ GEMINI_API_KEY
    if not os.environ.get("GEMINI_API_KEY"):
        print("❌ ข้อผิดพลาด: ไม่พบ GEMINI_API_KEY ในระบบ")
        print("กรุณาใส่ GEMINI_API_KEY ในไฟล์ .env หรือตั้งค่า Environment Variable")
        return

    # รับคำสั่งจากผู้ใช้ (เสียงหรือข้อความ)
    command = get_user_command()
    if not command:
        print("⚠️ ไม่ได้รับคำสั่ง ยกเลิกการทำงาน")
        return

    # พูดตอบรับเริ่มต้น
    speak(f"รับคำสั่งแล้วครับ กำลังดำเนินการ: {command}")

    # รัน Agent Loop (ถ่ายจอ -> วิเคราะห์ -> ควบคุมเมาส์/คีย์บอร์ด -> ทำซ้ำ)
    result_message = run_agent_loop(goal=command, max_steps=12)

    # เมื่อทำเสร็จ พูดตอบกลับมา
    print(f"\n🔊 รายงานผลลัพธ์ผ่านเสียง: '{result_message}'")
    speak(result_message)


if __name__ == "__main__":
    if "--console" in sys.argv:
        main()
    else:
        from widget import launch_widget

        launch_widget(
            run_agent=lambda goal: run_agent_loop(goal=goal, max_steps=12),
            listen_command=stt.listen_command,
            speak=speak,
            api_key_available=bool(os.environ.get("GEMINI_API_KEY")),
        )

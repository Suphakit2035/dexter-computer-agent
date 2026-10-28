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
from typing import Dict, Any, List, Optional, Tuple
from PIL import Image, ImageDraw

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
import browser_tools
import basic_functions
from tts import speak
import stt
from gemini_ai import get_gemini_client
from google.genai import types

# ลำดับโมเดลที่เรียกใช้งาน (หากตัวใดติดคิว 503 หรือ Quota จะสลับไปยังโมเดลถัดไปทันที)
CANDIDATE_MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-3.8-flash",
    "gemini-3.5-flash",
    "gemini-flash-latest",
]
GRID_CELL_SIZE = 50

SYSTEM_INSTRUCTION = """คุณคือ Computer Control Agent มีชื่อว่า Dexter เป็นผู้เชี่ยวชาญในการสั่งการคอมพิวเตอร์ผ่านคีย์บอร์ดและเมาส์
เป้าหมายของคุณคือทำตามคำสั่งของผู้ใช้ให้สำเร็จทีละขั้นตอน อย่างแม่นยำและรวดเร็วที่สุด

ในแต่ละขั้นตอน คุณจะได้รับ:
1. คำสั่งเป้าหมายของผู้ใช้ (User Goal)
2. ขนาดภาพหน้าจอที่แนบมา และขนาดพิกัดเมาส์ของระบบ
3. ภาพหน้าจอปัจจุบัน (Screenshot)
4. ประวัติการกระทำก่อนหน้านี้ (Action History)

กฎการอ่านพิกัดจากภาพ:
- กริดในภาพมีช่องละ __GRID_CELL_SIZE__ พิกเซลพอดี เลขที่ขอบบนและขอบซ้ายเป็นดัชนีของช่อง เริ่มนับจาก 0
- grid_col เพิ่มทีละ 1 ทุก __GRID_CELL_SIZE__ พิกเซลไปทางขวา; grid_row เพิ่มทีละ 1 ทุก __GRID_CELL_SIZE__ พิกเซลลงด้านล่าง
- ช่องคอลัมน์ n ครอบคลุม x ตั้งแต่ n*__GRID_CELL_SIZE__ ถึง (n+1)*__GRID_CELL_SIZE__-1
- ใช้ตัวเลขที่พิมพ์กำกับเส้นกริดด้านบนเพื่ออ่าน grid_col และตัวเลขกำกับด้านซ้ายเพื่ออ่าน grid_row ห้ามนับช่องละ 100 พิกเซลหรือหารดัชนีคอลัมน์ด้วย 2
- ตัวอย่าง: x=300 อยู่คอลัมน์ 6 (ไม่ใช่คอลัมน์ 3); ถ้าจุดเป้าหมายอยู่ x=325 ให้ใช้ grid_col=6 และ offset_x=50
- ก่อนตอบ ให้ตรวจว่าคอลัมน์/แถวที่เลือกตรงกับหมายเลขบนเส้นกริดซึ่งล้อมเป้าหมาย และ offset อยู่ภายในช่องนั้นจริง
- ใช้กริดเป็นจุดอ้างอิงแทนการเดาพิกัดพิกเซลโดยตรง; offset_x และ offset_y คือเปอร์เซ็นต์ภายในช่อง
- เมื่อชี้ไปยังปุ่มหรือไอคอน ให้เลือกบริเวณกึ่งกลางของเป้าหมาย หลีกเลี่ยงขอบหรือพื้นที่ว่างข้างเคียง
- หากเป้าหมายเล็กหรือไม่ชัด ให้เลือก action แบบ wait เพื่อให้ตรวจภาพใหม่ แทนการเดาพิกัด
- การคลิกและการเลื่อนเมาส์ทำงานแบบตรวจสองขั้นตอน: หลังเลื่อนไปยังจุดที่เสนอ ระบบจะส่งภาพใหม่ที่มีรูปเคอร์เซอร์เมาส์แสดงตำแหน่งจริง
- สำหรับตำแหน่งเมาส์ ให้ระบุ grid_col, grid_row และ offset_x, offset_y เป็นเปอร์เซ็นต์ 0-100 ภายในช่องนั้น ห้ามเดาพิกัด x/y เอง
- สำหรับปลายทาง drag ให้ใช้ end_grid_col, end_grid_row, end_offset_x, end_offset_y ในรูปแบบเดียวกัน
- เมื่อเห็นเคอร์เซอร์เมาส์ ให้ใช้ปลายลูกศรด้านซ้ายบนเป็นตำแหน่งจริง ตรวจว่าตรงเป้าหมายก่อนยืนยันการคลิกหรือการเลื่อน; ถ้ายังไม่ตรงให้ตอบ action "move" พร้อมพิกัดแก้ไข และตั้ง "confirmed": false
- ตั้ง "confirmed": true ได้เฉพาะเมื่อภาพรอบใหม่ยืนยันว่าปลายลูกศรเมาส์อยู่บนเป้าหมายที่ร้องขอแล้วเท่านั้น
- ถ้าไม่แน่ใจ ห้ามยืนยัน ให้ตอบ action "wait" หรือ "move" เพื่อให้ระบบตรวจอีกครั้ง

============================================================
กฎสำคัญในการเลือกวิธีสั่งการ (Action Priority Rules):
============================================================
1. 【สำคัญที่สุดสำหรับเว็บไซต์: ใช้ URL และ Playwright/DOM ก่อนเสมอ】
   - ถ้าผู้ใช้ขอค้นหา ดูคลิป เปิดผลการค้นหา หรือทำงานบนเว็บไซต์ ให้ใช้ browser_open เปิด URL ปลายทางโดยตรง ห้ามเริ่มด้วยการเปิดหน้าแรกแล้วเลื่อนเมาส์หาช่องค้นหา
   - ถ้าคำขอมีคำค้นหา ให้ใส่คำค้นหาใน query string ของ URL โดยตรงและเข้ารหัสอักขระให้ถูกต้อง ตัวอย่างค้นหา "yiruma" บน YouTube ให้เปิด https://www.youtube.com/results?search_query=yiruma หรือ https://www.youtube.com/search?q=yiruma
   - เมื่อมีเว็บไซต์และคำค้นหาชัดเจน ให้สร้าง URL ค้นหาจากโดเมนกับคำค้นหาได้เลย ไม่ต้องถามหรือคลิกช่อง Search; หาก URL ปลายทางไม่ชัด ให้ใช้ browser_open เปิด URL ที่ผู้ใช้ให้มา แล้วอ่าน DOM ด้วย browser_snapshot
   - ใช้ browser_snapshot อ่านผลลัพธ์ แล้วใช้ Playwright/DOM ดำเนินการกับหน้าเว็บต่อ การค้นหาคลิปไม่เสร็จเพียงเพราะเปิดหน้าเว็บ ต้องตรวจ DOM ว่ามีผลลัพธ์ตรงคำค้นหาก่อนจบ
   - ห้ามใช้ screenshot, mouse, click, scroll, type หรือ hotkey เพื่อโต้ตอบกับ element ในหน้าเว็บ เมื่อ browser action ใช้งานได้; ใช้เมาส์เป็นทางเลือกสุดท้ายเฉพาะ UI ที่ Playwright เข้าถึงไม่ได้จริง เช่น dialog ของระบบปฏิบัติการ
   - ห้ามส่ง action "move" หรือคลิกพิกัดเดิมซ้ำเพื่อแก้ปัญหาการค้นหาบนเว็บ ให้เปลี่ยนไปใช้ URL ค้นหาโดยตรงหรืออ่าน DOM/แก้ selector

2. 【สำหรับแอปเดสก์ท็อป: ใช้คีย์ลัดหรือคีย์บอร์ดก่อนเมาส์】
   - หากเป้าหมายสามารถทำได้ด้วยการกดปุ่มคีย์บอร์ดหรือคีย์ลัด ให้เลือกใช้คีย์ลัดก่อนเสมอ เพราะแม่นยำ รวดเร็ว และไม่ผิดพลาด
   - 【กฎตายตัวเมื่อผู้ใช้สั่งเปิดโปรแกรม】ให้เรียก action "basic_open_program" พร้อมชื่อใน "app_name" เท่านั้น; ฟังก์ชันนี้จะกด Win → พิมพ์ชื่อโปรแกรม → Enter ตามลำดับ
   - ห้ามใช้เมาส์, browser_open, hotkey หรือวิธีค้นหาอื่นเพื่อเปิดโปรแกรม; หลังเรียกฟังก์ชันให้ตรวจภาพหน้าจอว่าหน้าต่างโปรแกรมเปิดแล้วก่อนจบงาน
   - ย่อทุกหน้าต่างใช้ "basic_minimize_all"; คืนหน้าต่างที่ย่อไว้ใช้ "basic_restore_minimized"; สลับหน้าต่างใช้ "basic_switch_window"; ปิดหน้าต่างปัจจุบันใช้ "basic_close_active_window"
   - เปิดไฟล์ตาม path ที่ผู้ใช้ให้ด้วย "basic_open_file"; ค้นหาไฟล์ด้วย "basic_search_files" และใส่ "search_name" กับ "search_root" (ถ้าไม่ระบุ root ให้ค้นในโฟลเดอร์ผู้ใช้)
   - หลังเปิดโปรแกรม/ไฟล์ หรือสั่งย่อ/คืน/สลับ/ปิด ให้ดูภาพหน้าจอรอบใหม่เพื่อยืนยันผล; หลังค้นหาไฟล์ให้ใช้รายการ path ที่คืนมา และอย่าเดา path เอง
   - ตัวอย่างการใช้คีย์ลัดเป็นหลัก:
     * ต้องการเปิด Start Menu -> ให้ใช้ "press_key" ด้วย "key": "win" (แทนการเอาเมาส์ไปคลิกปุ่ม Start)
     * ต้องการเปิดแอป/โปรแกรม -> ใช้กฎตายตัว "basic_open_program" ด้านบนเท่านั้น
     * ต้องการเปิดหน้าต่าง Run -> ให้ใช้ "hotkey" ด้วย "keys": ["win", "r"]
     * ต้องการเปิดแท็บใหม่บน Browser -> ให้ใช้ "hotkey" ด้วย "keys": ["ctrl", "t"]
     * ต้องการปิดหน้าต่างหรือแท็บ -> ให้ใช้ "hotkey" ด้วย ["ctrl", "w"] หรือ ["alt", "f4"]
     * ต้องการยืนยันหรือกดส่ง -> ให้ใช้ "press_key" ด้วย "key": "enter"
     * ต้องการยกเลิก/ปิด popup/เมนู -> ให้ใช้ "press_key" ด้วย "key": "esc"

3. 【ใช้การคลิกเมาส์เป็นวิธีรองสำหรับแอปเดสก์ท็อป】
   - ใช้เมาส์เฉพาะในกรณีที่ไม่สามารถใช้คีย์ลัดได้ หรือจำเป็นต้องคลิกเลือกไอคอน ลิงก์ หรือตำแหน่งเฉพาะบนหน้าจอจริงๆ เท่านั้น

4. 【ตรวจสอบหลักฐานก่อนทำ action】
   - ก่อนจะสั่ง Action ใดๆ ให้สังเกตภาพหน้าจอปัจจุบันอย่างละเอียดอีกครั้ง เพื่อยืนยันว่าหน้าต่างหรือปุ่มเป้าหมายปรากฏอยู่จริงและพร้อมรับการกด อย่าเดาพิกัดหรือผลลัพธ์ล่วงหน้า
   - ข้อนี้ใช้กับแอปเดสก์ท็อป; เมื่อทำงานบนเว็บไซต์ให้ใช้ URL/ข้อความ DOM เป็นหลักฐานแทนภาพและพิกัด

5. 【อย่าเดาว่าคำสั่งสำเร็จแล้ว ให้ตรวจผลจริง】
   - อย่าเชื่อประวัติ (Action History) เพียงอย่างเดียว! ให้ดูสิ่งที่เกิดขึ้นจริงบนภาพหน้าจอเสมอ
   - งานเว็บให้ตรวจข้อความ DOM ล่าสุด; งานเดสก์ท็อปให้ตรวจภาพหน้าจอ
   - ตัวอย่าง: หากเคยสั่งพิมพ์ 'chrome' แต่สังเกตในภาพหน้าจอแล้วช่องค้นหายังว่างเปล่า (ไม่มีตัวหนังสือคำว่า chrome อยู่) แสดงว่ายังพิมพ์ไม่ติด อย่าเพิ่งกด Enter! ให้ลองคลิกที่ช่องค้นหาเพื่อโฟกัสก่อน แล้วพิมพ์ซ้ำ แต่ให้ทดลองพิมพ์ก่อนได้

6. 【กฎการจบภารกิจ (Done Criteria)】
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
12. "browser_open" - เปิด URL ในหน้าต่าง Chromium ผ่าน Playwright ระบุ "url"
13. "browser_snapshot" - อ่านข้อความและรายการ element ที่โต้ตอบได้จาก DOM; แต่ละรายการมี ref เช่น E0
14. "browser_click" - คลิก element ด้วย ref จาก snapshot (แนะนำ) หรือ CSS selector ที่มีหลักฐาน ระบุใน "selector"
15. "browser_fill" - กรอกช่องฟอร์มด้วย ref จาก snapshot (แนะนำ) หรือ CSS selector ระบุ "selector" และ "text"
16. "browser_press" - กดปุ่มใน element ด้วย ref จาก snapshot (แนะนำ) หรือ CSS selector ระบุ "selector" และ "key"
17. "basic_open_program" - เปิดโปรแกรมผ่าน Win → พิมพ์ชื่อ → Enter ระบุ "app_name"
18. "basic_minimize_all" - ย่อหน้าต่างทั้งหมด
19. "basic_restore_minimized" - คืนหน้าต่างที่ย่อไว้
20. "basic_switch_window" - สลับไปหน้าต่างก่อนหน้า
21. "basic_close_active_window" - ปิดหน้าต่างที่กำลังใช้งาน
22. "basic_open_file" - เปิดไฟล์/โฟลเดอร์ด้วยแอปเริ่มต้น ระบุ "file_path"
23. "basic_search_files" - ค้นหาชื่อไฟล์/โฟลเดอร์ในเครื่อง ระบุ "search_name" และ "search_root" (ไม่บังคับ)

เมื่อเป้าหมายเป็นเว็บไซต์ ให้ใช้ browser actions เพื่ออ่าน DOM และโต้ตอบกับ element โดยตรงก่อนใช้เมาส์จากภาพ
หลัง browser action ระบบจะแนบข้อความ DOM ล่าสุดในรอบถัดไป ใช้ ref เช่น E0 จาก snapshot ล่าสุดเป็น selector ได้โดยตรง; ห้ามเดา ref, selector หรือ URL ที่ไม่มีหลักฐานจากคำสั่ง/DOM
- หากงานของผู้ใช้ต้องเปิดหรือใช้งานเว็บไซต์ ให้เลือก browser_open เพื่อเปิด URL และ browser_snapshot เพื่ออ่านหน้า จากนั้นใช้ browser_click, browser_fill หรือ browser_press ตาม DOM
- ตลอดงานบนเว็บไซต์ ให้ใช้ Playwright/DOM เป็นวิธีหลัก และห้ามใช้ screenshot, พิกัดเมาส์, click, type หรือ hotkey เพื่อควบคุม element ในหน้าเว็บ
- ใช้การควบคุมหน้าจอด้วยภาพได้เฉพาะกรณีที่ Playwright เข้าถึงไม่ได้จริง เช่น dialog ของระบบปฏิบัติการ หรือเนื้อหาที่ไม่อยู่ใน DOM; หาก browser action ล้มเหลว ให้ตรวจ DOM/ผลลัพธ์และลองแก้ selector ก่อน
- ทำงานทีละ action แล้วตรวจข้อความ DOM ที่ได้กลับมาก่อนตัดสินใจขั้นถัดไป ห้ามสมมติว่าการนำทาง การคลิก หรือการส่งฟอร์มสำเร็จโดยไม่มีหลักฐาน

โครงสร้าง JSON ที่ต้องตอบกลับเท่านั้น:
{
  "thought": "อธิบายสิ่งที่เห็นบนจอ ตรวจสอบหน้าจอก่อนกด และเหตุผลในการเลือกใช้คีย์ลัดหรือเมาส์",
  "action": "press_key | hotkey | type | click | double_click | right_click | move | drag | scroll | browser_open | browser_snapshot | browser_click | browser_fill | browser_press | basic_open_program | basic_minimize_all | basic_restore_minimized | basic_switch_window | basic_close_active_window | basic_open_file | basic_search_files | wait | finish",
  "confirmed": true/false (ตั้ง true หลังตรวจปลายลูกศรเมาส์และยืนยันตำแหน่งคลิกหรือเลื่อนเท่านั้น),
  "grid_col": หมายเลขคอลัมน์กริดเริ่มจาก 0 หรือ null,
  "grid_row": หมายเลขแถวกริดเริ่มจาก 0 หรือ null,
  "offset_x": ตำแหน่งแนวนอนในช่องเป็นเปอร์เซ็นต์ 0-100 หรือ null,
  "offset_y": ตำแหน่งแนวตั้งในช่องเป็นเปอร์เซ็นต์ 0-100 หรือ null,
  "end_grid_col": หมายเลขคอลัมน์ปลายทาง drag หรือ null,
  "end_grid_row": หมายเลขแถวปลายทาง drag หรือ null,
  "end_offset_x": ตำแหน่งแนวนอนปลายทางในช่องเป็นเปอร์เซ็นต์ 0-100 หรือ null,
  "end_offset_y": ตำแหน่งแนวตั้งปลายทางในช่องเป็นเปอร์เซ็นต์ 0-100 หรือ null,
  "scroll_clicks": จำนวนคลิก scroll หรือ null,
  "key": "ชื่อปุ่ม (สำหรับ press_key เช่น 'win', 'enter') หรือ null",
  "text": "ข้อความที่พิมพ์ (สำหรับ type) หรือ null",
  "url": "URL (สำหรับ browser_open) หรือ null",
  "selector": "CSS selector (สำหรับ browser_click/browser_fill/browser_press) หรือ null",
  "app_name": "ชื่อโปรแกรมสำหรับ basic_open_program หรือ null",
  "file_path": "path ของไฟล์/โฟลเดอร์สำหรับ basic_open_file หรือ null",
  "search_name": "ชื่อหรือส่วนหนึ่งของชื่อไฟล์สำหรับ basic_search_files หรือ null",
  "search_root": "โฟลเดอร์เริ่มค้นหา (ไม่บังคับ; ค่าเริ่มต้นคือโฟลเดอร์ผู้ใช้) หรือ null",
  "keys": ["ปุ่ม1", "ปุ่ม2"] (สำหรับ hotkey) หรือ null,
  "wait_seconds": วินาทีที่รอ หรือ null,
  "done": true/false,
  "summary": "ข้อความสรุปสั้นๆ แจ้งความคืบหน้าหรือผลลัพธ์"
}
""".replace("__GRID_CELL_SIZE__", str(GRID_CELL_SIZE))


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
    click_confirmed: bool = False,
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

    if action in ("click", "double_click", "right_click"):
        if x is None or y is None:
            print("⚠️ ไม่กดเมาส์ เพราะคำสั่งไม่มีพิกัดเป้าหมายที่ตรวจสอบได้")
            return False
        mouse.move_to(x, y, duration=0.25)
        actual_x, actual_y = mouse.get_position()
        print(f"📍 ตำแหน่งเมาส์จริง: ({actual_x}, {actual_y})")
        if not click_confirmed:
            print("🔎 เลื่อนเมาส์ไปยังจุดเสนอแล้ว รอให้ AI ตรวจภาพยืนยันก่อนกด")
        elif abs(actual_x - x) <= 2 and abs(actual_y - y) <= 2:
            time.sleep(0.15)
            print(f"🖱️ AI ยืนยันตำแหน่งแล้ว กด {action} ที่ ({x}, {y})")
            if action == "click":
                mouse.click(x, y)
            elif action == "double_click":
                mouse.double_click(x, y)
            else:
                mouse.right_click(x, y)
        else:
            print("⚠️ ไม่กดเมาส์ เพราะตำแหน่งจริงไม่ตรงกับตำแหน่งเป้าหมาย")

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

    elif action.startswith("browser_"):
        try:
            if action == "browser_open":
                result = browser_tools.open_url(str(action_data.get("url", "")))
            elif action == "browser_snapshot":
                result = browser_tools.snapshot()
            elif action == "browser_click":
                result = browser_tools.click(str(action_data.get("selector", "")))
            elif action == "browser_fill":
                result = browser_tools.fill(str(action_data.get("selector", "")), str(action_data.get("text", "")))
            elif action == "browser_press":
                result = browser_tools.press(str(action_data.get("selector", "")), str(action_data.get("key", "Enter")))
            else:
                raise ValueError(f"ไม่รองรับ browser action: {action}")
            action_data["browser_result"] = result
            print(f"🌐 Playwright {action} สำเร็จ; อ่านข้อความ DOM ได้ {len(result)} ตัวอักษร")
        except Exception as exc:
            action_data["browser_result"] = f"Browser error: {exc}"
            action_data["browser_unavailable"] = isinstance(
                exc, browser_tools.BrowserUnavailableError
            )
            print(f"⚠️ Playwright ทำงานไม่สำเร็จ: {exc}")

    elif action.startswith("basic_"):
        try:
            if action == "basic_open_program":
                result = basic_functions.open_program(str(action_data.get("app_name", "")))
            elif action == "basic_minimize_all":
                result = basic_functions.minimize_all()
            elif action == "basic_restore_minimized":
                result = basic_functions.restore_minimized()
            elif action == "basic_switch_window":
                result = basic_functions.switch_window()
            elif action == "basic_close_active_window":
                result = basic_functions.close_active_window()
            elif action == "basic_open_file":
                result = basic_functions.open_file(str(action_data.get("file_path", "")))
            elif action == "basic_search_files":
                result = basic_functions.search_files(
                    str(action_data.get("search_name", "")),
                    str(action_data.get("search_root", "") or ""),
                )
            else:
                raise ValueError(f"ไม่รองรับ basic action: {action}")
            action_data["basic_result"] = result
            print(f"🧰 Basic action {action}: {result}")
        except Exception as exc:
            action_data["basic_result"] = f"Basic action error: {exc}"
            print(f"⚠️ Basic action ทำงานไม่สำเร็จ: {exc}")

    elif action == "wait":
        sec = float(action_data.get("wait_seconds", 1.0))
        time.sleep(sec)

    elif action == "finish":
        return True

    return done


CLICK_ACTIONS = {"click", "double_click", "right_click"}
ACTION_SETTLE_SECONDS = 2.0


def _grid_point_to_image(
    column: Any,
    row: Any,
    offset_x: Any,
    offset_y: Any,
    image_w: int,
    image_h: int,
) -> Optional[Tuple[int, int]]:
    """แปลงช่องกริดและตำแหน่งย่อย 0-100% เป็นพิกัดพิกเซลในภาพจริง"""
    try:
        column = int(column)
        row = int(row)
        offset_x = max(0.0, min(100.0, float(offset_x))) / 100.0
        offset_y = max(0.0, min(100.0, float(offset_y))) / 100.0
    except (TypeError, ValueError):
        return None

    if column < 0 or row < 0 or image_w <= 0 or image_h <= 0:
        return None
    left, top = column * GRID_CELL_SIZE, row * GRID_CELL_SIZE
    if left >= image_w or top >= image_h:
        return None
    cell_w = min(GRID_CELL_SIZE, image_w - left)
    cell_h = min(GRID_CELL_SIZE, image_h - top)
    return (
        min(image_w - 1, round(left + offset_x * (cell_w - 1))),
        min(image_h - 1, round(top + offset_y * (cell_h - 1))),
    )


def apply_grid_coordinates(action_data: Dict[str, Any], image_w: int, image_h: int) -> Dict[str, Any]:
    """แปลงพิกัดกริดที่ AI ส่งกลับเป็น x/y เดิม เพื่อใช้กับส่วนควบคุมเมาส์"""
    action_data = dict(action_data)
    for prefix, x_key, y_key in (("", "x", "y"), ("end_", "end_x", "end_y")):
        col_key = f"{prefix}grid_col"
        row_key = f"{prefix}grid_row"
        if col_key not in action_data and row_key not in action_data:
            # พิกัดเมาส์ต้องมาจากกริดเท่านั้น ไม่ใช้ x/y ที่ AI กะมาโดยตรง
            if action_data.get("action", "").lower() in CLICK_ACTIONS | {"move", "drag"}:
                action_data[x_key] = None
                action_data[y_key] = None
            continue
        point = _grid_point_to_image(
            action_data.get(col_key),
            action_data.get(row_key),
            action_data.get(f"{prefix}offset_x"),
            action_data.get(f"{prefix}offset_y"),
            image_w,
            image_h,
        )
        if point is None:
            action_data[x_key] = None
            action_data[y_key] = None
        else:
            action_data[x_key], action_data[y_key] = point
    return action_data


def _pending_pointer_from_position(
    action: str,
    screen_w: int,
    screen_h: int,
    image_w: int,
    image_h: int,
) -> Dict[str, Any]:
    """เก็บตำแหน่งเมาส์จริงและตำแหน่งเทียบกับภาพสำหรับรอบตรวจสอบ"""
    screen_x, screen_y = mouse.get_position()
    return {
        "action": action,
        "screen_x": screen_x,
        "screen_y": screen_y,
        "image_x": _map_image_coordinate(screen_x, screen_w, image_w),
        "image_y": _map_image_coordinate(screen_y, screen_h, image_h),
    }


def _matches_pending_pointer(
    action_data: Dict[str, Any],
    pending_click: Dict[str, Any],
    screen_w: int,
    screen_h: int,
    image_w: int,
    image_h: int,
) -> bool:
    x = _map_image_coordinate(action_data.get("x"), image_w, screen_w)
    y = _map_image_coordinate(action_data.get("y"), image_h, screen_h)
    return (
        x is not None
        and y is not None
        and abs(x - pending_click["screen_x"]) <= 4
        and abs(y - pending_click["screen_y"]) <= 4
    )


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


def prepare_image_part(
    image_path: str,
    pointer_marker: Optional[Tuple[int, int]] = None,
) -> types.Part:
    """
    อ่านภาพหน้าจอ วาดกริด และวาดเคอร์เซอร์เมาส์บนสำเนาภาพเมื่อตรวจสอบก่อนคลิก
    """
    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image, "RGBA")
    # Grid is drawn only onto the in-memory copy sent to the model.
    for x in range(0, image.width, GRID_CELL_SIZE):
        draw.line((x, 0, x, image.height - 1), fill=(255, 255, 255, 45), width=1)
        draw.rectangle((x + 2, 2, min(x + 28, image.width - 1), 18), fill=(15, 18, 24, 180))
        draw.text((x + 5, 4), str(x // GRID_CELL_SIZE), fill=(255, 235, 120, 255))
    for y in range(0, image.height, GRID_CELL_SIZE):
        draw.line((0, y, image.width - 1, y), fill=(255, 255, 255, 45), width=1)
        draw.rectangle((2, y + 2, min(28, image.width - 1), min(y + 18, image.height - 1)), fill=(15, 18, 24, 180))
        draw.text((5, y + 4), str(y // GRID_CELL_SIZE), fill=(255, 235, 120, 255))
    if pointer_marker is not None:
        x, y = pointer_marker
        x = max(0, min(image.width - 1, int(x)))
        y = max(0, min(image.height - 1, int(y)))
        # วาดลูกศรเมาส์แบบมาตรฐาน; ปลายซ้ายบน (x,y) คือ hotspot ที่ใช้คลิกจริง
        cursor = [
            (x, y), (x, y + 21), (x + 5, y + 16),
            (x + 10, y + 25), (x + 14, y + 23),
            (x + 9, y + 14), (x + 18, y + 14),
        ]
        shadow = [(px + 2, py + 2) for px, py in cursor]
        draw.polygon(shadow, fill=(0, 0, 0, 180))
        draw.polygon(cursor, fill=(255, 255, 255, 255), outline=(20, 24, 30, 255))
        draw.line(cursor + [cursor[0]], fill=(20, 24, 30, 255), width=2)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=95)
    data = buffer.getvalue()
    return types.Part.from_bytes(data=data, mime_type="image/jpeg")


def locate_target_in_cropped_screenshot(
    client,
    screenshot: Image.Image,
    goal: str,
) -> Optional[Tuple[int, int]]:
    """หาเป้าหมายจากภาพ 4 ส่วนที่ขยาย 2 เท่า แล้วแปลงกรอบกลับเป็นพิกัดภาพเต็ม"""
    image_w, image_h = screenshot.size
    mid_x, mid_y = image_w // 2, image_h // 2
    regions = {
        "A": (0, 0, mid_x, mid_y),
        "B": (mid_x, 0, image_w, mid_y),
        "C": (0, mid_y, mid_x, image_h),
        "D": (mid_x, mid_y, image_w, image_h),
    }
    contents = []
    for label, bounds in regions.items():
        crop = screenshot.crop(bounds)
        enlarged = crop.resize(
            (crop.width * 2, crop.height * 2), Image.Resampling.LANCZOS
        )
        buffer = io.BytesIO()
        enlarged.save(buffer, format="JPEG", quality=95)
        contents.extend([
            f"Region {label}",
            types.Part.from_bytes(data=buffer.getvalue(), mime_type="image/jpeg"),
        ])

    contents.append(f"""
เป้าหมายบนหน้าจอที่ผู้ใช้ต้องการ: "{goal}"
ภาพที่แนบมามี 4 ส่วนจากหน้าจอเดียวกัน ขยาย 2 เท่า: A=ซ้ายบน, B=ขวาบน, C=ซ้ายล่าง, D=ขวาล่าง
หาเป้าหมายจากสิ่งที่มองเห็นจริงเท่านั้น ถ้าเห็น ให้เลือก region และกรอบวัตถุ bbox_2d=[ymin,xmin,ymax,xmax] โดย normalize เป็น 0-1000 ภายในภาพ crop ที่เลือก
ถ้าไม่พบเป้าหมายอย่างชัดเจน ให้ตอบ found=false และ bbox_2d=null ห้ามเดาตำแหน่ง
ตอบ JSON เท่านั้น: {{"found":true/false,"region":"A|B|C|D|null","bbox_2d":[ymin,xmin,ymax,xmax] หรือ null,"reason":"หลักฐานสั้นๆ"}}
""")

    try:
        response = client.models.generate_content(
            model="gemini-flash-lite-latest",
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=(
                    "Locate the named target visually in the labeled image crops. "
                    "Return a crop-local bounding box normalized from 0 to 1000. "
                    "Do not infer a target that is not visible."
                ),
                response_mime_type="application/json",
                temperature=0.1,
            ),
        )
        result = json.loads(response.text or "{}")
    except Exception as exc:
        print(f"⚠️ Crop localization failed: {type(exc).__name__}: {exc}")
        return None

    if not isinstance(result, dict):
        print("⚠️ Crop localization คืนข้อมูล JSON ที่ไม่ถูกต้อง")
        return None

    label = result.get("region")
    box_2d = result.get("bbox_2d")
    if (
        result.get("found") is not True
        or not isinstance(label, str)
        or label not in regions
        or not isinstance(box_2d, list)
        or len(box_2d) != 4
    ):
        print(f"⚠️ ไม่พบเป้าหมายจากภาพ crop: {result.get('reason', 'ไม่มีกรอบตำแหน่งที่ใช้ได้')}")
        return None

    try:
        ymin, xmin, ymax, xmax = (float(value) for value in box_2d)
    except (TypeError, ValueError):
        print("⚠️ Crop localization คืนกรอบที่ไม่ใช่ตัวเลข")
        return None
    if not (0 <= ymin < ymax <= 1000 and 0 <= xmin < xmax <= 1000):
        print(f"⚠️ Crop localization คืนกรอบนอกช่วง 0-1000: {box_2d}")
        return None

    left, top, right, bottom = regions[label]
    center_x = (xmin + xmax) / 2000
    center_y = (ymin + ymax) / 2000
    image_x = left + round(center_x * (right - left - 1))
    image_y = top + round(center_y * (bottom - top - 1))
    print(
        f"🧩 Crop พบเป้าหมายในส่วน {label}, bbox={box_2d}; "
        f"พิกัดภาพเต็ม=({image_x}, {image_y})"
    )
    return image_x, image_y


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


def run_agent_loop(goal: str, max_steps: int = 20) -> str:
    """
    ลูปการทำงานหลัก: ถ่ายภาพหน้าจอ -> ส่งให้ Gemini -> ควบคุมเมาส์/คีย์บอร์ด -> ทำซ้ำจนเสร็จ
    """
    client = get_gemini_client()
    screen_w, screen_h = screen_capture.get_screen_resolution()
    history: List[str] = []
    final_summary = "ดำเนินการเสร็จสิ้นเรียบร้อยแล้วครับ"
    pending_click: Optional[Dict[str, Any]] = None
    pending_move: Optional[Dict[str, Any]] = None
    verification_attempts = 0
    max_verification_attempts = 3

    print(f"\n🚀 เริ่มต้นภารกิจ: '{goal}'")
    print(f"🖥️ ขนาดหน้าจอ: {screen_w} x {screen_h} พิกเซล (จำกัดสูงสุด {max_steps} ขั้นตอน)")

    screenshot_path = "current_screen.jpg"
    browser_context = "ยังไม่ได้เปิด Playwright browser session ในภารกิจนี้."
    basic_context = "ยังไม่มีผลลัพธ์จาก basic functions ในภารกิจนี้."

    for step in range(1, max_steps + 1):
        print(f"\n--- [ขั้นตอนที่ {step}/{max_steps}] ---")

        # 1. ถ่ายภาพหน้าจอแบบบีบอัด JPEG (ขนาดไฟล์ ~100KB ส่งไวมาก)
        print("📸 ถ่ายภาพหน้าจอปัจจุบัน...")
        # เพิ่มคุณภาพ JPEG เพื่อรักษาขอบปุ่มและไอคอนขนาดเล็กที่ AI ใช้กะพิกัด
        screenshot = screen_capture.capture_screen(save_path=screenshot_path, quality=90)
        image_w, image_h = screenshot.size
        pending_pointer = pending_click or pending_move
        pointer_marker = (pending_pointer["image_x"], pending_pointer["image_y"]) if pending_pointer else None
        img_part = prepare_image_part(screenshot_path, pointer_marker=pointer_marker)

        # 2. จัดเตรียม Prompt สำหรับ Gemini
        history_str = "\n".join([f"- {h}" for h in history]) if history else "ยังไม่มีการกระทำก่อนหน้านี้ (เพิ่งเริ่มต้น)"
        verification_prompt = ""
        if pending_pointer is not None:
            verification_kind = "ก่อนคลิก" if pending_click is not None else "ก่อนยืนยันว่าเลื่อนเมาส์สำเร็จ"
            verification_prompt = f"""

การตรวจตำแหน่ง{verification_kind} (สำคัญ):
- รูปลูกศรเมาส์ในภาพแสดงตำแหน่งเมาส์จริง ปลายลูกศรด้านซ้ายบนคือจุดชี้หรือจุดที่จะถูกกด
- จุดเมาส์ที่กำลังตรวจอยู่คือ ({pending_pointer['image_x']}, {pending_pointer['image_y']}) ในภาพ
- ตรวจจากภาพจริงว่าปลายลูกศรอยู่บนเป้าหมายที่ผู้ใช้ร้องขอหรือไม่ อย่าตัดสินจากประวัติหรือพิกัดที่ AI เคยเสนออย่างเดียว
- ถ้าตรงเป้าหมาย ให้ตอบ action "{pending_pointer['action']}" พร้อมข้อมูลกริดและ offset เดิม, "confirmed": true และ "done": true เมื่อภารกิจเสร็จ
- ถ้าไม่ตรงหรือไม่แน่ใจ ห้ามยืนยัน ให้ตอบ action "move" พร้อมพิกัดศูนย์กลางเป้าหมายที่ถูกต้อง และ "confirmed": false
- ระบบจะยังไม่คลิกหรือรายงานว่าเลื่อนสำเร็จจนกว่าจะตรวจภาพที่มีรูปลูกศรเมาส์
"""
        prompt = f"""
เป้าหมายของผู้ใช้ (User Goal): "{goal}"
ขนาดภาพที่แนบให้วิเคราะห์: กว้าง {image_w} x สูง {image_h} พิกเซล
ขนาดพิกัดเมาส์ของระบบ: กว้าง {screen_w} x สูง {screen_h} พิกเซล
ตารางมีช่องละ {GRID_CELL_SIZE}x{GRID_CELL_SIZE} พิกเซล เริ่มที่มุมซ้ายบน (0,0); ช่องขอบภาพอาจมีขนาดเล็กกว่า
ตอบตำแหน่งคลิก/เลื่อน/ลากด้วยหมายเลขช่องและ offset 0-100% เท่านั้น ระบบจะแปลงกลับเป็นพิกัดภาพ {image_w}x{image_h} และพิกัดเมาส์ให้อัตโนมัติ
ประวัติการกระทำก่อนหน้านี้:
{history_str}
ข้อความจาก DOM ของเว็บไซต์ (ถ้ามี):
{browser_context}
ผลลัพธ์จาก basic functions (ถ้ามี):
{basic_context}
{verification_prompt}

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
        action_data = apply_grid_coordinates(
            parse_ai_response(raw_text), image_w, image_h
        )
        if action_data.get("browser_result"):
            browser_context = str(action_data["browser_result"])
        thought = action_data.get("thought", "")
        summary = action_data.get("summary", "")
        print(f"💭 ความคิด AI: {thought}")
        if summary:
            print(f"📢 แจ้งสถานะ: {summary}")

        # 5. เลื่อนเมาส์ไปยังจุดเสนอ แล้วขอให้ AI ตรวจภาพซ้ำก่อนสั่งคลิกจริง
        action_name = action_data.get("action", "").lower()
        is_done = False
        if (
            pending_click is None
            and pending_move is None
            and action_name in CLICK_ACTIONS | {"move"}
        ):
            crop_point = locate_target_in_cropped_screenshot(client, screenshot, goal)
            if crop_point is None:
                final_summary = "ระบบหยุดโดยไม่ขยับเมาส์ เพราะหาเป้าหมายจากภาพ crop ไม่ได้อย่างมั่นใจ"
                print(f"⚠️ {final_summary}")
                break
            action_data["x"], action_data["y"] = crop_point

        if pending_click is None and pending_move is None and action_name in CLICK_ACTIONS:
            execute_action(action_data, screen_w, screen_h, image_w, image_h)
            if action_data.get("x") is not None and action_data.get("y") is not None:
                pending_click = _pending_pointer_from_position(
                    action_name, screen_w, screen_h, image_w, image_h
                )
                verification_attempts = 0
                print("🔎 ส่งภาพรอบถัดไปให้ AI ตรวจปลายลูกศรเมาส์ก่อนคลิก")
        elif pending_click is None and pending_move is None and action_name == "move":
            # อย่าเชื่อ done จากข้อเสนอเลื่อนครั้งแรก ต้องให้ AI ตรวจภาพที่มีลูกศรจริงก่อน
            execute_action(action_data, screen_w, screen_h, image_w, image_h)
            if action_data.get("x") is not None and action_data.get("y") is not None:
                pending_move = _pending_pointer_from_position(
                    "move", screen_w, screen_h, image_w, image_h
                )
                verification_attempts = 0
                print("🔎 ส่งภาพพร้อมลูกศรเมาส์ให้ AI ตรวจตำแหน่งก่อนรายงานว่าสำเร็จ")
        elif pending_move is not None:
            same_point = _matches_pending_pointer(
                action_data, pending_move, screen_w, screen_h, image_w, image_h
            )
            explicitly_confirmed = action_data.get("confirmed") is True
            # For a move confirmation, the screenshot describes the cursor's
            # current position. Ignore any newly proposed grid point when the AI
            # confirms that current cursor is already on target; otherwise a
            # center-of-cell coordinate can trigger an unnecessary second move.
            if action_name == "move" and explicitly_confirmed:
                pending_move = None
                verification_attempts = 0
                is_done = bool(action_data.get("done", False))
                print("✅ AI ยืนยันตำแหน่งเมาส์ปัจจุบันจากภาพ; คงพิกัดเดิม")
            elif action_name == "wait":
                execute_action(action_data, screen_w, screen_h, image_w, image_h)
                verification_attempts += 1
            elif action_name == "move":
                if same_point:
                    print("⚠️ AI ยังไม่ยืนยันตำแหน่งจากรูปลูกศร จึงยังไม่รายงานว่าสำเร็จ")
                elif action_data.get("x") is not None and action_data.get("y") is not None:
                    execute_action(action_data, screen_w, screen_h, image_w, image_h)
                    pending_move = _pending_pointer_from_position(
                        "move", screen_w, screen_h, image_w, image_h
                    )
                    print("🔁 เลื่อนไปพิกัดแก้ไข แล้วส่งภาพลูกศรให้ตรวจอีกครั้ง")
                verification_attempts += 1
            elif action_name in CLICK_ACTIONS:
                # ถ้า AI เปลี่ยนคำขอเป็นคลิก ให้เริ่มขั้นตอนยืนยันคลิกแยกต่างหาก
                pending_move = None
                verification_attempts = 0
                execute_action(action_data, screen_w, screen_h, image_w, image_h)
                if action_data.get("x") is not None and action_data.get("y") is not None:
                    pending_click = _pending_pointer_from_position(
                        action_name, screen_w, screen_h, image_w, image_h
                    )
            elif action_name == "finish":
                print("⚠️ AI ขอจบงานก่อนยืนยันตำแหน่งลูกศร จึงยังไม่รับรองผล")
                verification_attempts += 1
            else:
                pending_move = None
                verification_attempts = 0
                is_done = execute_action(action_data, screen_w, screen_h, image_w, image_h)
        elif pending_click is not None:
            same_point = _matches_pending_pointer(
                action_data, pending_click, screen_w, screen_h, image_w, image_h
            )
            explicitly_confirmed = action_data.get("confirmed") is True

            if (
                action_name == pending_click["action"]
                and same_point
                and explicitly_confirmed
            ):
                is_done = execute_action(
                    action_data,
                    screen_w,
                    screen_h,
                    image_w,
                    image_h,
                    click_confirmed=True,
                )
                pending_click = None
                verification_attempts = 0
            elif action_name == "wait":
                execute_action(action_data, screen_w, screen_h, image_w, image_h)
                verification_attempts += 1
            elif action_name in CLICK_ACTIONS or action_name == "move":
                if action_name == pending_click["action"] and same_point:
                    print("⚠️ AI ยังไม่ได้ยืนยันตำแหน่ง จึงไม่คลิกและจะขอตรวจซ้ำ")
                elif action_data.get("x") is not None and action_data.get("y") is not None:
                    correction = dict(action_data)
                    correction["action"] = "move"
                    correction["done"] = False
                    execute_action(correction, screen_w, screen_h, image_w, image_h)
                    pending_click = _pending_pointer_from_position(
                        pending_click["action"], screen_w, screen_h, image_w, image_h
                    )
                    print("🔁 ใช้พิกัดที่ AI แก้ไข แล้วจะตรวจภาพอีกครั้งก่อนคลิก")
                verification_attempts += 1
            else:
                # AI เปลี่ยนไปใช้คีย์บอร์ดหรือ action อื่น จึงยกเลิกคลิกที่ค้างไว้
                pending_click = None
                verification_attempts = 0
                is_done = execute_action(action_data, screen_w, screen_h, image_w, image_h)
        else:
            is_done = execute_action(action_data, screen_w, screen_h, image_w, image_h)

        if action_data.get("browser_unavailable"):
            final_summary = str(action_data.get("browser_result", "Playwright browser unavailable"))
            print(f"⚠️ {final_summary}")
            break

        if action_name.startswith("browser_") and action_data.get("browser_result"):
            browser_context = str(action_data["browser_result"])
        if action_name.startswith("basic_") and action_data.get("basic_result"):
            basic_context = str(action_data["basic_result"])

        if (pending_click is not None or pending_move is not None) and verification_attempts >= max_verification_attempts:
            final_summary = "ระบบยกเลิกการดำเนินการ เพราะ AI ยังยืนยันตำแหน่งจากภาพไม่ได้"
            print(f"⚠️ {final_summary}")
            history.append(f"Step {step}: ยกเลิกตำแหน่งเมาส์ที่ยังยืนยันไม่ได้")
            break

        # บันทึกประวัติ
        act_desc = f"Step {step}: {action_name} - {thought}"
        history.append(act_desc)

        # ตรวจสอบการเสร็จสิ้น
        if is_done:
            final_summary = summary or f"ดำเนินการ '{goal}' สำเร็จเรียบร้อยแล้วครับ"
            print(f"\n🎉 ภารกิจสำเร็จในขั้นตอนที่ {step}!")
            break

        # หน่วงเวลาสั้นๆ เพื่อให้หน้าจอแสดงผลการเปลี่ยนแปลงหลังคลิก
        time.sleep(ACTION_SETTLE_SECONDS)
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
    result_message = run_agent_loop(goal=command, max_steps=20)

    # เมื่อทำเสร็จ พูดตอบกลับมา
    print(f"\n🔊 รายงานผลลัพธ์ผ่านเสียง: '{result_message}'")
    speak(result_message)


if __name__ == "__main__":
    if "--console" in sys.argv:
        main()
    else:
        from widget import launch_widget

        launch_widget(
            run_agent=lambda goal: run_agent_loop(goal=goal, max_steps=20),
            listen_command=stt.listen_command,
            speak=speak,
            api_key_available=bool(os.environ.get("GEMINI_API_KEY")),
        )

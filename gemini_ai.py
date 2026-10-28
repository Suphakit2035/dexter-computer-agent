import os
import sys
from pathlib import Path
from typing import Union, List, Optional
from PIL import Image
from google import genai
from google.genai import types

# โหลดค่า Environment Variable จากไฟล์ .env (ถ้ามี)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ตั้งค่า stdout/stderr ให้รองรับ UTF-8 บน Windows console
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def get_gemini_client(api_key: Optional[str] = None) -> genai.Client:
    """
    สร้างและคืนค่า Gemini Client
    หากไม่ระบุ api_key จะดึงค่าจาก Environment Variable: GEMINI_API_KEY
    """
    key = api_key or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise ValueError(
            "ไม่พบ Gemini API Key กรุณาระบุผ่านพารามิเตอร์ api_key "
            "หรือตั้งค่า Environment Variable 'GEMINI_API_KEY'"
        )
    return genai.Client(
        api_key=key,
        http_options=types.HttpOptions(
            timeout=60_000,
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
    )


def _load_image(image_input: Union[str, Path, Image.Image]) -> Image.Image:
    """
    แปลง input ภาพให้อยู่ในรูปแบบ PIL Image
    รองรับทั้ง path ไฟล์ (str/Path) หรืออ็อบเจกต์ PIL.Image อยู่แล้ว
    """
    if isinstance(image_input, (str, Path)):
        img_path = Path(image_input)
        if not img_path.exists():
            raise FileNotFoundError(f"ไม่พบไฟล์ภาพที่พาธ: {img_path}")
        return Image.open(img_path)
    elif isinstance(image_input, Image.Image):
        return image_input
    else:
        raise TypeError(
            f"รูปแบบของภาพไม่ถูกต้อง: {type(image_input)} (รองรับเฉพาะ str path หรือ PIL Image)"
        )


def _safe_get_text(response) -> str:
    """ดึงข้อความจาก response อย่างปลอดภัย ป้องกันกรณีติด Safety Filter"""
    try:
        return response.text or ""
    except Exception:
        # ตรวจสอบเพิ่มเติมหากถูกบล็อกหรือไม่มี text คืนค่า
        if response.candidates:
            finish_reason = response.candidates[0].finish_reason
            return f"[ไม่สามารถแสดงผลได้: คำตอบถูกระงับเนื่องจากเหตุผล {finish_reason}]"
        return ""


def ask_gemini(
    prompt: str,
    image: Optional[Union[str, Path, Image.Image, List[Union[str, Path, Image.Image]]]] = None,
    model: str = "gemini-3.5-flash",  # แก้ไขชื่อโมเดลให้เป็นเวอร์ชันปัจจุบัน
    api_key: Optional[str] = None,
    system_instruction: Optional[str] = None,
    temperature: Optional[float] = None,
) -> str:
    """
    ฟังก์ชันส่งข้อความและ/หรือภาพไปยัง Gemini AI
    """
    client = get_gemini_client(api_key=api_key)

    config_args = {}
    if system_instruction:
        config_args["system_instruction"] = system_instruction
    if temperature is not None:
        config_args["temperature"] = temperature

    config = types.GenerateContentConfig(**config_args) if config_args else None

    contents = []

    if image is not None:
        if isinstance(image, (list, tuple)):
            for img in image:
                contents.append(_load_image(img))
        else:
            contents.append(_load_image(image))

    contents.append(prompt)

    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=config,
    )

    return _safe_get_text(response)


class GeminiAgent:
    """
    คลาสสำหรับจัดการการเชื่อมต่อ Gemini AI แบบนำ client มาใช้ซ้ำได้
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        default_model: str = "gemini-2.5-flash",  # แก้ไขชื่อโมเดลให้เป็นเวอร์ชันปัจจุบัน
        system_instruction: Optional[str] = None,
    ):
        self.client = get_gemini_client(api_key=api_key)
        self.default_model = default_model
        self.system_instruction = system_instruction

    def ask(
        self,
        prompt: str,
        image: Optional[Union[str, Path, Image.Image, List[Union[str, Path, Image.Image]]]] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """
        ส่งข้อความ/ภาพไปยัง Gemini ผ่าน Instance
        """
        target_model = model or self.default_model

        config_args = {}
        if self.system_instruction:
            config_args["system_instruction"] = self.system_instruction
        if temperature is not None:
            config_args["temperature"] = temperature

        config = types.GenerateContentConfig(**config_args) if config_args else None

        contents = []
        if image is not None:
            if isinstance(image, (list, tuple)):
                for img in image:
                    contents.append(_load_image(img))
            else:
                contents.append(_load_image(image))

        contents.append(prompt)

        response = self.client.models.generate_content(
            model=target_model,
            contents=contents,
            config=config,
        )
        return _safe_get_text(response)

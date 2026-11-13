import asyncio

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.requests import ClientDisconnect

from .ocr import InvalidImage, OcrTimeout, OcrUnavailable, decode_image, recognize

MAX_BYTES = 10 * 1024 * 1024
MEDIA_TYPES = {"image/jpeg", "image/png"}
app = FastAPI(title="MRZ Passport Scanner")
scan_slots = asyncio.Semaphore(2)


def failure(status_code: int, code: str, message: str):
    return JSONResponse(
        {"status": "error", "data": None, "mrz": None, "checks": {}, "dates": {},
         "errors": [{"code": code, "message": message}], "warnings": []},
        status_code=status_code,
        headers={"Cache-Control": "no-store"},
    )


def scan_image(content: bytes, media_type: str):
    return recognize(decode_image(content, media_type))


@app.post(
    "/api/passport/scan",
    openapi_extra={"requestBody": {"required": True, "content": {
        media_type: {"schema": {"type": "string", "format": "binary"}}
        for media_type in sorted(MEDIA_TYPES)
    }}},
)
async def scan_passport(request: Request):
    media_type = request.headers.get("content-type", "").partition(";")[0].strip().lower()
    if media_type not in MEDIA_TYPES:
        return failure(415, "UNSUPPORTED_IMAGE", "รองรับเฉพาะไฟล์ JPEG และ PNG")

    if scan_slots.locked():
        return failure(503, "SCANNER_BUSY", "กำลังประมวลผลภาพอื่น กรุณาลองใหม่")
    async with scan_slots:
        image = bytearray()
        try:
            async with asyncio.timeout(15):
                async for chunk in request.stream():
                    if len(image) + len(chunk) > MAX_BYTES:
                        return failure(413, "IMAGE_TOO_LARGE", "ขนาดไฟล์ต้องไม่เกิน 10 MiB")
                    image.extend(chunk)
        except (ClientDisconnect, TimeoutError):
            return failure(408, "UPLOAD_INTERRUPTED", "อัปโหลดภาพไม่เสร็จ กรุณาลองใหม่")

        try:
            result = await asyncio.to_thread(scan_image, bytes(image), media_type)
        except InvalidImage:
            return failure(422, "INVALID_IMAGE", "เปิดภาพไม่ได้ ชนิดไฟล์ไม่ตรง หรือขนาดภาพอยู่นอกช่วงที่รองรับ")
        except OcrUnavailable:
            return failure(503, "OCR_UNAVAILABLE", "เรียกใช้ Tesseract ไม่ได้ กรุณาตรวจสอบการติดตั้งและโมเดล ocrb")
        except OcrTimeout:
            return failure(504, "OCR_TIMEOUT", "OCR ใช้เวลานานเกินกำหนด กรุณาลองใช้ภาพที่ชัดขึ้น")
        if result is None:
            return failure(422, "MRZ_NOT_READABLE", "อ่าน MRZ รูปแบบ TD3 ไม่ได้ กรุณาถ่ายใหม่ให้เห็นทั้งสองบรรทัดอย่างคมชัด")
        return JSONResponse(result, headers={"Cache-Control": "no-store"})

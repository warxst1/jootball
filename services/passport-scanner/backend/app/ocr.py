import os
import re
import subprocess
import time
from io import BytesIO
from itertools import pairwise

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from .mrz import parse_td3

MAX_PIXELS = 24_000_000


class InvalidImage(ValueError):
    pass


class OcrUnavailable(RuntimeError):
    pass


class OcrTimeout(RuntimeError):
    pass


def decode_image(content: bytes, media_type: str) -> np.ndarray:
    try:
        with Image.open(BytesIO(content)) as image:
            if image.format != {"image/jpeg": "JPEG", "image/png": "PNG"}[media_type]:
                raise InvalidImage
            if image.width * image.height > MAX_PIXELS or min(image.size) < 40:
                raise InvalidImage
            image = ImageOps.exif_transpose(image).convert("RGBA")
            white = Image.new("RGBA", image.size, "white")
            gray = np.asarray(Image.alpha_composite(white, image).convert("L"))
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as error:
        raise InvalidImage from error

    scale = min(1, 2200 / max(gray.shape))
    height, width = gray.shape
    size = (max(1, round(width * scale)), max(1, round(height * scale)))
    return cv2.resize(gray, size, interpolation=cv2.INTER_AREA)


def mrz_regions(gray: np.ndarray):
    height, width = gray.shape
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(9, width // 42), 5))
    blackhat = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, kernel)
    gradient = cv2.convertScaleAbs(cv2.Sobel(blackhat, cv2.CV_32F, 1, 0, ksize=3))
    merged = cv2.morphologyEx(gradient, cv2.MORPH_CLOSE, kernel)
    _, mask = cv2.threshold(merged, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((max(5, height // 36), 5), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = [cv2.boundingRect(contour) for contour in contours]
    for x, y, w, h in sorted(boxes, key=lambda box: box[2], reverse=True)[:4]:
        if w < width * 0.40 or w < 4 * h:
            continue
        pad_x = max(12, w // 30)
        pad_y = max(h, height // 30)
        yield gray[max(0, y - pad_y):y + h + pad_y, max(0, x - pad_x):x + w + pad_x]

    yield gray[height * 3 // 5:]
    yield gray


def parse_ocr_lines(first: str, second: str) -> dict | None:
    parsed = parse_td3(first, second)
    if parsed is not None or len(first) != 44 or len(second) != 44:
        return parsed

    # These fixed positions contain country codes and cannot contain digits.
    upper = first[:2] + first[2:5].replace("0", "O") + first[5:]
    lower = second[:10] + second[10:13].replace("0", "O") + second[13:]
    parsed = parse_td3(upper, lower)
    if parsed is not None:
        parsed["ocr_mrz"] = [first, second]
        parsed["warnings"].append({"code": "OCR_COUNTRY_CODE_NORMALIZED"})
    return parsed


def recognize(gray: np.ndarray) -> dict | None:
    executable = os.environ.get("TESSERACT_CMD") or "tesseract"
    deadline = time.monotonic() + 20
    best = None
    best_score = -1
    completed_attempt = False
    for region in mrz_regions(gray):
        height, width = region.shape
        scale = min(3, max(1, 1500 / width), 2400 / max(height, width))
        normalized = cv2.resize(region, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        normalized = cv2.copyMakeBorder(normalized, 16, 16, 16, 16, cv2.BORDER_CONSTANT, value=255)
        _, encoded = cv2.imencode(".png", normalized)
        for mode in ("6", "11"):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                if completed_attempt:
                    return best
                raise OcrTimeout
            try:
                completed = subprocess.run(
                    [executable, "stdin", "stdout", "-l", "ocrb", "--psm", mode, "-c",
                     "tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<"],
                    input=encoded.tobytes(), capture_output=True, timeout=min(5, remaining), check=True,
                )
            except subprocess.TimeoutExpired:
                continue
            except (OSError, subprocess.CalledProcessError) as error:
                raise OcrUnavailable from error

            completed_attempt = True
            lines = [
                re.sub(r"[ \t]+", "", line)
                for line in completed.stdout.decode("ascii", errors="replace").splitlines()
                if line.strip()
            ]
            for first, second in pairwise(lines):
                parsed = parse_ocr_lines(first, second)
                if parsed is None:
                    continue
                score = sum(check["status"] == "PASS" for check in parsed["checks"].values())
                if score > best_score:
                    best, best_score = parsed, score
                if not parsed["errors"]:
                    return parsed
    if not completed_attempt:
        raise OcrTimeout
    return best

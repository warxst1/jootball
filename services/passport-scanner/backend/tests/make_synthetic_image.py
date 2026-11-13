import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .test_mrz import FIRST, SECOND


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Render synthetic TD3 text for an OCR smoke test")
    parser.add_argument("--font", default="C:/Windows/Fonts/consola.ttf")
    parser.add_argument("--output", type=Path, default=Path("synthetic-passport.png"))
    args = parser.parse_args()

    image = Image.new("RGB", (1500, 900), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(args.font, 46)
    draw.text((85, 85), "SYNTHETIC OCR TEST", font=font, fill="black")
    draw.text((85, 710), FIRST, font=font, fill="black")
    draw.text((85, 772), SECOND, font=font, fill="black")
    image.save(args.output)

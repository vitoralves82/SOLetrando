"""
Gera o icone do Soletrando (assets/icon.ico)
Letra "S" em circulo verde (#00C853) com fundo transparente.
Tamanhos: 16x16, 32x32, 48x48, 64x64, 128x128, 256x256
"""

import os
from PIL import Image, ImageDraw, ImageFont

sizes = [16, 32, 48, 64, 128, 256]
images = []

for size in sizes:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    margin = max(1, size // 16)
    draw.ellipse([margin, margin, size - margin, size - margin], fill="#00C853")
    try:
        font = ImageFont.truetype("arial.ttf", int(size * 0.55))
    except Exception:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), "S", font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((size - tw) // 2, (size - th) // 2 - margin), "S", fill="white", font=font)
    images.append(img)

os.makedirs("assets", exist_ok=True)
images[-1].save(
    "assets/icon.ico",
    format="ICO",
    sizes=[(s, s) for s in sizes],
    append_images=images[:-1],
)
print("[OK] assets/icon.ico gerado com sucesso")

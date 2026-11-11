"""Sprite preparation helpers shared by the Qt UI (PIL side, no Tk)."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageOps


def round_card_image(pil_img: Image.Image, target_box: int, radius: int = 28) -> Image.Image:
    contained = ImageOps.fit(
        pil_img.convert("RGBA"),
        (target_box, target_box),
        method=Image.Resampling.LANCZOS,
    )
    mask = Image.new("L", (target_box * 2, target_box * 2), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle(
        (0, 0, target_box * 2 - 1, target_box * 2 - 1),
        radius=radius * 2,
        fill=255,
    )
    mask = mask.resize((target_box, target_box), Image.Resampling.LANCZOS)
    out = Image.new("RGBA", (target_box, target_box), (0, 0, 0, 0))
    out.paste(contained, (0, 0), mask)
    return out


def prepare_sprite_rgba(path: Path, box_size: int = 560) -> Image.Image:
    with Image.open(path) as raw:
        raw.load()
        oriented = ImageOps.exif_transpose(raw).convert("RGBA")

    alpha = oriented.getchannel("A")
    min_alpha, _ = alpha.getextrema()
    if min_alpha > 240:
        inner = int(box_size * 0.84)
        framed = round_card_image(oriented, inner, radius=32)
        canvas = Image.new("RGBA", (box_size, box_size), (0, 0, 0, 0))
        offset = (box_size - inner) // 2
        canvas.paste(framed, (offset, offset), framed)
        return canvas

    bbox = oriented.getbbox()
    if bbox:
        oriented = oriented.crop(bbox)
    max_inner = int(box_size * 0.90)
    w, h = oriented.size
    scale = min(max_inner / max(w, 1), max_inner / max(h, 1))
    nw = max(1, int(round(w * scale)))
    nh = max(1, int(round(h * scale)))
    resized = oriented.resize((nw, nh), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (box_size, box_size), (0, 0, 0, 0))
    canvas.paste(resized, ((box_size - nw) // 2, (box_size - nh) // 2), resized)
    return canvas


def create_soft_shadow(width: int, height: int, alpha_max: int = 44) -> Image.Image:
    scale = 2
    img = Image.new("RGBA", (width * scale, height * scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    pad_x = int(width * scale * 0.14)
    pad_y = int(height * scale * 0.20)
    draw.ellipse(
        (pad_x, pad_y, width * scale - pad_x, height * scale - pad_y),
        fill=(28, 22, 18, alpha_max),
    )
    img = img.filter(ImageFilter.GaussianBlur(radius=9))
    return img.resize((width, height), Image.Resampling.LANCZOS)
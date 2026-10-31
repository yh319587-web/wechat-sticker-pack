# -*- coding: utf-8 -*-
"""给横幅左侧加专辑名标题。产物只用于对外宣传，不要放进投稿包。

用法：
    python scripts/banner_title.py --banner 02_导出/banner.png --title 喵庭小记 --subtitle 橘子篇
    python scripts/banner_title.py --banner b.png --title 某某 --out 04_宣传图/横幅-标题版.png
"""
import argparse
import os
import sys

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
except ImportError:
    sys.exit("缺少依赖：pip install pillow")

SUPER = 4  # 超采样倍数
FILL = (255, 248, 230)
HALO = (255, 253, 247)
RING = (78, 98, 43)
SUB_COLOR = (92, 72, 42)

TITLE_FONTS = [
    "assets/fonts/ZCOOLKuaiLe.ttf",
    "fonts/ZCOOLKuaiLe.ttf",
    r"C:\Windows\Fonts\ZCOOL KuaiLe.ttf",
    "/Library/Fonts/ZCOOLKuaiLe-Regular.ttf",
]
SUB_FONTS = [
    r"C:\Windows\Fonts\Noto Sans SC Bold (TrueType).otf",
    r"C:\Windows\Fonts\msyhbd.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
]


def pick(cands):
    for p in cands:
        if os.path.exists(p):
            return p
    return None


def glyph(ch, font_path, size, ring_w=5.5, halo_w=1.5, fat=0.0):
    font = ImageFont.truetype(font_path, size * SUPER)
    pad = int((ring_w + 7) * SUPER)
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    bb = probe.textbbox((0, 0), ch, font=font, stroke_width=int(ring_w * SUPER))
    w = bb[2] - bb[0] + pad * 2
    h = bb[3] - bb[1] + pad * 2
    org = (pad - bb[0], pad - bb[1])

    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.text(org, ch, font=font, fill=RING, stroke_width=int(ring_w * SUPER), stroke_fill=RING)
    d.text(org, ch, font=font, fill=HALO, stroke_width=int(halo_w * SUPER), stroke_fill=HALO)
    d.text(org, ch, font=font, fill=FILL, stroke_width=int(fat * SUPER), stroke_fill=FILL)
    layer = layer.resize((w // SUPER, h // SUPER), Image.LANCZOS)
    return layer.crop(layer.getbbox())


def title_block(text, font_path, size=68, tracking=-1):
    glyphs = [glyph(c, font_path, size) for c in text]
    width = sum(g.width for g in glyphs) + tracking * (len(glyphs) - 1)
    height = max(g.height for g in glyphs)

    core = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    x = 0
    for g in glyphs:
        core.alpha_composite(g, (x, (height - g.height) // 2))
        x += g.width + tracking

    shadow = Image.new("RGBA", (width + 24, height + 24), (0, 0, 0, 0))
    sil = Image.new("RGBA", (width, height), (0, 0, 0, 70))
    sil.putalpha(core.getchannel("A").point(lambda v: int(v * 0.4)))
    shadow.alpha_composite(sil, (8, 8))
    shadow = shadow.filter(ImageFilter.GaussianBlur(5))

    block = Image.new("RGBA", (width + 24, height + 24), (0, 0, 0, 0))
    block.alpha_composite(shadow, (1, 2))
    block.alpha_composite(core, (8, 8))
    return block


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--banner", required=True)
    ap.add_argument("--title", default="某某")
    ap.add_argument("--subtitle", default="")
    ap.add_argument("--out", default="04_宣传图/横幅-标题版.png")
    ap.add_argument("--font", default=None)
    ap.add_argument("--size", type=int, default=68)
    ap.add_argument("--x", type=int, default=24)
    ap.add_argument("--y", type=int, default=114)
    args = ap.parse_args()

    title_font = args.font or pick(TITLE_FONTS)
    if not title_font:
        sys.exit("找不到标题字体，用 --font 指定（推荐站酷快乐体，免费商用）")

    canvas = Image.open(args.banner).convert("RGBA")
    block = title_block(args.title, title_font, args.size)
    canvas.alpha_composite(block, (args.x, args.y))

    if args.subtitle:
        sub_font = pick(SUB_FONTS)
        if sub_font:
            try:
                font = ImageFont.truetype(sub_font, max(18, args.size // 2))
                ImageDraw.Draw(canvas).text(
                    (args.x + 30, args.y + block.height - 15),
                    "· " + args.subtitle,
                    font=font,
                    fill=SUB_COLOR + (255,),
                )
            except OSError:
                print("[warn] 副标题字体不可用，已跳过")
        else:
            print("[warn] 找不到副标题字体，已跳过")

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    canvas.convert("RGB").save(args.out, optimize=True)
    print("saved {} {} {:.0f}KB".format(args.out, canvas.size, os.path.getsize(args.out) / 1024))


if __name__ == "__main__":
    main()

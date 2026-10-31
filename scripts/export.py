# -*- coding: utf-8 -*-
"""把 raw/ 里的原图导出成微信要求的全套素材。

用法：
    python scripts/export.py --plan plan.json
    python scripts/export.py --plan plan.json --no-text
"""
import argparse
import json
import os
import shutil
import sys

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
except ImportError:
    sys.exit("缺少依赖：pip install pillow")


def load_raw(raw_dir, sid):
    path = os.path.join(raw_dir, str(sid) + ".png")
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    im = Image.open(path).convert("RGBA")
    bbox = im.getbbox()
    return im.crop(bbox) if bbox else im


def place(im, W, fit_w, fit_h, top):
    s = min(fit_h / im.height, fit_w / im.width)
    im = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)
    canvas = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    canvas.paste(im, ((W - im.width) // 2, top), im)
    return canvas


def white_stroke(im, radius, color=(255, 255, 255)):
    if radius <= 0:
        return im
    alpha = im.getchannel("A").filter(ImageFilter.MaxFilter(radius * 2 + 1))
    out = Image.new("RGBA", im.size, color + (0,))
    out.putalpha(alpha)
    out.paste(im, (0, 0), im)
    return out


def draw_label(canvas, text, cfg, W):
    font_path = cfg.get("font")
    if not text or not font_path or not os.path.exists(font_path):
        if text:
            print("[warn] 字体缺失，跳过叠字：{}".format(font_path))
        return canvas
    size = int(cfg.get("size", 42))
    max_w = int(cfg.get("max_width", W - 52))
    min_size = int(cfg.get("min_size", 20))
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    font = ImageFont.truetype(font_path, size)
    while size > min_size:
        l, t, r, b = d.textbbox((0, 0), text, font=font)
        if r - l <= max_w:
            break
        size -= 2
        font = ImageFont.truetype(font_path, size)
    l, t, r, b = d.textbbox((0, 0), text, font=font)
    baseline = int(cfg.get("baseline", W - 18))
    x = (W - (r - l)) / 2 - l
    d.text(
        (x, baseline - b),
        text,
        font=font,
        fill=tuple(cfg.get("color", (74, 52, 42, 255))),
        stroke_width=int(cfg.get("stroke_width", 3)),
        stroke_fill=tuple(cfg.get("stroke", (255, 246, 230, 255))),
    )
    return Image.alpha_composite(canvas, layer)


def make_paper(w, h, base=(249, 240, 224)):
    bg = Image.new("RGBA", (w, h), tuple(base) + (255,))
    dots = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(dots)
    blobs = [
        (0.16, 0.24, 0.34, (242, 196, 136, 130)),
        (0.52, 0.82, 0.40, (246, 210, 160, 110)),
        (0.90, 0.18, 0.30, (236, 182, 124, 120)),
        (0.34, 0.60, 0.26, (250, 224, 186, 100)),
    ]
    for cx, cy, rr, col in blobs:
        d.ellipse([(cx - rr) * w, (cy - rr) * h, (cx + rr) * w, (cy + rr) * h], fill=col)
    dots = dots.filter(ImageFilter.GaussianBlur(max(w, h) // 12))
    return Image.alpha_composite(bg, dots)


def paste_fit(bg, im, cx, cy, max_h):
    im = im.crop(im.getbbox())
    s = max_h / im.height
    im = im.resize((max(1, round(im.width * s)), max_h), Image.LANCZOS)
    bg.paste(im, (round(cx - im.width / 2), round(cy - im.height / 2)), im)
    return bg


def head_crop(canvas, zoom, dy=0.03):
    """按头部比例裁方形图标：宽度取角色宽 0.68、高度取 0.62，向下偏移一点带上下巴。"""
    bbox = canvas.getbbox()
    if not bbox:
        return canvas
    x0, y0, x1, y1 = bbox
    side = int(min((x1 - x0) * 0.68, (y1 - y0) * 0.62) * zoom)
    cx = (x0 + x1) // 2
    top = y0 + int((y1 - y0) * dy)
    top = max(0, min(top, canvas.height - side))
    left = max(0, min(cx - side // 2, canvas.width - side))
    return canvas.crop((left, top, left + side, top + side))


def main():
    ap = argparse.ArgumentParser(description="导出微信表情包全套素材")
    ap.add_argument("--plan", default="plan.json")
    ap.add_argument("--raw", default="raw")
    ap.add_argument("--out", help="输出目录，默认 <ip>-<album>")
    ap.add_argument("--no-text", action="store_true", help="不叠文字")
    args = ap.parse_args()

    with open(args.plan, "r", encoding="utf-8") as fh:
        plan = json.load(fh)

    style = plan.get("style", {})
    text_cfg = dict(style.get("text") or {})
    W = int(style.get("size", 240))
    fit_w = int(style.get("fit_width", W - 28))
    fit_h = int(style.get("fit_height", W - 72))
    top = int(style.get("top", 10))
    radius = int((style.get("stroke") or {}).get("width", 2))
    icon_zoom = float(style.get("icon_zoom", 1.0))
    paper = tuple(style.get("paper", (249, 240, 224)))

    ip = plan.get("ip", "IP")
    album = plan.get("album", "日常")
    base_dir = args.out or "{}-{}".format(ip, album)
    dirs = {
        "src": os.path.join(base_dir, "01_源文件"),
        "main": os.path.join(base_dir, "02_导出", "main"),
        "thumb": os.path.join(base_dir, "02_导出", "thumb"),
        "export": os.path.join(base_dir, "02_导出"),
        "pack": os.path.join(base_dir, "03_投稿包"),
        "promo": os.path.join(base_dir, "04_宣传图"),
    }
    for path in dirs.values():
        os.makedirs(path, exist_ok=True)

    stickers = plan["stickers"]
    margins = []
    for st in stickers:
        sid = str(st["id"])
        im = load_raw(args.raw, sid)
        base = place(im, W, fit_w, fit_h, top)

        label = "" if args.no_text else (st.get("label") or "")
        with_text = draw_label(base, label, text_cfg, W)
        main_img = white_stroke(with_text, radius)
        main_img.save(os.path.join(dirs["main"], sid + ".png"), optimize=True)
        main_img.save(os.path.join(dirs["pack"], sid + ".png"), optimize=True)

        thumb = with_text.resize((W // 2, W // 2), Image.LANCZOS)
        thumb.save(os.path.join(dirs["thumb"], sid + ".png"), optimize=True)
        thumb.save(os.path.join(dirs["pack"], sid + "_t.png"), optimize=True)

        bbox = base.getbbox()
        margins.append((sid, bbox[0], bbox[1], W - bbox[2], W - bbox[3]))

        shutil.copyfile(
            os.path.join(args.raw, sid + ".png"),
            os.path.join(dirs["src"], "{}-{}-原图.png".format(ip, sid)),
        )

    cover_id = str(plan.get("cover") or stickers[0]["id"])
    cover = place(load_raw(args.raw, cover_id), W, fit_w, fit_h, top)
    if plan.get("cover_text") and not args.no_text:
        label = next((s.get("label") for s in stickers if str(s["id"]) == cover_id), "")
        cover = draw_label(cover, label, text_cfg, W)
    cover.save(os.path.join(dirs["export"], "cover.png"), optimize=True)
    cover.save(os.path.join(dirs["pack"], "cover.png"), optimize=True)

    icon_id = str(plan.get("icon") or cover_id)
    icon_src = place(load_raw(args.raw, icon_id), W, fit_w, fit_h, top)
    icon = head_crop(icon_src, icon_zoom, float(style.get("icon_top_offset", 0.03))).resize((50, 50), Image.LANCZOS)
    icon.save(os.path.join(dirs["export"], "icon.png"), optimize=True)
    icon.save(os.path.join(dirs["pack"], "icon.png"), optimize=True)

    banner = make_paper(750, 400, paper)
    paste_fit(banner, load_raw(args.raw, str(plan.get("banner_from") or cover_id)), 375, 200, 330)
    banner.convert("RGB").save(os.path.join(dirs["export"], "banner.png"), optimize=True)
    banner.convert("RGB").save(os.path.join(dirs["pack"], "banner.png"), optimize=True)

    if plan.get("reward", True):
        guide = make_paper(750, 560, paper)
        paste_fit(guide, load_raw(args.raw, str(plan.get("guide_from") or cover_id)), 375, 290, 430)
        guide.convert("RGB").save(os.path.join(dirs["export"], "reward_guide.png"), optimize=True)

        thanks = make_paper(750, 750, paper)
        paste_fit(thanks, load_raw(args.raw, str(plan.get("thanks_from") or cover_id)), 375, 400, 500)
        thanks.convert("RGB").save(os.path.join(dirs["export"], "reward_thanks.png"), optimize=True)

    write_readme(dirs["pack"], plan)

    min_margin = min(min(m[1], m[2], m[3], m[4]) for m in margins)
    biggest = max(os.path.getsize(os.path.join(dirs["main"], f)) for f in os.listdir(dirs["main"]))
    print("输出目录：{}".format(os.path.abspath(base_dir)))
    print("最小安全区：{}px（内控 ≥12px）".format(min_margin))
    print("最大主图：{}KB（内控 ≤400KB）".format(biggest // 1024))
    if min_margin < 12:
        print("! 安全区不足，调小 style.fit_width / fit_height 或增大 style.top")
    if biggest > 400 * 1024:
        print("! 主图超内控线，检查图像复杂度或文字描边宽度")


def write_readme(pack_dir, plan):
    lines = [
        "# 投稿说明",
        "",
        "专辑：{}".format(plan.get("album_full") or "{}-{}".format(plan.get("ip", ""), plan.get("album", ""))),
        "模式：{}".format("加道具 props" if plan.get("style", {}).get("mode") == "props" else "纯表情 plain"),
        "张数：{}".format(len(plan["stickers"])),
        "",
        "## 上传顺序",
        "",
        "1. 详情页横幅 `banner.png`（750×400，无文字）",
        "2. 封面 `cover.png`（240×240，透明、无白描边）",
        "3. 图标 `icon.png`（50×50，透明、无白描边）",
        "4. 主图 + 缩略图：`01.png` + `01_t.png` …",
        "5. 逐张填写含义词",
        "",
        "## 含义词",
        "",
        "| 编号 | 含义词 | 画面 |",
        "| --- | --- | --- |",
    ]
    for st in plan["stickers"]:
        lines.append("| {} | {} | {} |".format(
            st["id"], st.get("label") or st.get("name", ""), st.get("name", "")))
    lines += [
        "",
        "## 提醒",
        "",
        "- 缩略图、封面、图标不能再有白描边。",
        "- 横幅不得出现任何文字，带标题的版本在 `04_宣传图/`。",
        "- 含义词每张不超过 4 字、同套不重复。",
    ]
    with open(os.path.join(pack_dir, "README-投稿说明.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()

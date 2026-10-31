# -*- coding: utf-8 -*-
"""校验投稿包是否满足微信硬指标。

用法：
    python scripts/check.py --pack 喵庭小记-xxx/03_投稿包
"""
import argparse
import os
import re
import sys

try:
    from PIL import Image
except ImportError:
    sys.exit("缺少依赖：pip install pillow")

KB = 1024
RULES = {
    "main": (240, 240, 400 * KB),
    "thumb": (120, 120, 100 * KB),
    "cover": (240, 240, 200 * KB),
    "icon": (50, 50, 50 * KB),
    "banner": (750, 400, 300 * KB),
    "reward_guide": (750, 560, 300 * KB),
    "reward_thanks": (750, 750, 300 * KB),
}

ok_count = 0
bad_count = 0


def report(name, ok, detail):
    global ok_count, bad_count
    if ok:
        ok_count += 1
        print("  [ok]   {:<16} {}".format(name, detail))
    else:
        bad_count += 1
        print("  [fail] {:<16} {}".format(name, detail))


def check_image(path, name, size, limit, need_alpha, opaque=False, edge_check=True):
    if not os.path.exists(path):
        report(name, False, "文件不存在：" + os.path.basename(path))
        return
    with Image.open(path) as im:
        w, h = im.size
        mode = im.mode
        has_alpha = mode in ("RGBA", "LA") or (mode == "P" and "transparency" in im.info)
        kb = os.path.getsize(path) / KB
        problems = []
        if (w, h) != size:
            problems.append("尺寸 {}×{} ≠ {}×{}".format(w, h, size[0], size[1]))
        if kb > limit / KB:
            problems.append("体积 {:.0f}KB > {}KB".format(kb, limit // KB))
        if need_alpha and not has_alpha:
            problems.append("缺透明通道")
        if opaque and has_alpha:
            alpha = im.convert("RGBA").getchannel("A")
            if alpha.getextrema()[0] < 255:
                problems.append("有透明区域，横幅/赞赏图必须不透明")
        if need_alpha and has_alpha and edge_check:
            alpha = im.convert("RGBA").getchannel("A")
            edge = []
            edge += list(alpha.crop((0, 0, w, 1)).getdata())
            edge += list(alpha.crop((0, h - 1, w, h)).getdata())
            edge += list(alpha.crop((0, 0, 1, h)).getdata())
            edge += list(alpha.crop((w - 1, 0, w, h)).getdata())
            if max(edge) > 8:
                problems.append("有内容贴边（四周须全透明）")
        if not opaque and im.convert("RGBA").getchannel("A").getextrema()[1] == 0:
            problems.append("全透明，图是空的")
        report(name, not problems, "{}×{} {:.0f}KB  {}".format(w, h, kb, mode) if not problems else "；".join(problems))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", required=True)
    args = ap.parse_args()
    pack = args.pack
    if not os.path.isdir(pack):
        sys.exit("目录不存在：" + pack)

    files = os.listdir(pack)
    mains = sorted(f for f in files if re.fullmatch(r"\d{2}\.png", f))
    thumbs = sorted(f for f in files if re.fullmatch(r"\d{2}_t\.png", f))

    print("\n[1] 主图")
    if len(mains) not in (8, 16, 24):
        report("主图数量", False, "{} 张，只能是 8 / 16 / 24".format(len(mains)))
    else:
        report("主图数量", True, "{} 张".format(len(mains)))
    for f in mains:
        check_image(os.path.join(pack, f), f, RULES["main"][:2], RULES["main"][2], True)

    print("\n[2] 缩略图")
    ids_main = [f[:2] for f in mains]
    ids_thumb = [f[:2] for f in thumbs]
    if ids_main != ids_thumb:
        report("编号对应", False, "主图 {} / 缩略图 {}".format(",".join(ids_main), ",".join(ids_thumb)))
    else:
        report("编号对应", True, "{} 组一一对应".format(len(ids_main)))
    for f in thumbs:
        check_image(os.path.join(pack, f), f, RULES["thumb"][:2], RULES["thumb"][2], True)

    print("\n[3] 封面 / 图标")
    check_image(os.path.join(pack, "cover.png"), "cover.png", RULES["cover"][:2], RULES["cover"][2], True)
    check_image(os.path.join(pack, "icon.png"), "icon.png", RULES["icon"][:2], RULES["icon"][2], True, edge_check=False)

    print("\n[4] 横幅 / 赞赏")
    check_image(os.path.join(pack, "banner.png"), "banner.png", RULES["banner"][:2], RULES["banner"][2], False, True)
    for name in ("reward_guide.png", "reward_thanks.png"):
        if os.path.exists(os.path.join(pack, name)):
            check_image(os.path.join(pack, name), name, RULES[name.replace(".png", "")][:2],
                        RULES[name.replace(".png", "")][2], False, True)

    print("\n[5] 需要人工确认")
    print("  - 缩略图 / 封面 / 图标没有白描边（脚本测不出，肉眼看）")
    print("  - 横幅上没有任何文字")
    print("  - 整套线宽、配色、画风一致；每张动作差异明显")
    print("  - 无第三方 IP、品牌、真人肖像、二维码、水印")
    print("  - 含义词每张 ≤4 字且不重复")

    print("\n结果：{} 项通过，{} 项失败".format(ok_count, bad_count))
    sys.exit(1 if bad_count else 0)


if __name__ == "__main__":
    main()

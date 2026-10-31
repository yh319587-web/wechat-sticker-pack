# -*- coding: utf-8 -*-
"""按 plan.json 批量生成表情原图（OpenAI 兼容 /v1/images/edits）。

只依赖标准库，不需要 requests。

用法：
    export OPENAI_API_KEY=sk-xxx
    python scripts/gen.py --plan plan.json --ref ref.jpg
    python scripts/gen.py --plan plan.json --ref ref.jpg --only 03,15 --force
    python scripts/gen.py --plan plan.json --ref ref.jpg --dry-run
"""
import argparse
import base64
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

LOCK = threading.Lock()

PLAIN = """装饰规则（本套为纯表情模式）：
一、画面中只有角色本身：不画道具、不画手持物、不画情绪符号、不画动势线、不画背景元素。
二、不佩戴任何配饰：不要项圈、围巾、帽子、眼镜、铃铛，也不要别花、别叶子。
三、不画地面、不画投影、不画边框、不画对话框。留白就是全部背景。
四、情绪只能靠五官与体态表达：眼睛形状、耳朵角度、重心、尾巴走向。"""

PROPS = """装饰规则（必须有装饰，但必须克制、统一）：
一、角色身上不佩戴任何配饰：不要项圈、围巾、帽子、眼镜、铃铛。角色就是它本身，不加任何穿戴物。
二、情绪符号：用少量手绘水彩小元素烘托情绪，浮在角色周围，不接触身体，不遮挡脸。每个元素都要有粗深棕轮廓线，和角色是同一种画法，不能是干净的矢量图标。
三、小道具：只画一件，摆在角色脚边的地面上，比爪子略大一点，与爪子之间留出空隙，绝不被爪子碰到。
四、整套只用三类颜色：__PALETTE__，可以加一点低饱和的暖粉或雾蓝。不要高饱和荧光色，不要大红大紫。
五、装饰总面积不超过画面的四分之一，不能比角色更抢眼，留白仍然是主角。
六、所有元素都限制在画面中央 88% 的范围内，不能贴到画面边缘被裁切。"""

NEGATIVE = """禁止绘制任何文字、字母、数字、标点、问号、感叹号、对话气泡、水印、签名、logo。不要画其他角色或人物。"""


def composition(mode, subject):
    tail = "道具在脚边，情绪符号在头部周围；" if mode == "props" else "四周留白充足；"
    return (
        "构图：1:1 正方形，纯透明背景，{s}居中偏上，{s}本身约占画面 55%，{t}"
        "{s}的耳朵、尾巴、四肢完整可见；不要地面、不要投影、不要纸张底色、不要边框、不要对话框。"
    ).format(s=subject, t=tail)


def build_prompt(plan, sticker, mode):
    style = plan.get("style", {})
    subject = style.get("subject") or "角色"
    palette = style.get("palette", "暖橘、奶油白、低饱和橄榄绿")

    blocks = [
        "严格以参考图中的{0}为唯一角色外观依据：{1}。不可改变品种、毛色、花纹分布、头身比例。".format(
            subject, style["character"]),
        "画风必须严格复刻参考图：{0}。禁止写实、3D、矢量、日漫、赛璐璐、数码厚涂、精细插画。".format(style["art"]),
    ]
    if style.get("extra"):
        blocks.append(style["extra"].strip())
    anatomy = style["anatomy"]
    if mode == "plain":
        anatomy = anatomy.replace("道具摆在身体旁边的地面上，与爪子留出一段空隙。", "").rstrip()

    blocks += [
        "身体结构必须符合真实解剖，这是硬性要求：\n" + anatomy,
        (PROPS if mode == "props" else PLAIN).replace("__PALETTE__", palette),
        composition(mode, subject),
        NEGATIVE,
    ]

    body = [(sticker.get("action") or "").strip()]
    if mode == "props":
        if sticker.get("symbol"):
            body.append("情绪符号：" + sticker["symbol"].strip())
        if sticker.get("prop"):
            body.append("道具：" + sticker["prop"].strip())
    head = ("只绘制下面这一个动作和情绪，以及指定的道具和符号："
            if mode == "props" else "只绘制下面这一个动作和情绪：")
    blocks.append(head + "\n\n" + "\n".join(body))
    return "\n\n".join(blocks)


def guess_mime(path):
    return "image/jpeg" if path.lower().endswith((".jpg", ".jpeg")) else "image/png"


def post_multipart(url, fields, file_field, file_path, headers, timeout):
    boundary = "----sticker" + uuid.uuid4().hex
    body = b""
    for key, val in fields.items():
        body += ('--%s\r\nContent-Disposition: form-data; name="%s"\r\n\r\n%s\r\n'
                 % (boundary, key, val)).encode("utf-8")
    with open(file_path, "rb") as fh:
        payload = fh.read()
    body += ('--%s\r\nContent-Disposition: form-data; name="%s"; filename="%s"\r\n'
             'Content-Type: %s\r\n\r\n'
             % (boundary, file_field, os.path.basename(file_path), guess_mime(file_path))).encode("utf-8")
    body += payload + b"\r\n"
    body += ("--%s--\r\n" % boundary).encode("utf-8")

    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "multipart/form-data; boundary=" + boundary)
    for key, val in headers.items():
        req.add_header(key, val)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def call_api(api, key, prompt, ref_path, retries=3):
    url = api["base_url"].rstrip("/") + "/v1/images/edits"
    fields = {
        "model": api.get("model", "gpt-image-1"),
        "prompt": prompt,
        "size": api.get("size", "1024x1024"),
        "quality": api.get("quality", "high"),
        "n": "1",
    }
    for opt in ("background", "output_format"):
        if api.get(opt):
            fields[opt] = api[opt]

    headers = {"Authorization": "Bearer " + key}
    timeout = api.get("timeout", 300)
    last_error = ""

    for attempt in range(1, retries + 1):
        try:
            raw = post_multipart(url, fields, "image", ref_path, headers, timeout)
            return json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "ignore")[:300]
            last_error = "HTTP {}: {}".format(exc.code, detail)
            if exc.code == 400 and "background" in detail:
                fields.pop("background", None)
                continue
            if exc.code in (400, 401, 403, 404):
                break
        except Exception as exc:  # noqa: BLE001
            last_error = "{}: {}".format(type(exc).__name__, exc)
        if attempt < retries:
            time.sleep(5 * attempt)
    raise RuntimeError(last_error)


def save_payload(payload, out_path):
    item = (payload.get("data") or [{}])[0]
    if item.get("b64_json"):
        with open(out_path, "wb") as fh:
            fh.write(base64.b64decode(item["b64_json"]))
        return
    if item.get("url"):
        with urllib.request.urlopen(item["url"], timeout=300) as resp:
            with open(out_path, "wb") as fh:
                fh.write(resp.read())
        return
    raise RuntimeError("返回里没有 b64_json 也没有 url")


def main():
    ap = argparse.ArgumentParser(description="批量生成微信表情原图")
    ap.add_argument("--plan", default="plan.json")
    ap.add_argument("--ref", help="参考图路径，默认取 plan.ref_image")
    ap.add_argument("--mode", choices=["plain", "props", "auto"], default="auto",
                    help="覆盖 plan.style.mode")
    ap.add_argument("--only", help="只生成指定编号，逗号分隔，如 03,15")
    ap.add_argument("--force", action="store_true", help="已存在也重新生成")
    ap.add_argument("--dry-run", action="store_true", help="只打印提示词")
    ap.add_argument("--out", default="raw")
    ap.add_argument("--prompts", default="prompts")
    ap.add_argument("--api-key", help="默认读 OPENAI_API_KEY")
    args = ap.parse_args()

    with open(args.plan, "r", encoding="utf-8") as fh:
        plan = json.load(fh)

    style = plan.get("style", {})
    mode = style.get("mode", "props") if args.mode == "auto" else args.mode
    if mode not in ("plain", "props"):
        sys.exit("style.mode 只能是 plain 或 props")

    api = plan.get("api", {})
    ref = args.ref or plan.get("ref_image")
    if not ref:
        sys.exit("缺参考图：用 --ref 指定，或在 plan.ref_image 里写路径")

    stickers = plan["stickers"]
    if args.only:
        wanted = {x.strip() for x in args.only.split(",") if x.strip()}
        stickers = [s for s in stickers if str(s["id"]) in wanted]
        missing = wanted - {str(s["id"]) for s in stickers}
        if missing:
            sys.exit("plan 里找不到编号：" + ",".join(sorted(missing)))

    os.makedirs(args.out, exist_ok=True)
    os.makedirs(args.prompts, exist_ok=True)

    tasks = []
    for st in stickers:
        sid = str(st["id"])
        prompt = build_prompt(plan, st, mode)
        with open(os.path.join(args.prompts, sid + ".txt"), "w", encoding="utf-8") as fh:
            fh.write(prompt)
        out_path = os.path.join(args.out, sid + ".png")
        if os.path.exists(out_path) and not args.force:
            print("[skip] {} {} 已存在".format(sid, st.get("name", "")))
            continue
        tasks.append((sid, st, prompt, out_path))

    print("模式 {}｜待生成 {} 张｜参考图 {}".format(mode, len(tasks), ref))

    if args.dry_run:
        for sid, st, prompt, _ in tasks:
            print("\n" + "=" * 62 + "\n{} {}\n".format(sid, st.get("name", "")) + "=" * 62)
            print(prompt)
        return

    if not tasks:
        print("没有需要生成的图。")
        return

    key = args.api_key or os.environ.get("OPENAI_API_KEY") or api.get("api_key")
    if not key:
        sys.exit("缺 API key：export OPENAI_API_KEY=sk-xxx")
    if not os.path.exists(ref):
        sys.exit("参考图不存在：" + ref)

    workers = max(1, int(api.get("concurrency", 4)))
    ok, fail = [], []

    def work(item):
        sid, st, prompt, out_path = item
        payload = call_api(api, key, prompt, ref, int(api.get("retries", 3)))
        save_payload(payload, out_path)
        return sid, os.path.getsize(out_path) // 1024

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(work, t): t for t in tasks}
        for fut in as_completed(futures):
            sid = futures[fut][0]
            try:
                sid, kb = fut.result()
                with LOCK:
                    ok.append(sid)
                    print("[ok]   {}  {}KB  ({}/{})".format(sid, kb, len(ok) + len(fail), len(tasks)))
            except Exception as exc:  # noqa: BLE001
                with LOCK:
                    fail.append(sid)
                    print("[fail] {}  {}".format(sid, exc))

    print("\n完成 {} 张，失败 {} 张。".format(len(ok), len(fail)))
    if fail:
        print("重发失败项：python scripts/gen.py --plan {} --only {}".format(args.plan, ",".join(sorted(fail))))
        sys.exit(1)


if __name__ == "__main__":
    main()

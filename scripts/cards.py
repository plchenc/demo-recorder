#!/usr/bin/env python3
"""demo-recorder · selfdrive 模式 - 卡片生成（片头/技术说明/结尾）。

程序自驱型演示的「片头 / 技术说明卡 / 结尾卡」生成器（PIL 绘制，深色风格）。
由 selfdrive.py 调用，也可独立使用：

  python3 cards.py --meta meta.json -w out      # 按 meta.json 生成全部卡片
  python3 cards.py --demo                        # 生成内置示例卡片（果蝇恐龙）

卡片文案原则（观众视角）：主语是「你/它」，说得到什么，不堆技术黑话；
技术卡要点 = 标签(2-6字) + 一句话(≤38字)，每条一个可讲的事实。
"""
import argparse
import json
import os
import subprocess
import sys

W, H = 1920, 1080
BG = (13, 17, 23)
FG = (230, 237, 243)
ACC = (63, 185, 80)     # 终端绿：强调/标签
DIM = (139, 148, 158)   # 次要文字
LINE = (48, 54, 61)

FONT_DIRS = [
    "/usr/share/fonts/opentype/noto",            # Debian/Ubuntu
    "/usr/share/fonts/truetype/noto",            # 部分发行版
    "/System/Library/Fonts",                     # macOS
]


def _font_candidates():
    """按优先级返回 (黑体系, 常规系) 候选字体路径。env CARDS_FONT 可强制。"""
    forced = os.environ.get("CARDS_FONT")
    if forced:
        base = os.path.basename(forced).lower()
        if "black" in base or "bold" in base:
            return forced, forced
        return forced, forced
    bold = reg = None
    try:
        r = subprocess.run(["fc-list", ":lang=zh", "file"],
                           capture_output=True, text=True, timeout=10)
        files = [l.strip().rstrip(":") for l in r.stdout.splitlines() if l.strip()]
        for f in files:
            low = os.path.basename(f).lower()
            if bold is None and ("black" in low or "bold" in low) and "cjk" in low:
                bold = f
            if reg is None and ("regular" in low or "medium" in low) and "cjk" in low:
                reg = f
    except Exception:
        pass
    for d in FONT_DIRS:
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            p = os.path.join(d, f)
            low = f.lower()
            if bold is None and "notosanscjk-black" in low:
                bold = p
            if reg is None and ("notosanscjk-regular" in low
                                or "notosanscjk-medium" in low):
                reg = p
    if bold is None:
        sys.exit("✗ 未找到中文字体（Noto Sans CJK）；apt install fonts-noto-cjk"
                 " 或 env CARDS_FONT=/path/to/font.ttf")
    return bold, (reg or bold)


def _load(path, size):
    from PIL import ImageFont
    try:
        return ImageFont.truetype(path, size, index=2)  # ttc: 优先 SC face
    except Exception:
        return ImageFont.truetype(path, size)


def _center(d, y, text, f, fill, width=W):
    bb = d.textbbox((0, 0), text, font=f)
    d.text(((width - (bb[2] - bb[0])) / 2 - bb[0], y), text, font=f, fill=fill)


def _blank():
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (W, H), BG)
    return img, ImageDraw.Draw(img)


def make_title(cards, out_png):
    """片头卡：大字标题(1-2行) + 绿色副标 + 灰色注脚。"""
    f_big = _load(_bold, 130)
    f_sub = _load(_med, 44)
    f_note = _load(_reg, 36)
    img, d = _blank()
    titles = cards["title"] if isinstance(cards["title"], list) else [cards["title"]]
    y = 500 - 170 * len(titles)
    for t in titles:
        _center(d, y, t, f_big, FG)
        y += 170
    if cards.get("title_sub"):
        _center(d, y + 50, cards["title_sub"], f_sub, ACC)
    if cards.get("title_note"):
        _center(d, y + 160, cards["title_note"], f_note, DIM)
    d.line([(760, 660 if len(titles) > 1 else 490), (1160, 660 if len(titles) > 1 else 490)],
           fill=LINE, width=3)
    img.save(out_png)


def make_tech(cards, out_png):
    """技术说明卡：标题 + 标签-正文行(标签框自适应宽) + 底部注脚。"""
    f_head = _load(_bold, 64)
    f_tag = _load(_bold, 40)
    f_txt = _load(_reg, 38)
    f_foot = _load(_med, 38)
    img, d = _blank()
    if cards.get("tech_head"):
        _center(d, 90, cards["tech_head"], f_head, ACC)
    y = 250
    for row in cards.get("tech_rows", []):
        tag, txt = (row + [""])[:2] if isinstance(row, list) else ("", row)
        tw = d.textbbox((0, 0), tag, font=f_tag)[2]
        if tag:
            d.rounded_rectangle([(90, y - 6), (140 + tw, y + 56)], 12,
                                fill=(31, 40, 51))
            d.text((115, y + 2), tag, font=f_tag, fill=ACC)
        d.text((190 + tw, y + 4), txt, font=f_txt, fill=FG)
        y += 130
    if cards.get("tech_foot"):
        _center(d, 950, cards["tech_foot"], f_foot, DIM)
    img.save(out_png)


def make_end(cards, out_png):
    """结尾卡：标题 + 绿色副标 + 署名。"""
    f_big = _load(_bold, 84)
    f_sub = _load(_med, 46)
    f_note = _load(_reg, 40)
    img, d = _blank()
    _center(d, 400, cards.get("end_title", "Demo"), f_big, FG)
    if cards.get("end_sub"):
        _center(d, 560, cards["end_sub"], f_sub, ACC)
    if cards.get("end_note"):
        _center(d, 700, cards["end_note"], f_note, DIM)
    img.save(out_png)


def gen_all(meta, workdir):
    """按 meta['cards'] 生成三张卡，返回 {head,tech,end: png路径}；缺失段跳过。"""
    os.makedirs(workdir, exist_ok=True)
    cards = meta.get("cards") or {}
    out = {}
    if cards.get("title"):
        p = os.path.join(workdir, "card_title.png")
        make_title(cards, p)
        out["head"] = p
    if cards.get("tech_rows"):
        p = os.path.join(workdir, "card_tech.png")
        make_tech(cards, p)
        out["tech"] = p
    if cards.get("end_title"):
        p = os.path.join(workdir, "card_end.png")
        make_end(cards, p)
        out["end"] = p
    return out


def main():
    ap = argparse.ArgumentParser(description="selfdrive 卡片生成")
    ap.add_argument("--meta", help="meta.json（含 cards 段）")
    ap.add_argument("-w", "--workdir", default="out", help="输出目录")
    ap.add_argument("--demo", action="store_true", help="内置示例（果蝇恐龙）")
    a = ap.parse_args()
    global _bold, _med, _reg
    _bold, _reg = _font_candidates()
    _med = _reg
    if a.demo:
        meta = json.load(open(os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "examples", "selfdrive", "meta.json")))
    else:
        if not a.meta:
            sys.exit("用法: cards.py --meta meta.json -w out | --demo")
        meta = json.load(open(a.meta))
    out = gen_all(meta, a.workdir)
    for k, v in out.items():
        print(f"  {k}: {v}")
    print(f"✓ 卡片生成 {len(out)} 张 → {a.workdir}/")


if __name__ == "__main__":
    main()

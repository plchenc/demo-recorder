#!/usr/bin/env python3
"""demo-recorder · selfdrive 模式 - 程序自驱型演示合成。

适用：画面不是「agent 操作网页」，而是「程序/模型/硬件自己跑」的演示
（游戏 AI、仿真、机器人、数字大脑……）。操控方自己出正片
（playwright 内录 / screencast / 摄像头均可），本脚本负责：
  片头卡 → 技术说明卡 → 正片(等比放大+居中 pad) → 结尾卡 → 1080p MP4

用法:
  python3 selfdrive.py --video <正片.webm|mp4> --meta meta.json -w out
  python3 selfdrive.py --demo                       # 用内置示例参数

meta.json 关键字段:
  main_scale_h  正片目标高(默认自动: 1920 宽等比, ≤1080)
  cards         见 cards.py（title/tech_rows/end_title...）
  card_secs     {head:3.0, tech:4.0, end:2.5} 可选

流程经验（果蝇恐龙 demo 实战沉淀）:
  - 正片若为 playwright 录制，录制端用 device_scale_factor≥2 原生高分辨率，
    CSS 尺寸不动（位图与显示 1:1，勿加 CSS zoom，否则画面被挤出视窗）
  - 采样/操控坐标若读 canvas 位图，记得随 DPR 同步乘 scale
  - 死亡/失败画面保留：真实感是自驱 demo 的说服力
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "scripts"))


def find_ffmpeg():
    for p in [os.environ.get("FFMPEG"),
              os.path.join(HERE, "bin", "ffmpeg"),
              shutil_which("ffmpeg")]:
        if p and os.path.exists(p):
            return p
    sys.exit("✗ 未找到 ffmpeg（apt install ffmpeg / npm i ffmpeg-static"
             " / 静态包放 skill bin/）")


def shutil_which(name):
    from shutil import which
    return which(name)


def probe_size(ff, video):
    r = subprocess.run([ff, "-i", video], capture_output=True, text=True)
    for line in r.stderr.splitlines():
        if "Stream" in line and "Video" in line:
            for part in line.split(","):
                part = part.strip()
                if "x" in part and part.split("x")[0].isdigit():
                    w, h = part.split("x")[:2]
                    return int(w), int(h)
    sys.exit("✗ 无法读取正片分辨率")


def run(args):
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"✗ ffmpeg 失败\n{r.stderr[-600:]}")


def main():
    global _cards
    ap = argparse.ArgumentParser(description="selfdrive 模式合成")
    ap.add_argument("--video", help="程序自驱正片（webm/mp4）")
    ap.add_argument("--meta", help="meta.json")
    ap.add_argument("-w", "--workdir", default="out")
    ap.add_argument("--demo", action="store_true", help="内置示例参数+跳过正片校验")
    ap.add_argument("--audio", default="",
                    help="正片音轨（m4a/wav，按正片自身时间轴；"
                         "自动延后至片头+技术卡结束处）")
    a = ap.parse_args()

    if a.demo:
        ex = os.path.join(HERE, "examples", "selfdrive", "meta.json")
        meta = json.load(open(ex))
        if not a.video:
            sys.exit("--demo 需同时给 --video（任意 webm/mp4 均可试跑）")
    else:
        if not (a.video and a.meta):
            sys.exit("用法: selfdrive.py --video <正片> --meta meta.json -w out")
        meta = json.load(open(a.meta))

    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        sys.exit("✗ 缺 pillow：.venv/bin/pip install pillow -i "
                 "https://pypi.tuna.tsinghua.edu.cn/simple")

    ff = find_ffmpeg()
    os.makedirs(a.workdir, exist_ok=True)
    out = meta.get("out") or "selfdrive_final.mp4"
    if not os.path.isabs(out):
        out = os.path.join(a.workdir, out)

    # 1) 卡片
    import cards as cards_mod
    _bold, _reg = cards_mod._font_candidates()
    cards_mod._bold, cards_mod._reg = _bold, _reg
    cards_mod._med = _reg
    pngs = cards_mod.gen_all(meta, a.workdir)
    if not pngs:
        sys.exit("✗ meta.cards 为空：至少提供 title/tech_rows/end_title 之一")

    secs = meta.get("card_secs") or {}
    seg_files = []
    for seg, dsec in [("head", secs.get("head", 3.0)),
                      ("tech", secs.get("tech", 4.0)),
                      ("end", secs.get("end", 2.5))]:
        if seg not in pngs:
            continue
        seg_f = os.path.join(a.workdir, f"seg_{seg}.mp4")
        run([ff, "-y", "-loop", "1", "-t", str(dsec), "-i", pngs[seg],
             "-r", "25", "-c:v", "libx264", "-pix_fmt", "yuv420p",
             "-crf", "20", "-preset", "fast", "-vf", "scale=1920:1080",
             seg_f])
        seg_files.append((seg, seg_f))

    # 2) 正片：等比放大到 1920 宽（高≤1080 不放大），居中 pad 1080
    main_f = os.path.join(a.workdir, "seg_main.mp4")
    w, h = probe_size(ff, a.video)
    tw = 1920
    th = round(h * tw / w / 2) * 2
    if th > 1080:
        th = 1080
        tw = round(w * th / h / 2) * 2
    pad_top = (1080 - th) // 2
    vf = (f"scale={tw}:{th}:flags=lanczos,"
          f"pad=1920:1080:0:{pad_top}:color=0d1117")
    run([ff, "-y", "-i", a.video, "-r", "25", "-vf", vf,
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20",
         "-preset", "fast", main_f])
    # 正片插入在 tech 卡之后（head→tech→main→end）
    order = []
    for seg, f in seg_files:
        order.append((seg, f))
        if seg == "tech":
            order.append(("main", main_f))
    if "main" not in [s for s, _ in order]:
        order.append(("main", main_f))

    # 3) concat
    list_f = os.path.join(a.workdir, "concat.txt")
    with open(list_f, "w") as fh:
        for _, seg_file in order:
            fh.write(f"file '{seg_file}'\n")
    run([ff, "-y", "-f", "concat", "-safe", "0", "-i", list_f,
         "-c:v", "libx264", "-crf", "20", "-preset", "fast",
         "-pix_fmt", "yuv420p",
         "-movflags", "+faststart", out])
    if a.audio:
        # 音轨对齐：延后 = 片头+技术卡时长（正片音效从正片起点算）
        front = sum(float(secs.get(s, d)) for s, d in
                    [("head", 3.0), ("tech", 4.0)] if s in pngs)
        run([ff, "-y", "-i", a.audio,
             "-af", f"adelay={int(front * 1000)}|{int(front * 1000)}",
             "-c:a", "aac", "-b:a", "128k",
             os.path.join(a.workdir, "audio_shifted.m4a")])
        final_a = out + ".a.mp4"
        run([ff, "-y", "-i", out, "-i",
             os.path.join(a.workdir, "audio_shifted.m4a"),
             "-map", "0:v", "-map", "1:a",
             "-c:v", "copy", "-c:a", "copy",
             "-movflags", "+faststart", final_a])
        os.replace(final_a, out)
    print(f"✓ selfdrive 成片: {out}"
          + ("（含音轨）" if a.audio else ""))
    print(f"  段落顺序: {' → '.join(s for s, _ in order)}")


if __name__ == "__main__":
    main()

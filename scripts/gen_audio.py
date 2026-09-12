#!/usr/bin/env python3
"""demo-recorder 第一步：把剧本解说词合成为语音段落（edge-tts，微软神经语音，
无需 API key，需能访问 speech.platform.bing.com）。

输入: scenario.json
输出: workdir/audio/seg_<i>_<name>.mp3 × N + manifest.json（含每段精确时长）

用法:
  python3 gen_audio.py <scenario.json> [-w workdir] [--force]
"""
import argparse
import asyncio
import json
import os
import re
import subprocess
import sys

import edge_tts

DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural"  # 晓晓，女声；男声: zh-CN-YunxiNeural


def find_ffmpeg():
    """ffmpeg 查找顺序: env FFMPEG > skill bin/ > PATH"""
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for p in [os.environ.get("FFMPEG"),
              os.path.join(here, "bin", "ffmpeg"),
              shutil_which("ffmpeg")]:
        if p and os.path.exists(p):
            return p
    sys.exit("✗ 未找到 ffmpeg。请安装（apt install ffmpeg / npm i ffmpeg-static），"
             "或将二进制放到 skill 的 bin/ 目录，或设环境变量 FFMPEG")


def shutil_which(name):
    from shutil import which
    return which(name)


def probe_duration_ms(ffmpeg, path, retries=2):
    """用 ffmpeg 解码测时长（比读文件头可靠，不依赖 ffprobe）"""
    for _ in range(retries + 1):
        r = subprocess.run([ffmpeg, "-i", path, "-f", "null", "-"],
                           capture_output=True, text=True, timeout=60)
        m = re.findall(r"time=(\d+):(\d+):(\d+\.?\d*)", r.stderr)
        if m:
            h, mi, s = m[-1]
            return int((int(h) * 3600 + int(mi) * 60 + float(s)) * 1000)
    return 0


async def synth(text, voice, rate, out, retries=3):
    for i in range(retries):
        try:
            await edge_tts.Communicate(
                text, voice, rate=rate).save(out)
            if os.path.getsize(out) > 1000:
                return True
        except Exception as e:  # noqa: BLE001
            print(f"  重试 {i + 1}/{retries}: {e}")
            await asyncio.sleep(2)
    return False


async def run(sc, work, force):
    audio_dir = os.path.join(work, "audio")
    os.makedirs(audio_dir, exist_ok=True)
    ffmpeg = find_ffmpeg()
    voice = sc.get("voice", DEFAULT_VOICE)
    rate = sc.get("rate", "+8%")

    manifest = []
    ok_all = True
    for i, st in enumerate(sc.get("steps", []), 1):
        name = st.get("name", f"step{i}")
        text = (st.get("narration") or "").strip()
        out = os.path.join(audio_dir, f"seg_{i:02d}_{name}.mp3")
        if not text:
            print(f"  - {name}: 无解说，跳过")
            continue
        if os.path.exists(out) and not force:
            print(f"  = {name}: 已存在，跳过（--force 重生成）")
        else:
            print(f"  ⏵ {name}: 合成 {len(text)} 字 …")
            if not await synth(text, voice, rate, out):
                ok_all = False
                print(f"  ✗ {name}: 合成失败")
                continue
        dur = probe_duration_ms(ffmpeg, out)
        manifest.append({"name": name, "file": out,
                         "dur_ms": dur, "narration": text})
        print(f"    {dur / 1000:.1f}s  {os.path.basename(out)}")

    json.dump(manifest, open(os.path.join(audio_dir, "manifest.json"), "w"),
              ensure_ascii=False, indent=1)
    total = sum(m["dur_ms"] for m in manifest) / 1000
    print(f"[audio] {len(manifest)} 段 / 共 {total:.1f}s → manifest.json")
    if not ok_all:
        sys.exit(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scenario")
    ap.add_argument("-w", "--workdir", default=None)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    sc = json.load(open(args.scenario, encoding="utf-8"))
    work = os.path.abspath(args.workdir or os.path.join(
        os.path.dirname(os.path.abspath(args.scenario)), "out"))
    asyncio.run(run(sc, work, args.force))


if __name__ == "__main__":
    main()

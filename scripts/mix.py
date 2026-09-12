#!/usr/bin/env python3
"""demo-recorder 第三步：合成 —— 解说音频按时间戳混入录屏 + 可选字幕烧录 + H.264 通用编码。

输入: workdir/{raw.webm, stamps.json, audio/manifest.json, subtitles.srt}
输出: <scenario.out 或 workdir/demo.mp4>

用法:
  python3 mix.py <scenario.json> [-w workdir] [--no-subtitle] [--crf 22]
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def find_ffmpeg():
    for p in [os.environ.get("FFMPEG"),
              os.path.join(HERE, "bin", "ffmpeg"),
              shutil_which("ffmpeg")]:
        if p and os.path.exists(p):
            return p
    sys.exit("✗ 未找到 ffmpeg")


def shutil_which(name):
    from shutil import which
    return which(name)


def find_zh_font():
    """探测系统中文字体（subtitles 滤镜烧录用），没有则返回 None"""
    try:
        r = subprocess.run(["fc-list", ":lang=zh", "family"],
                           capture_output=True, text=True, timeout=10)
        fams = set()
        for line in r.stdout.splitlines():
            for fam in line.split(","):
                fams.add(fam.strip())
    except Exception:  # noqa: BLE001
        return None
    for want in ["Noto Sans CJK SC", "Noto Sans CJK", "WenQuanYi Micro Hei",
                 "WenQuanYi Zen Hei", "AR PL UKai CN", "AR PL UMing CN"]:
        if want in fams:
            return want
    return None


def build_filter(n_audio, stamps_ms, files, use_sub, srt, font, work):
    """adelay 对齐 + amix 保持音量（normalize=0 关键，否则多段衰减）+ 字幕烧录"""
    chains = []
    for i, ms in enumerate(stamps_ms, 1):
        # aformat 统一采样率/声道（不同 voice 来源防御）
        chains.append(f"[{i}:a]aformat=sample_rates=24000:channel_layouts=mono,"
                      f"adelay={ms}:all=1[a{i}]")
    if n_audio:
        mix_in = "".join(f"[a{i}]" for i in range(1, n_audio + 1))
        chains.append(f"{mix_in}amix=inputs={n_audio}:normalize=0,volume=1.0[aout]")
    sub = ""
    if use_sub and srt and os.path.exists(srt):
        style = (f"FontName={font},FontSize=20,PrimaryColour=&H00FFFFFF,"
                 f"OutlineColour=&H96000000,BorderStyle=1,Outline=1.5,Shadow=1,"
                 f"MarginV=30,Alignment=2") if font else \
                "FontSize=20,BorderStyle=1,Outline=1.5,MarginV=30"
        srt_esc = srt.replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
        sub = (f",subtitles=filename='{srt_esc}':force_style='{style}'")
    vf = f"[0:v]scale=trunc(iw/2)*2:trunc(ih/2)*2{sub}[vout]"
    return ";".join(chains + [vf])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scenario")
    ap.add_argument("-w", "--workdir", default=None)
    ap.add_argument("--no-subtitle", action="store_true")
    ap.add_argument("--crf", type=int, default=22)
    args = ap.parse_args()

    sc = json.load(open(args.scenario, encoding="utf-8"))
    work = os.path.abspath(args.workdir or os.path.join(
        os.path.dirname(os.path.abspath(args.scenario)), "out"))
    raw = os.path.join(work, "raw.webm")
    stamps = json.load(open(os.path.join(work, "stamps.json"), encoding="utf-8"))
    mf_path = os.path.join(work, "audio", "manifest.json")
    manifest = json.load(open(mf_path, encoding="utf-8")) \
        if os.path.exists(mf_path) else []

    # 按 stamps.order 对齐音频段（录制时的步骤顺序 = 播放顺序）
    order, ms = stamps.get("order", []), stamps.get("ms", {})
    seg_by_name = {m["name"]: m for m in manifest}
    picked = [seg_by_name[n] for n in order
              if n in seg_by_name and os.path.exists(seg_by_name[n]["file"])]
    stamps_ms = [ms[n] for n in order if n in seg_by_name
                 and os.path.exists(seg_by_name[n]["file"])]

    use_sub = sc.get("subtitle", True) and not args.no_subtitle
    srt = os.path.join(work, "subtitles.srt")
    font = find_zh_font()
    if use_sub and not font:
        print("⚠ 未找到中文字体，字幕将使用默认字体（中文可能显示为方块）")
        print("  Ubuntu: apt install fonts-noto-cjk")
    fc = build_filter(len(picked), stamps_ms, picked, use_sub, srt, font, work)

    out = os.path.abspath(sc.get("out") or os.path.join(work, "demo.mp4"))
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    cmd = [find_ffmpeg(), "-y", "-i", raw]
    cmd += sum([["-i", m["file"]] for m in picked], [])
    maps = ["-map", "[vout]", "-map", "[aout]"] if picked \
        else ["-map", "0:v"]
    cmd += ["-filter_complex", fc] + maps + [
        "-c:v", "libx264", "-preset", "fast", "-crf", str(args.crf),
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        "-c:a", "aac", "-b:a", "128k", "-shortest", out]
    print(f"[mix] {len(picked)} 段解说混入；字幕: "
          f"{'烧录(' + font + ')' if use_sub and font else '关闭'}")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-1500:])
        sys.exit("✗ ffmpeg 失败")
    dur = [l for l in r.stderr.splitlines() if " time=" in l]
    print(f"[mix] ✅ {out}  ({os.path.getsize(out) / 1e6:.1f} MB, "
          f"最后时间戳 {dur[-1].split('time=')[-1].split()[0] if dur else '?'})")


if __name__ == "__main__":
    main()

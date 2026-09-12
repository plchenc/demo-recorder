#!/usr/bin/env python3
"""demo-recorder 第二步：按剧本操作页面并录屏（Chrome headless + Playwright 内部合成，
不依赖桌面环境，Wayland/Xorg/headless 服务器均可）。

输入: scenario.json + workdir/audio/manifest.json（gen_audio.py 产物，可缺省=纯静音录制）
输出: workdir/raw.webm + workdir/stamps.json + workdir/subtitles.srt

用法:
  python3 record.py <scenario.json> [-w workdir] [--no-strict]
"""
import argparse
import json
import os
import shutil
import sys
import time

from playwright.sync_api import sync_playwright

# ---------------- 通用工具 ----------------

CHROME_CANDIDATES = [
    # Linux
    "/opt/google/chrome/chrome", "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable", "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    # macOS
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
]


def find_chrome(scenario):
    """优先级: scenario.chrome_path > env DEMO_CHROME_PATH > 系统常见路径 > playwright 内置"""
    for p in [scenario.get("chrome_path"), os.environ.get("DEMO_CHROME_PATH"),
              *CHROME_CANDIDATES]:
        if p and os.path.exists(p):
            return p
    return None  # None = playwright 自带 chromium


BANNER_JS = """
() => {
  let b = document.getElementById('stage-banner');
  if (!b) {
    b = document.createElement('div');
    b.id = 'stage-banner';
    b.style.cssText = 'position:fixed;bottom:18px;right:18px;z-index:99999;'
      + 'background:rgba(20,20,35,0.92);color:#7CFC98;font:600 17px/1.5 '
      + 'system-ui,sans-serif;padding:10px 18px;border-radius:10px;'
      + 'max-width:640px;box-shadow:0 4px 18px rgba(0,0,0,.45);'
      + 'white-space:pre-line;';
    document.body.appendChild(b);
  }
  return 'ok';
}
"""

INTRO_CARD_CSS = """
* { margin:0; box-sizing:border-box; }
body { font-family: system-ui,"Noto Sans CJK SC","PingFang SC",sans-serif;
  background: linear-gradient(135deg,#0b1020 0%,#151d38 55%,#0f172a 100%);
  color:#e2e8f0; width:100vw; height:100vh;
  display:flex; align-items:center; justify-content:center; }
.wrap { text-align:center; max-width:860px; padding:0 40px; }
.logo { font-size:30px; margin-bottom:18px; }
h1 { font-size:56px; letter-spacing:1px; color:#fff; margin-bottom:10px; }
h1 .accent { color:#7CFC98; }
.slogan { font-size:20px; color:#94a3b8; margin-bottom:34px; }
.feats { display:flex; gap:14px; justify-content:center; margin-bottom:38px; }
.feat { background:rgba(124,252,152,.08); border:1px solid rgba(124,252,152,.25);
  color:#a7f3c0; font-size:15px; padding:8px 18px; border-radius:999px; }
.meta { font-size:15px; color:#64748b; line-height:1.9; }
.meta b { color:#cbd5e1; font-weight:600; }
"""


def _skill_version():
    """从 SKILL.md frontmatter 读版本（失败回落 1.x）"""
    import re
    try:
        sk = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "SKILL.md")
        m = re.search(r"^version:\s*(.+)$", open(sk, encoding="utf-8").read(),
                      re.M)
        return m.group(1).strip() if m else "1.x"
    except Exception:  # noqa: BLE001
        return "1.x"


def intro_card_html(sc):
    """首帧信息片头：工具名/版本/能力/本片元信息"""
    import datetime
    vw, vh = sc.get("viewport", [1280, 800])
    title = sc.get("title") or sc.get("base_url", "")
    today = datetime.date.today().strftime("%Y-%m-%d")
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<style>{INTRO_CARD_CSS}</style></head><body><div class="wrap">
  <div class="logo">🎬</div>
  <h1>demo-<span class="accent">recorder</span></h1>
  <div class="slogan">一份 JSON 剧本 → 自动配音 · 真实录屏 · 字幕成片</div>
  <div class="feats"><span class="feat">edge-tts 配音</span>
    <span class="feat">Playwright 真实操作</span>
    <span class="feat">srt 字幕烧录</span><span class="feat">H.264 通用格式</span></div>
  <div class="meta"><b>{title}</b><br>
    v{_skill_version()} · {vw}×{vh} · {today}</div>
</div></body></html>"""


def resolve_locator(page, spec):
    """定位器 DSL:
       "text=提交"        → 文本匹配（playwright 原生）
       "ph:请输入客户名"   → placeholder 匹配
       "role:button:发送"  → ARIA role + 名称（exact）
       "role:tab:本体建模" → 同上，tab 角色
       其他               → CSS 选择器
    """
    if spec.startswith("ph:"):
        return page.get_by_placeholder(spec[3:])
    if spec.startswith("role:"):
        _, role, name = spec.split(":", 2)
        return page.get_by_role(role, name=name, exact=True)
    return page.locator(spec)


def wait_text(page, text, timeout=20000):
    """轮询 body.innerText（比 wait_for_selector 稳，SPA/Gradio 适用）"""
    deadline = time.time() + timeout / 1000
    while time.time() < deadline:
        try:
            if text in page.inner_text("body"):
                return True
        except Exception:
            pass
        page.wait_for_timeout(600)
    return False


def srt_time(sec):
    h = int(sec // 3600)
    m = int(sec % 3600 // 60)
    s = sec % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", ",")


def wrap_zh(line, width=26):
    """中文长句折行（按字符；避免标点被孤立到下一行行首）"""
    parts = [line[i:i + width] for i in range(0, len(line), width)]
    for i in range(len(parts) - 1):  # 标点悬挂：并入上一行行尾
        while parts[i + 1] and parts[i + 1][0] in "。，、！？；：）":
            parts[i] += parts[i + 1][0]
            parts[i + 1] = parts[i + 1][1:]
            if not parts[i + 1]:
                parts[i:] = [parts[i]]
                break
    return "\n".join(p for p in parts if p)


def build_srt(steps, stamps, manifest, out_path):
    """字幕 = 每段解说按句子切分，按字数比例分配在 [stamp, stamp+dur] 内"""
    dur_by_name = {m["name"]: m["dur_ms"] / 1000 for m in manifest}
    records = []
    for st in steps:
        name = st.get("name")
        if name not in stamps or name not in dur_by_name:
            continue
        t0, dur = stamps[name] / 1000, dur_by_name[name]
        if not st.get("narration"):
            continue
        # 按句末标点切句（保留标点）
        sents, buf = [], ""
        for ch in st["narration"]:
            buf += ch
            if ch in "。！？；":
                sents.append(buf)
                buf = ""
        if buf.strip():
            sents.append(buf)
        total_chars = sum(len(s) for s in sents) or 1
        cur = t0
        for s in sents:
            seg = dur * len(s) / total_chars
            records.append((cur, cur + min(seg, 6.5), s.strip()))
            cur += seg
    with open(out_path, "w", encoding="utf-8") as f:
        for i, (a, b, txt) in enumerate(records, 1):
            f.write(f"{i}\n{srt_time(a)} --> {srt_time(b)}\n"
                    f"{wrap_zh(txt)}\n\n")
    return len(records)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scenario")
    ap.add_argument("-w", "--workdir", default=None)
    ap.add_argument("--no-strict", action="store_true",
                    help="动作失败不中止（默认失败即停，保留现场截图）")
    args = ap.parse_args()

    sc = json.load(open(args.scenario, encoding="utf-8"))
    work = os.path.abspath(args.workdir or os.path.join(
        os.path.dirname(os.path.abspath(args.scenario)), "out"))
    os.makedirs(work, exist_ok=True)
    os.makedirs(os.path.join(work, "snaps"), exist_ok=True)

    manifest = []
    mf = os.path.join(work, "audio", "manifest.json")
    if os.path.exists(mf):
        manifest = json.load(open(mf, encoding="utf-8"))
    steps = sc.get("steps", [])
    base = sc.get("base_url", "http://127.0.0.1:8000")
    vw, vh = sc.get("viewport", [1280, 800])
    use_banner = sc.get("banner", True)

    stamps = {"order": [], "ms": {}}
    t0 = None

    def stamp(name):
        stamps["order"].append(name)
        stamps["ms"][name] = round((time.time() - t0) * 1000)

    def do_action(page, act):
        op = act[0]
        a = act[1:]
        if op == "goto":
            url = a[0]
            if url.startswith("http") or url.startswith("file:"):
                page.goto(url, wait_until="domcontentloaded")
            else:
                page.goto(base.rstrip("/") + url, wait_until="domcontentloaded")
            page.wait_for_timeout(1200)
            if use_banner:  # 导航会重置 DOM，banner 需重注入
                page.evaluate(BANNER_JS)
        elif op == "click":
            resolve_locator(page, a[0]).click()
            if len(a) > 1:
                page.wait_for_timeout(a[1])
        elif op == "dblclick":
            resolve_locator(page, a[0]).dblclick()
        elif op == "fill":
            resolve_locator(page, a[0]).fill(a[1])
        elif op == "type":  # 逐字输入（真人感）
            loc = resolve_locator(page, a[0])
            loc.click()
            loc.type(a[1], delay=a[2] if len(a) > 2 else 40)
        elif op == "press":
            page.keyboard.press(a[0])
        elif op == "select":
            resolve_locator(page, a[0]).select_option(a[1])
        elif op == "hover":
            resolve_locator(page, a[0]).hover()
        elif op == "wait":
            page.wait_for_timeout(a[0])
        elif op == "wait_text":
            ok = wait_text(page, a[0], a[1] if len(a) > 1 else 20000)
            if not ok:
                raise TimeoutError(f"wait_text 超时: {a[0]!r}")
        elif op == "wait_selector":
            page.wait_for_selector(a[0], timeout=a[1] if len(a) > 1 else 20000)
        elif op == "scroll":
            page.mouse.wheel(0, a[0])
            page.wait_for_timeout(600)
        elif op == "eval":
            page.evaluate(a[0])
        elif op == "snap":  # 调试截图（不影响视频）
            page.screenshot(path=os.path.join(work, "snaps",
                                              (a[0] if a else f"s{time.time()}") + ".png"))
        else:
            raise ValueError(f"未知动作: {op}")

    chrome = find_chrome(sc)
    print(f"[record] chrome: {chrome or 'playwright 内置 chromium'}")
    print(f"[record] workdir: {work}  steps: {len(steps)}")

    with sync_playwright() as p:
        kwargs = {"headless": True}
        if chrome:
            kwargs["executable_path"] = chrome
        browser = p.chromium.launch(
            args=["--no-sandbox", "--disable-dev-shm-usage"], **kwargs)
        ctx = browser.new_context(
            viewport={"width": vw, "height": vh},
            record_video_dir=work,
            record_video_size={"width": vw, "height": vh})
        page = ctx.new_page()
        page.set_default_timeout(20000)

        try:
            # 首帧信息片头：demo-recorder 基本信息，保持 intro_card_secs 秒
            # （t0 之前，不占音频时间轴——片头后解说立即开始）
            if sc.get("intro_card", True):
                page.goto("about:blank")
                page.set_content(intro_card_html(sc), wait_until="domcontentloaded")
                page.wait_for_timeout(
                    int(sc.get("intro_card_secs", 2.0) * 1000))
            # 首个动作前先落到页面（保证录到真实首屏）
            first_goto = next((s for s in steps
                               if s.get("actions") and s["actions"][0][0] == "goto"),
                              None)
            if first_goto is None:
                page.goto(base, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)
            if use_banner:
                page.evaluate(BANNER_JS)
            t0 = time.time()

            dur_by_name = {m["name"]: m["dur_ms"] / 1000 for m in manifest}
            for idx, st in enumerate(steps, 1):
                name = st.get("name", f"step{idx}")
                step_start = time.time()
                stamp(name)
                print(f"  [{stamps['ms'][name] / 1000:>7.2f}s] {name}")
                if use_banner and st.get("banner_text"):
                    page.evaluate(BANNER_JS)  # 幂等注入
                    page.evaluate(
                        f"() => {{document.getElementById('stage-banner')"
                        f".textContent = {st['banner_text']!r};}}")
                for act in st.get("actions", []):
                    try:
                        do_action(page, act)
                    except Exception as e:  # noqa: BLE001
                        page.screenshot(path=os.path.join(
                            work, "snaps", f"ERROR_{name}.png"))
                        print(f"  ✗ 动作失败 {name} {act[:2]}: {e}")
                        if not args.no_strict:
                            raise
                # 对齐保持：本步画面至少停留「解说时长 + 缓冲」
                need = max(st.get("pause_after", 1.0),
                           dur_by_name.get(name, 0) + 1.2)
                remain = need - (time.time() - step_start)
                while remain > 0:
                    page.wait_for_timeout(min(800, remain * 1000))
                    remain = need - (time.time() - step_start)

            page.wait_for_timeout(int(sc.get("tail_hold", 1.5) * 1000))
        finally:
            video = page.video
            path = video.path() if video else None
            ctx.close()
            browser.close()
        if path and os.path.exists(path):
            shutil.move(path, os.path.join(work, "raw.webm"))
            print(f"[record] raw.webm ok")

    json.dump(stamps, open(os.path.join(work, "stamps.json"), "w"),
              ensure_ascii=False, indent=1)
    n = build_srt(steps, stamps["ms"], manifest,
                  os.path.join(work, "subtitles.srt"))
    print(f"[record] stamps.json ok; subtitles: {n} 条")


if __name__ == "__main__":
    sys.exit(main())

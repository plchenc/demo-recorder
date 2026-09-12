#!/usr/bin/env bash
# demo-recorder 一键安装：独立 venv（不影响系统）+ 国内镜像加速
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
PIP_MIRROR="https://pypi.tuna.tsinghua.edu.cn/simple"

echo "== demo-recorder 安装 =="
command -v python3 >/dev/null || { echo "✗ 请先安装 python3"; exit 1; }

if [ ! -x "$HERE/.venv/bin/python3" ]; then
  echo "1/3 创建独立 venv ..."
  python3 -m venv "$HERE/.venv"
fi
PY="$HERE/.venv/bin/python3"

echo "2/3 安装 playwright + edge-tts（清华镜像）..."
"$PY" -m pip install -q --upgrade pip -i "$PIP_MIRROR"
"$PY" -m pip install -q playwright edge-tts -i "$PIP_MIRROR"

echo "3/3 浏览器 ..."
SYS_BROWSERS="/opt/google/chrome/chrome /usr/bin/google-chrome /usr/bin/google-chrome-stable /usr/bin/chromium /usr/bin/chromium-browser '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' '/Applications/Chromium.app/Contents/MacOS/Chromium'"
FOUND=0
for b in $SYS_BROWSERS; do [ -x "$b" ] && FOUND=1 && break; done
if [ "$FOUND" = "1" ]; then
  echo "  检测到系统 Chrome/Chromium，跳过下载（record.py 自动使用）"
else
  echo "  下载 playwright chromium（npmmirror 镜像）..."
  PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright/ \
    "$PY" -m playwright install chromium
fi

echo
bash "$HERE/check_env.sh"

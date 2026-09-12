#!/usr/bin/env bash
# demo-recorder 环境自检：逐项检查并给出修复指引（只读，不改系统）
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
PASS=0; FAIL=0; WARN=0

chk() { # chk <名称> <判断命令> <失败提示>
  local name="$1" cmd="$2" tip="$3"
  if eval "$cmd" >/dev/null 2>&1; then
    echo "  ✅ $name"; PASS=$((PASS+1))
  else
    echo "  ❌ $name"; [ -n "$tip" ] && echo "     └ 修复: $tip"; FAIL=$((FAIL+1))
  fi
}

echo "== demo-recorder 环境自检 =="

chk "python3 >= 3.10" "python3 -c 'import sys; assert sys.version_info >= (3,10)'" \
  "安装新版 python3（playwright 需要）"

if [ -x "$HERE/.venv/bin/python3" ]; then
  PY="$HERE/.venv/bin/python3"
  echo "  ✅ venv 已创建 ($PY)"; PASS=$((PASS+1))
else
  echo "  ❌ venv 未创建"; FAIL=$((FAIL+1))
  echo "     └ 修复: bash $HERE/install.sh"
  PY="python3"
fi

if [ -x "$PY" ] || command -v "$PY" >/dev/null; then
  chk "playwright 库" "\"$PY\" -c 'import playwright'" \
    "\"$PY\" -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple playwright"
  chk "edge-tts 库" "\"$PY\" -c 'import edge_tts'" \
    "\"$PY\" -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple edge-tts"
fi

# 浏览器：系统 chrome 或 playwright chromium
if [ -x /opt/google/chrome/chrome ] || command -v google-chrome >/dev/null 2>&1 \
   || command -v chromium >/dev/null 2>&1 || command -v chromium-browser >/dev/null 2>&1; then
  echo "  ✅ 系统 Chrome/Chromium（record.py 将自动使用）"; PASS=$((PASS+1))
else
  if ls "$HOME/.cache/ms-playwright"/chromium* >/dev/null 2>&1; then
    echo "  ✅ playwright chromium 已下载"; PASS=$((PASS+1))
  else
    echo "  ❌ 无可用浏览器"; FAIL=$((FAIL+1))
    echo "     └ 修复: $PY -m playwright install chromium"
    echo "       国内加速: PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright/ $PY -m playwright install chromium"
  fi
fi

# ffmpeg
FF="${FFMPEG:-}"
[ -z "$FF" ] && [ -x "$HERE/bin/ffmpeg" ] && FF="$HERE/bin/ffmpeg"
[ -z "$FF" ] && command -v ffmpeg >/dev/null 2>&1 && FF="ffmpeg"
if [ -n "$FF" ]; then
  echo "  ✅ ffmpeg ($FF)"; PASS=$((PASS+1))
else
  echo "  ❌ ffmpeg"; FAIL=$((FAIL+1))
  cat <<'EOF'
     └ 修复（任选其一）:
       1) apt install ffmpeg            （有 sudo）
       2) npm install ffmpeg-static      （二进制在 node_modules/ffmpeg-static/ffmpeg，
                                          设 export FFMPEG=<该路径>）
       3) 静态包: https://johnvansickle.com/ffmpeg/ 解压后放 $HERE/bin/ffmpeg
EOF
fi

# 中文字体（烧字幕需要，缺失仅警告）
if fc-list :lang=zh family 2>/dev/null | grep -qiE "noto|wenquanyi|wqy|UKai|UMing"; then
  echo "  ✅ 中文字体（可烧录字幕）"; PASS=$((PASS+1))
else
  echo "  ⚠ 无中文字体 → 字幕将不烧录/乱码"; WARN=$((WARN+1))
  echo "     └ 修复: apt install fonts-noto-cjk"
fi

echo
echo "结果: $PASS 通过 / $FAIL 失败 / $WARN 警告"
[ "$FAIL" -eq 0 ] && echo "🟢 环境就绪，可运行: bash $HERE/run.sh examples/hello/scenario.json"
exit $FAIL

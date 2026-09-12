#!/usr/bin/env bash
# demo-recorder 一键入口：配音 → 录屏 → 合成
# 用法:
#   bash run.sh <scenario.json>                 # 全流程
#   bash run.sh <scenario.json> -w myout        # 指定工作目录（默认 <剧本所在目录>/out）
#   bash run.sh <scenario.json> --skip-audio    # 复用已有配音（改操作不改台词时）
#   bash run.sh <scenario.json> --record-only   # 只录屏（无声版快速预览）
#   bash run.sh <scenario.json> --mix-only      # 只重新合成（换字幕/crf 时）
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
PY="$HERE/.venv/bin/python3"
[ -x "$PY" ] || PY=$(command -v python3)
SC=""; W=""; MODE="all"
for a in "$@"; do
  case "$a" in
    --skip-audio) MODE="skip_audio" ;;
    --record-only|--silent) MODE="record_only" ;;
    --mix-only) MODE="mix_only" ;;
    -w) : ;; # 值由下一个参数承接
    *) if [ "${PREV:-}" = "-w" ]; then W="$a"; else SC="$a"; fi ;;
  esac
  PREV="$a"
done
[ -n "$SC" ] || { head -9 "$0" | tail -7; exit 1; }
[ -f "$SC" ] || { echo "✗ 找不到剧本 $SC"; exit 1; }

run_gen()  { "$PY" "$HERE/scripts/gen_audio.py" "$SC" ${W:+-w "$W"} "$@"; }
run_rec()  { "$PY" "$HERE/scripts/record.py"    "$SC" ${W:+-w "$W"} "$@"; }
run_mix()  { "$PY" "$HERE/scripts/mix.py"       "$SC" ${W:+-w "$W"} "$@"; }

case "$MODE" in
  all)        run_gen && run_rec && run_mix ;;
  skip_audio) run_rec && run_mix ;;
  record_only) run_rec && echo "(无声预览: $W/raw.webm)" ;;
  mix_only)   run_mix ;;
esac

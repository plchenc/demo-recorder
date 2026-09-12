---
name: demo-recorder
description: >
  用自然语言创建录屏讲解视频：用户用一句话描述想演示什么，你写剧本 JSON →
  自动配音（edge-tts 神经语音）+ Playwright 真实操作录屏（headless Chrome，
  无需桌面）+ 字幕烧录 + ffmpeg 合成 mp4。用户不必会写代码或剪辑。
  适用于产品演示、操作教程、AI 应用 showcase 视频。
version: 1.2
---

# demo-recorder

把「一句话需求」变成「成品讲解视频」：`bash run.sh <剧本.json>` 一条命令
产出带配音和字幕的 mp4（H.264 + AAC，任何设备可播）。

## 接到自然语言需求时的工作流

1. **理解需求**：目标页面（URL）、讲什么（功能点/流程）、语言与声音偏好、时长
2. **探测页面**：不确定选择器时，先用一次性 playwright 脚本读目标页 DOM
   （类名/文案/placeholder），或让用户提供关键元素描述
3. **写剧本**：按下方速查生成 scenario.json（步骤=演示逻辑，narration=解说词）
4. **执行**：`bash run.sh <剧本.json>`；首次使用先跑 hello 示例验证环境
5. **交付**：报告成片路径 + 时长，说明可 `--skip-audio`/`--mix-only` 迭代

## 何时用

- 用户要给 Web 应用（含 Gradio/自研系统）录演示/教学视频
- 需要中文配音讲解 + 字幕，且操作画面必须真实（非 PPT 动画）
- 服务器无桌面环境（Wayland/Xorg 均可，headless Chrome 内部合成）

## 快速上手

```bash
bash install.sh                                    # 首次：独立 venv + 国内镜像
bash check_env.sh                                  # 自检（7 项）
bash run.sh examples/hello/scenario.json           # 跑通自带示例
bash run.sh <你的剧本.json> -w out                  # 正式使用
```

分步执行（调试用）：

```bash
.venv/bin/python3 scripts/gen_audio.py <剧本> -w out [--force]   # 只配音
.venv/bin/python3 scripts/record.py    <剧本> -w out [--no-strict] # 只录屏
.venv/bin/python3 scripts/mix.py       <剧本> -w out [--no-subtitle] # 只合成
```

## 剧本速查（完整格式见 README.md）

```json
{
  "base_url": "http://127.0.0.1:3101",   // 目标应用
  "viewport": [1280, 800], "subtitle": true, "out": "demo.mp4",
  "steps": [
    { "name": "intro", "banner_text": "标题角标",
      "narration": "这一步的解说词（自动配音+生成字幕）",
      "actions": [["goto", "/"], ["wait", 1500]] }
  ]
}
```

动作：`goto click dblclick fill type press select hover wait wait_text
wait_selector scroll eval snap`；定位器：CSS / `text=提交` / `ph:占位符` /
`role:button:发送`。

## 注意事项

- 改操作不改台词 → `--skip-audio` 复用配音；换字幕样式 → `--mix-only`
- 音画对齐原理：录制时记录每步起始毫秒（stamps.json），配音按此 adelay；
  每步画面自动停留 ≥ 解说时长，保证解说完整
- 配音失败多为网络（edge-tts 需访问微软服务）；字幕乱码=缺中文字体
  （`apt install fonts-noto-cjk`）
- Gradio 6.x 定位经验：优先 `role:tab:xxx`/`role:button:xxx`，动态内容用
  `wait_text`（轮询 body.innerText），不要依赖 DOM 快照
- ffmpeg 获取：`apt install ffmpeg` / `npm i ffmpeg-static` / 静态包放 `bin/`

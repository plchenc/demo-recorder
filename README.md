# demo-recorder — 网页演示视频一键成片

写一份 JSON 剧本，自动产出**带配音讲解、带字幕、画面真实操作**的 mp4 演示视频。

> **收到包的同事请从这里开始**（假设解压到任意目录）：
> ```bash
> cd demo-recorder
> bash install.sh       # 1. 装独立环境（约 2 分钟，国内镜像，不动系统）
> bash check_env.sh     # 2. 自检，全绿即就绪
> bash run.sh examples/hello/scenario.json   # 3. 跑通示例 → hello-demo.mp4
> ```
> 然后照第 3 节写你自己的剧本即可。卡住了看第 6 节 FAQ。

```
你的剧本.json ──► ① edge-tts 配音（微软神经语音，无需 API key）
                  ② Playwright 录屏（headless Chrome，真实操作页面）
                  ③ ffmpeg 合成（音画对齐 + 字幕烧录 + H.264）
                          │
                          ▼
                 demo.mp4（H.264 + AAC，任何设备可播）
```

**特点**
- ✅ 真实操作：视频里的每次点击、输入都是浏览器真实执行，无剪辑无拼接
- ✅ 无需桌面：headless Chrome 内部合成录屏，纯服务器（无 GUI/Wayland）可用
- ✅ 中文配音：微软 edge-tts 神经语音（默认晓晓女声），无需 API key
- ✅ 自动字幕：解说词按句切分、自动对时间轴、烧录进画面（可关）
- ✅ 音画对齐：每步画面自动停留 ≥ 解说时长，解说永远完整不被截断
- ✅ 环境自包含：独立 venv，国内镜像安装，不影响系统

---

## 1. 安装（一次性）

```bash
bash install.sh     # 独立 venv + playwright + edge-tts（清华镜像）+ 浏览器
bash check_env.sh   # 7 项自检，全绿即就绪
```

浏览器优先复用系统 Chrome/Chromium（Linux/macOS 自动探测）；没有则自动下载
playwright chromium（npmmirror 镜像加速）。

**ffmpeg 需自备**（包里不带二进制）：

| 平台 | 安装方式 |
|---|---|
| macOS | `brew install ffmpeg`（推荐先装 [Homebrew](https://brew.sh)） |
| Linux 有 sudo | `apt install ffmpeg` |
| 通用（无 sudo） | `npm install ffmpeg-static` 后 `export FFMPEG=<二进制路径>`；或静态包（Linux [johnvansickle](https://johnvansickle.com/ffmpeg/) / macOS [evermeet.cx](https://evermeet.cx/ffmpeg/)）解压放 `bin/ffmpeg` |

**macOS 额外说明**：
- `python3` 由 Xcode 命令行工具提供：首次使用先跑 `xcode-select --install`
- 中文字体系统自带（苹方 PingFang SC），字幕直接可用；若烧录乱码：
  `export DEMO_SUB_FONT='PingFang SC'`
- Apple Silicon（M1/M2/M3/M4）与 Intel 均支持，playwright/edge-tts 均有原生轮子
- "无法验证开发者"提示与本项目无关（我们不装内核扩展/APP，仅命令行工具）

## 2. 五分钟上手

```bash
bash run.sh examples/hello/scenario.json
# 产出 hello-demo.mp4（工作目录 examples/hello/out/）
```

自带示例演示了点击、逐字输入、下拉选择、等待文本四类动作。

**在线网站示例**（真实用户案例，Mac 上录制）：

```bash
bash run.sh examples/apple/scenario.json
# Apple 官网首页菜单讲解：hover 展开导航子菜单 + 滚动 + 5 段解说，58s 成片
```

展示了进阶用法：`:has-text()` 组合定位、`hover` 触发悬浮菜单、`eval` 派发事件
收起菜单。注意：在线示例依赖目标站点当前结构与网络可达性，站点改版后需更新
剧本中的选择器。

## 3. 写你自己的剧本

新建 `my.json`（完整字段见第 4 节），然后：

```bash
bash run.sh my.json                 # 全流程
bash run.sh my.json -w out2         # 指定工作目录
bash run.sh my.json --skip-audio    # 改了操作、没改台词 → 复用已有配音
bash run.sh my.json --record-only   # 只录屏（无声快速预览）
bash run.sh my.json --mix-only      # 只重新合成（换字幕开关/清晰度）
```

剧本最小结构：

```json
{
  "base_url": "http://127.0.0.1:8080",
  "steps": [
    {
      "name": "intro",
      "banner_text": "MyApp 功能演示",
      "narration": "大家好，欢迎观看 MyApp 演示。",
      "actions": [["goto", "/"], ["wait", 1500]]
    },
    {
      "name": "create",
      "banner_text": "① 新建订单",
      "narration": "点击新建按钮，填写客户和产品，提交后立即看到结果。",
      "actions": [
        ["click", "role:button:新建"],
        ["type", "ph:请输入客户名", "华为技术", 45],
        ["select", "#product", "A100"],
        ["click", "text=提交"],
        ["wait_text", "创建成功", 10000]
      ],
      "pause_after": 1.5
    }
  ]
}
```

## 4. 剧本字段全表

**顶层（meta）**

| 字段 | 默认 | 说明 |
|---|---|---|
| `base_url` | 必填 | 目标应用入口；步骤内相对路径会拼在它后面 |
| `viewport` | [1280,800] | 视频分辨率 |
| `voice` | 晓晓(女) | edge-tts 语音。男声 `zh-CN-YunxiNeural`；其他见 `edge-tts --list-voices` |
| `rate` | "+8%" | 语速（可 "-10%" 放慢） |
| `subtitle` | true | 是否烧录字幕（srt 文件总会生成，可外挂） |
| `banner` | true | 右下角步骤角标（当前演示到哪一步） |
| `out` | out/demo.mp4 | 成片路径 |
| `tail_hold` | 1.5 | 结束后静止秒数 |
| `chrome_path` | 自动 | 指定浏览器（默认自动找系统 Chrome → playwright 内置） |

**每个 step**

| 字段 | 说明 |
|---|---|
| `name` | 步骤名（音频文件/时间戳按它对齐，需唯一） |
| `narration` | 解说词（配音 + 字幕来源；留空=纯操作无声段） |
| `banner_text` | 角标文字（支持 \n 换行）；不填则沿用上一个 |
| `actions` | 动作序列（下表） |
| `pause_after` | 本步结束后画面停留秒数（音频对齐会自动取更大值） |

**动作（actions）**

| 动作 | 示例 | 说明 |
|---|---|---|
| `goto` | `["goto", "/order"]` | 打开页面（绝对 URL 直接用，相对拼 base_url） |
| `click` | `["click", "text=提交", 400]` | 点击；第 3 项=点击后等待 ms |
| `dblclick` | `["dblclick", "#cell"]` | 双击 |
| `fill` | `["fill", "#qty", "100"]` | 整体填入（瞬间） |
| `type` | `["type", "ph:客户名", "华为", 45]` | 逐字输入（第 4 项=每字间隔 ms，真人感） |
| `press` | `["press", "Enter"]` | 键盘 |
| `select` | `["select", "#prod", "A100"]` | 下拉选择 |
| `hover` | `["hover", "#menu"]` | 悬停 |
| `wait` | `["wait", 1500]` | 停留 |
| `wait_text` | `["wait_text", "创建成功", 10000]` | 轮询页面文字出现（SPA 神器） |
| `wait_selector` | `["wait_selector", ".done", 10000]` | 等元素出现 |
| `scroll` | `["scroll", 600]` | 滚轮下滑 |
| `eval` | `["eval", "window.scrollTo(0,0)"]` | 执行 JS |
| `snap` | `["snap", "checkpoint"]` | 存调试截图（不影响视频） |

**定位器写法**（所有动作用的第一个字符串）

| 写法 | 匹配 | 示例 |
|---|---|---|
| CSS | 元素 | `#submit`、`.toolbar button` |
| `text=xxx` | 可见文本 | `text=提交订单` |
| `ph:xxx` | 输入框 placeholder | `ph:请输入客户名` |
| `role:角色:名称` | ARIA 角色精确匹配 | `role:button:发送`、`role:tab:本体建模` |

## 5. 工作原理（音画对齐）

```
① gen_audio: 解说词 → seg_01_xxx.mp3 … + manifest.json（每段精确时长）
② record:    录屏时记 stamps.json = 每步起始毫秒；每步停留 ≥ 解说时长
③ mix:       ffmpeg filter_complex
             [n]adelay=<stamp_ms> → amix(normalize=0 保持音量) → aac
             视频: scale + subtitles(srt 烧录) → libx264 yuv420p faststart
```

出问题时可分别重跑三步（见 run.sh 分步模式）；`out/` 下保留中间产物
（raw.webm / stamps.json / subtitles.srt / audio/ / snaps/）。

## 6. 常见问题

| 现象 | 原因与解决 |
|---|---|
| 配音失败/超时 | edge-tts 需访问微软服务，检查外网；脚本自动重试 3 次 |
| 字幕方块/乱码 | 缺中文字体：`apt install fonts-noto-cjk`（无字体时会警告） |
| 找不到 ffmpeg | `apt install ffmpeg` / `npm i ffmpeg-static` / 放 `bin/ffmpeg` / `export FFMPEG=...` |
| 找不到元素 | 用 `snap` 动作存截图肉眼核对；SPA 动态内容用 `wait_text` 而非固定 wait |
| Gradio 页面 | Tab 用 `role:tab:名称`，按钮 `role:button:名称`；Accordion 展开后的内容才在 DOM |
| root 容器 | 已自动加 `--no-sandbox`；视频闪烁则加 `--disable-dev-shm-usage`（已默认） |
| 想换声音 | `voice` 字段；列出全部：`.venv/bin/edge-tts --list-voices | grep zh-CN` |
| 音量小 | mix.py 里 `volume=1.0` 调大（如 1.4） |
| macOS 字幕乱码 | `export DEMO_SUB_FONT='PingFang SC'`；若 ffmpeg 为 brew 安装仍乱码，换 `brew install --cask font-noto-cjk` 后用 Noto Sans CJK SC |
| macOS 找不到浏览器 | 装了 Chrome 即自动识别；未装则 install.sh 会下载 playwright chromium |

## 7. 在 opencode / Claude Code 等 Agent 中安装

SKILL.md 遵循 [Agent Skills](https://agentskills.io) 开放规范，兼容 opencode、
Claude Code 等支持该规范的工具。以 opencode 为例：

```bash
git clone https://github.com/plchenc/demo-recorder.git
mkdir -p ~/.config/opencode/skills
ln -s "$(pwd)/demo-recorder" ~/.config/opencode/skills/demo-recorder   # 软链，git pull 即更新
opencode run "用 demo-recorder 的 hello 示例录一段（--skip-audio）"      # agent 自主执行
```

Claude Code：`ln -s ... ~/.claude/skills/demo-recorder`（同样识别 SKILL.md）。

## 8. 目录结构

```
demo-recorder/
├── SKILL.md            # agent 视角说明（简版）
├── README.md           # 本文档
├── install.sh          # 一键安装
├── check_env.sh        # 环境自检
├── run.sh              # 一键入口
├── scripts/
│   ├── gen_audio.py    # ① 配音
│   ├── record.py       # ② 录屏
│   └── mix.py          # ③ 合成
├── examples/hello/     # 自包含教学示例（静态页+剧本）
└── bin/                # 可选：放 ffmpeg 二进制
```

# tts-mcp-server — 中文TTS聚合MCP Server

> 一个 MCP Server，把**中文语音合成 + 精确字幕对齐**做成 Agent 可调用的工具。
> 多引擎聚合：**Edge-TTS（在线免费）** + **Piper（离线免费）**，统一音色目录，用户无感切换。

## 演示

![字幕对齐演示](assets/demo_subtitles.gif)

> 文本 → 语音 + 逐词对齐字幕（真实引擎时间戳，非估算）

## 为什么做这个

现有 TTS MCP 生态里：
- Edge-TTS 的 MCP 都是**单引擎薄壳**（最高 8★、只活 2 天、只有 1 个 `text_to_speech` 工具）
- **没有任何一个能生成字幕** —— 但字幕对齐才是视频/播客/有声书的刚需
- CosyVoice 等本地克隆的中文 MCP 有效实现 = **0**

本项目的杀手锏：**synthesize_with_subtitles** —— 文本转语音的同时，从引擎的真实边界事件生成**逐词对齐的 SRT 字幕**，可直接烧录到视频。

## 核心能力

| 工具 | 说明 |
|---|---|
| `list_voices` | 列出全部音色（14个中文，含方言/港台），按引擎/性别/方言过滤 |
| `synthesize` | 文本 → MP3 + SRT，多引擎聚合，支持预设 |
| `synthesize_with_subtitles` ⭐ | 文本 → 语音 + **引擎级时间戳字幕**（Edge用WordBoundary词级，Piper用音素对齐字符级） |
| `batch_synthesize` ⭐⭐ | **批量并行合成**：多段文本并发TTS（实测提速13倍），每段独立音频+字幕 |
| Resource: `tts://voice/config` | 音色目录 + 5个预设（新闻/小说/方言/会议/离线） |

## 字幕对齐原理

**不是估算，是引擎的真实时间戳**：

```
Edge-TTS: WordBoundary 事件 → 词级 {start_s, end_s}
Piper:    本地离线，字符级时间戳（无网可用，CPU极快 RTF<0.1）
→ 统一合并为 SRT 行（硬断点优先 + 字符/时长双限）
```

实测：最后一条字幕的结束时间 = 音频真实总时长，误差 <0.5s。

## 安装

```bash
pip install tts-mcp-server        # 干净底座（字幕算法 + 框架）
pip install tts-mcp-server[edge]  # + Edge-TTS 引擎（推荐，默认）
pip install tts-mcp-server[piper] # + Piper 离线引擎（可选，断网兜底）
```

## 使用

### Claude Desktop

`claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "tts-server": {
      "command": "tts-mcp",
      "args": [],
      "env": { "TTS_OUTPUT_DIR": "/path/to/tts_out" }
    }
  }
}
```

### Cursor

`.cursor/mcp.json`:
```json
{
  "mcpServers": {
    "tts-server": {
      "type": "stdio",
      "command": "tts-mcp",
      "args": []
    }
  }
}
```

## 演示用例：会议纪要 → 带字幕的播客

```
调用 synthesize_with_subtitles(
  text="各位同事早上好，本次周会将讨论三个议题……",
  preset="meeting"
)
→ 得到 meeting.mp3 + meeting.srt
→ 播放器加载 SRT，逐句跟读，重点可跳转
```

## 预设

| 预设 | 音色 | 语速 | 场景 |
|---|---|---|---|
| news | 云扬（男） | +5% | 新闻播报 |
| novel | 云希（男） | 0 | 有声小说 |
| dialect | 晓北（东北话） | 0 | 方言演示 |
| meeting | 晓晓（女） | +5% | 会议纪要 |
| offline | 华炎（Piper） | 0 | 断网离线 |

## 路线图

- [x] P0: Edge-TTS 引擎 + 字幕对齐 + 预设
- [ ] P1: 百度 TTS 接入（个人实名免费额度）+ whisper 转写
- [ ] P2: 视频翻译配音工作流（ffmpeg 合成）

## License

MIT。引擎适配层（`engines/edge` 依赖 edge-tts GPL-3.0、`engines/piper` 依赖 piper-tts GPL-3.0）通过 optional-dependencies + 晚绑定隔离，主包许可证干净。

---

## 系列（Chinese MCP Suite）

> 中文内容创作/工具 MCP 全家桶，全本地、CPU、离线：


- **tts-mcp-server**（本仓库）— TTS聚合+字幕对齐
- [idphoto-mcp](https://github.com/Gollum-code/idphoto-mcp) — 本地证件照
- [audio-post-mcp](https://github.com/Gollum-code/audio-post-mcp) — 音频后期
- [video-workflow-mcp](https://github.com/Gollum-code/video-workflow-mcp) — 视频工作流
- [poetry-mcp](https://github.com/Gollum-code/poetry-mcp) — 古诗文
- [script-mcp](https://github.com/Gollum-code/script-mcp) — 口播文案
- [asset-mcp](https://github.com/Gollum-code/asset-mcp) — 素材库
- [idiom-mcp](https://github.com/Gollum-code/idiom-mcp) — 成语典故
- [weather-mcp](https://github.com/Gollum-code/weather-mcp) — 天气/空气


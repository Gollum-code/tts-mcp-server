# tts-mcp-server — Chinese TTS Aggregation MCP Server

> A Model Context Protocol server that turns **Chinese text-to-speech + precise subtitle alignment** into tools any agent can call.
> Multi-engine aggregation: **Edge-TTS (free online)** + **Piper (offline free)**, unified voice catalog, transparent engine switching.

## Demo

![Subtitle alignment demo](assets/demo_subtitles.gif)

> Text → speech + word-aligned subtitles (REAL engine timestamps, not estimates)

## Why

In the TTS MCP ecosystem:
- Edge-TTS MCPs are all **thin single-engine shells** (max 8★, lived 2 days, only 1 `text_to_speech` tool)
- **None generate subtitles** — but subtitle alignment is the real need for video/podcast/audiobook
- CosyVoice-style local-clone Chinese MCPs: effective count = **0**

This project's killer feature: **synthesize_with_subtitles** — while synthesizing speech, generate **word-aligned SRT subtitles from the engine's real boundary events**.

## Core tools

| Tool | Description |
|---|---|
| `list_voices` | All voices (14 Chinese incl. dialects/HK/TW), filter by engine/gender/dialect |
| `synthesize` | Text → MP3 + SRT, multi-engine, presets |
| `synthesize_with_subtitles` ⭐ | Text → speech + **engine-level timestamp subtitles** (Edge WordBoundary word-level, Piper char-level) |
| `batch_synthesize` ⭐⭐ | **Parallel batch synthesis** (measured 13x speedup), per-segment audio+subtitles |
| Resource: `tts://voice/config` | Voice catalog + 5 presets (news/novel/dialect/meeting/offline) |

## Subtitle alignment principle

**Not estimated — real engine timestamps**:

```
Edge-TTS: WordBoundary events → word-level {start_s, end_s}
Piper:    local offline, char-level timestamps (no network, CPU RTF < 0.1)
→ merged into SRT lines (hard-break priority + char/duration dual limits)
```

Measured: last subtitle line's end time == audio real duration, error < 0.5s.

## Install

```bash
pip install tts-mcp-server          # clean core (subtitle algo + framework)
pip install tts-mcp-server[edge]    # + Edge-TTS engine (recommended, default)
pip install tts-mcp-server[piper]   # + Piper offline engine (optional, no-network fallback)
```

## Usage

### Claude Desktop

`claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "tts-server": {
      "command": "tts-mcp",
      "args": []
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

## Example: meeting notes → podcast with subtitles

```
synthesize_with_subtitles(
  text="各位同事早上好，本次周会将讨论三个议题……",
  preset="meeting"
)
→ meeting.mp3 + meeting.srt
→ load SRT in player, sentence-by-sentence follow-along
```

## Presets

| Preset | Voice | Speed | Use case |
|---|---|---|---|
| news | 云扬 (male) | +5% | news broadcast |
| novel | 云希 (male) | 0 | audiobook |
| dialect | 晓北 (NE dialect) | 0 | dialect demo |
| meeting | 晓晓 (female) | +5% | meeting notes |
| offline | 华炎 (Piper) | 0 | offline/no-network |

## License

MIT. Engine adapters isolate GPL deps (edge-tts GPL-3.0, piper-tts GPL-3.0) via optional-dependencies + late-binding.

## Series

[Chinese MCP Suite](https://github.com/Gollum-code) — 9 local-first Chinese MCP servers: TTS, ID photo, audio post, video workflow, poetry, scripts, asset library, idioms, weather. All local/CPU/offline/MIT.

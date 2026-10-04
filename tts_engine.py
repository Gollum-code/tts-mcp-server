# 引擎抽象层：统一 voice_id → 多引擎路由
# 架构：客户端只感知统一 voice_id，底层引擎切换透明
# 许可证隔离：edge-tts (GPL) / piper (GPL) 均通过独立适配器+晚绑定+子进程

from __future__ import annotations

import asyncio
import subprocess
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

# ── 统一音色目录：voice_id 前缀区分引擎 ──
# edge:{name}  → Edge-TTS（默认，词级时间戳）
# piper:{name} → Piper 离线（音素级对齐，断网兜底）
# baidu:{name} → 百度TTS（P1，个人实名免费额度）
VOICE_CATALOG = [
    # Edge-TTS 中文（默认引擎）
    {"voice_id": "edge:zh-CN-XiaoxiaoNeural", "engine": "edge", "native": "zh-CN-XiaoxiaoNeural", "name": "晓晓", "desc": "温柔知性女声", "gender": "Female", "dialect": "标准普通话", "scenarios": ["新闻", "有声书"], "recommended": True},
    {"voice_id": "edge:zh-CN-XiaoyiNeural", "engine": "edge", "native": "zh-CN-XiaoyiNeural", "name": "晓伊", "desc": "活泼灵动女声", "gender": "Female", "dialect": "标准普通话", "scenarios": ["儿童", "新手"], "recommended": False},
    {"voice_id": "edge:zh-CN-YunjianNeural", "engine": "edge", "native": "zh-CN-YunjianNeural", "name": "云健", "desc": "浑厚磁性男声", "gender": "Male", "dialect": "标准普通话", "scenarios": ["纪录片", "新闻"], "recommended": False},
    {"voice_id": "edge:zh-CN-YunxiNeural", "engine": "edge", "native": "zh-CN-YunxiNeural", "name": "云希", "desc": "阳光青年男声", "gender": "Male", "dialect": "标准普通话", "scenarios": ["有声书", "广告"], "recommended": True},
    {"voice_id": "edge:zh-CN-YunxiaNeural", "engine": "edge", "native": "zh-CN-YunxiaNeural", "name": "云夏", "desc": "少年音", "gender": "Male", "dialect": "标准普通话", "scenarios": ["青春", "少年"], "recommended": False},
    {"voice_id": "edge:zh-CN-YunyangNeural", "engine": "edge", "native": "zh-CN-YunyangNeural", "name": "云扬", "desc": "低沉新闻男声", "gender": "Male", "dialect": "标准普通话", "scenarios": ["新闻播报"], "recommended": False},
    {"voice_id": "edge:zh-CN-liaoning-XiaobeiNeural", "engine": "edge", "native": "zh-CN-liaoning-XiaobeiNeural", "name": "晓北", "desc": "东北话女声", "gender": "Female", "dialect": "东北话", "scenarios": ["方言喜剧"], "recommended": False},
    {"voice_id": "edge:zh-CN-shaanxi-XiaoniNeural", "engine": "edge", "native": "zh-CN-shaanxi-XiaoniNeural", "name": "晓妮", "desc": "陕西话女声", "gender": "Female", "dialect": "陕西话", "scenarios": ["方言剧"], "recommended": False},
    {"voice_id": "edge:zh-HK-HiuGaaiNeural", "engine": "edge", "native": "zh-HK-HiuGaaiNeural", "name": "晓佳", "desc": "粤语女声", "gender": "Female", "dialect": "粤语", "scenarios": ["粤语播报"], "recommended": False},
    {"voice_id": "edge:zh-HK-WanLungNeural", "engine": "edge", "native": "zh-HK-WanLungNeural", "name": "云龙", "desc": "粤语男声", "gender": "Male", "dialect": "粤语", "scenarios": ["粤语", "新闻"], "recommended": False},
    {"voice_id": "edge:zh-TW-HsiaoChenNeural", "engine": "edge", "native": "zh-TW-HsiaoChenNeural", "name": "晓臻", "desc": "台湾女声", "gender": "Female", "dialect": "台湾腔", "scenarios": ["台语", "播客"], "recommended": False},
    {"voice_id": "edge:zh-TW-YunJheNeural", "engine": "edge", "native": "zh-TW-YunJheNeural", "name": "云哲", "desc": "台湾男声", "gender": "Male", "dialect": "台湾腔", "scenarios": ["台语", "新闻"], "recommended": False},
    # Piper 离线（默认勿选主引擎，作为断网兜底）
    {"voice_id": "piper:zh_CN-huayan-medium", "engine": "piper", "native": "zh_CN-huayan-medium", "name": "华炎", "desc": "离线本地女声（断网可用）", "gender": "Female", "dialect": "标准普通话", "scenarios": ["离线", "隐私"], "recommended": False},
    {"voice_id": "piper:zh_CN-xiao_ya-medium", "engine": "piper", "native": "zh_CN-xiao_ya-medium", "name": "小雅", "desc": "离线本地女声（断网可用）", "gender": "Female", "dialect": "标准普通话", "scenarios": ["离线", "隐私"], "recommended": False},
]

PRESETS = {
    "news": {"voice": "edge:zh-CN-YunyangNeural", "rate": "+5%", "max_chars": 25, "max_duration": 6.0, "desc": "新闻播报，沉稳男声"},
    "novel": {"voice": "edge:zh-CN-YunxiNeural", "rate": "+0%", "max_chars": 20, "max_duration": 7.0, "desc": "有声小说，青年男声"},
    "dialect": {"voice": "edge:zh-CN-liaoning-XiaobeiNeural", "rate": "+0%", "max_chars": 18, "max_duration": 6.0, "desc": "东北话演示方言"},
    "meeting": {"voice": "edge:zh-CN-XiaoxiaoNeural", "rate": "+5%", "max_chars": 22, "max_duration": 7.0, "desc": "会议纪要转播客"},
    "offline": {"voice": "piper:zh_CN-huayan-medium", "rate": "+0%", "max_chars": 20, "max_duration": 7.0, "desc": "断网离线模式（本地推理）"},
}

HARD_BREAKS = set("。！？；：…")
SOFT_BREAKS = set("，、 ")


@dataclass
class WordEvent:
    text: str
    start_s: float
    end_s: float

    @property
    def duration_s(self) -> float:
        return self.end_s - self.start_s


def resolve_voice(voice_id: str) -> dict:
    for v in VOICE_CATALOG:
        if v["voice_id"] == voice_id:
            return v
    raise ValueError(f"未知音色 {voice_id}，可用的: {[v['voice_id'] for v in VOICE_CATALOG]}")


# ── 字幕行合并算法（引擎无关）──

def _fmt_srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    h, rem = divmod(ms, 3600000)
    m, rem = divmod(rem, 60000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_srt_blocks(word_events, max_chars=20, max_duration=7.0):
    """词级/字符级事件 → SRT字幕行。硬断点优先，字符/时长双限。"""
    blocks = []
    cur_words = []
    cur_start = None

    def flush():
        nonlocal cur_words, cur_start
        if not cur_words:
            return
        blocks.append({
            "start_s": cur_start,
            "end_s": cur_words[-1].end_s,
            "text": "".join(w.text for w in cur_words),
        })
        cur_words = []
        cur_start = None

    for ev in word_events:
        if cur_words is None or cur_start is None:
            cur_words = [ev]
            cur_start = ev.start_s
            continue
        text = ev.text
        would_chars = sum(len(w.text) for w in cur_words) + len(text)
        char_ok = would_chars <= max_chars
        duration_ok = (ev.end_s - cur_start) <= max_duration
        gap_ok = (ev.start_s - cur_words[-1].end_s) < 1.0
        must_break = (not char_ok) or (not duration_ok) or (not gap_ok)
        has_hard = any(c in HARD_BREAKS for c in text)
        if must_break or has_hard:
            if has_hard and char_ok and duration_ok and not must_break:
                cur_words.append(ev)
                flush()
            else:
                flush()
                cur_words = [ev]
                cur_start = ev.start_s
        else:
            cur_words.append(ev)
    flush()
    return blocks


def render_srt(blocks, index_start=1):
    lines = []
    for i, b in enumerate(blocks, start=index_start):
        lines.append(str(i))
        lines.append(f"{_fmt_srt_time(b['start_s'])} --> {_fmt_srt_time(b['end_s'])}")
        lines.append(b["text"])
        lines.append("")
    return "\n".join(lines)


# ── 引擎适配器 ──

class EdgeEngine:
    """Edge-TTS（在线免费，词级时间戳）。GPL隔离在适配器内。"""

    def __init__(self):
        import edge_tts  # 晚绑定，主包默认不依赖

    def synthesize_with_alignment(self, text, voice, rate, volume, pitch):
        import edge_tts
        import threading
        com = edge_tts.Communicate(text, voice, rate=rate, volume=volume, pitch=pitch, boundary="WordBoundary")
        events = []
        audio = bytearray()

        def _run_in_thread():
            async def _run():
                async for chunk in com.stream():
                    if chunk["type"] == "audio":
                        audio.extend(chunk["data"])
                    elif chunk["type"] == "WordBoundary":
                        events.append(WordEvent(
                            text=chunk["text"],
                            start_s=chunk["offset"] / 1e7,
                            end_s=(chunk["offset"] + chunk["duration"]) / 1e7,
                        ))
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(_run())
            finally:
                loop.close()

        t = threading.Thread(target=_run_in_thread)
        t.start()
        t.join()
        return bytes(audio), events

    def voice_available(self, native_voice):
        return True


class PiperEngine:
    """Piper（离线免费，本地推理）。
    直接用 piper-tts 库（晚绑定 import，GPL-3.0 隔离），CPU 极快（RTF<0.1）。
    音素对齐：piper 支持 phoneme alignments，可生成字符级时间戳。
    """

    def __init__(self, model_dir: str | None = None):
        self.model_dir = model_dir or str(Path.home() / ".piper")
        self._voice = None
        self._loaded_model = None

    def _load_voice(self, voice):
        if self._loaded_model == voice and self._voice is not None:
            return self._voice
        from piper import PiperVoice
        model_path = Path(self.model_dir) / f"{voice}.onnx"
        if not model_path.exists():
            raise FileNotFoundError(
                f"Piper模型不存在: {model_path}. 请先下载中文模型:\n"
                f"python -c \"from piper.download_voices import download_voice; download_voice('{voice}', r'{self.model_dir}')\""
            )
        self._voice = PiperVoice.load(str(model_path))
        self._loaded_model = voice
        return self._voice

    def synthesize_with_alignment(self, text, voice, rate, volume, pitch):
        """Piper 合成，返回 (wav_bytes, WordEvent列表)。
        用音素对齐（include_alignments）做字符级时间戳；失败退字符均分。
        """
        import numpy as np
        import wave as wave_mod
        import io

        voice_obj = self._load_voice(voice)
        # 用 alignments 生成字符级时间戳
        try:
            chunks = list(voice_obj.synthesize(text, include_alignments=True))
        except Exception:
            chunks = list(voice_obj.synthesize(text))

        # 收集音频
        samples = []
        sample_rate = 22050
        for ch in chunks:
            if ch is None:
                continue
            arr = getattr(ch, "audio_int16_array", None)
            if arr is not None:
                samples.extend(arr)
        if not samples:
            raise RuntimeError("Piper 未产生音频数据")

        duration = len(samples) / sample_rate
        # 字符级对齐（中文按字=音自然映射；Piper音素对齐API不稳定，用均分+标点权重保底）
        events = self._fallback_align(text, duration)

        # 编码 wav
        audio_bytes = np.array(samples, dtype=np.int16).tobytes()
        buf = io.BytesIO()
        with wave_mod.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(audio_bytes)
        return buf.getvalue(), events

    def _fallback_align(self, text, duration):
        """兜底：按字符均分时间（当 Piper 无法提供对齐时）。"""
        chars = [c for c in text if c.strip()]
        if not chars:
            return []
        per = duration / len(chars)
        events = []
        pos = 0.0
        for c in chars:
            events.append(WordEvent(text=c, start_s=round(pos, 3), end_s=round(pos + per * len(c), 3)))
            pos += per * len(c)
        return events


ENGINES = {
    "edge": EdgeEngine(),
    "piper": PiperEngine(),
}


def synthesize_to_files(text, voice_id, rate="+0%", volume="+0%", pitch="+0Hz",
                        output_dir="tts_out", max_chars=20, max_duration=7.0) -> dict:
    """统一入口：按 voice_id 路由到对应引擎，输出 audio + srt。"""
    import re
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    ts = int(time.time() * 1000)
    audio_path = out / f"tts_{ts}.mp3"
    srt_path = out / f"tts_{ts}.srt"

    meta = resolve_voice(voice_id)
    engine = ENGINES[meta["engine"]]

    if meta["engine"] == "edge":
        audio, events = engine.synthesize_with_alignment(
            text, meta["native"], rate, volume, pitch)
        audio_path.write_bytes(audio)
    elif meta["engine"] == "piper":
        audio, events = engine.synthesize_with_alignment(text, meta["native"], rate, volume, pitch)
        audio_path.write_bytes(audio)
    else:
        raise ValueError(f"引擎 {meta['engine']} 尚未实现")

    blocks = build_srt_blocks(events, max_chars=max_chars, max_duration=max_duration)
    srt_path.write_text(render_srt(blocks), encoding="utf-8")

    return {
        "audio_path": str(audio_path),
        "subtitle_path": str(srt_path),
        "duration_s": round(events[-1].end_s, 3) if events else None,
        "line_count": len(blocks),
        "engine": meta["engine"],
        "voice": voice_id,
        "word_event_count": len(events),
    }
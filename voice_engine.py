"""
Voice Engine — Speech-to-Text + Text-to-Speech
STT: OpenAI Whisper (local, via faster-whisper or whisper.cpp)
TTS: pyttsx3 (offline) with edge-tts fallback (online)
"""

import asyncio
import base64
import io
import logging
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import AsyncGenerator, Dict, List, Optional

log = logging.getLogger("synapse.voice")

AUDIO_DIR = Path("./data/audio")
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

# Supported TTS engines (in preference order)
TTS_ENGINES = ["edge-tts", "pyttsx3", "espeak"]


class VoiceEngine:
    def __init__(self):
        self._whisper_model = None
        self._tts_engine    = None
        self._tts_voices: List[str] = []
        self._default_voice = ""
        self._stt_available = False
        self._tts_available = False

    # ── Initialise ────────────────────────────────────────────────────────────
    async def init(self):
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._detect_engines)

    def _detect_engines(self):
        # Detect STT (Whisper)
        try:
            import faster_whisper
            self._stt_available = True
            log.info("STT: faster-whisper available")
        except ImportError:
            try:
                result = subprocess.run(
                    ["whisper", "--help"], capture_output=True, timeout=3
                )
                self._stt_available = result.returncode == 0
                if self._stt_available:
                    log.info("STT: whisper CLI available")
            except Exception:
                log.info("STT: not available (pip install faster-whisper)")

        # Detect TTS
        for engine in TTS_ENGINES:
            if engine == "edge-tts":
                try:
                    import edge_tts
                    self._tts_engine = "edge-tts"
                    self._tts_available = True
                    log.info("TTS: edge-tts available")
                    break
                except ImportError:
                    pass
            elif engine == "pyttsx3":
                try:
                    import pyttsx3
                    eng = pyttsx3.init()
                    voices = eng.getProperty("voices")
                    self._tts_voices = [v.id for v in (voices or [])]
                    if self._tts_voices:
                        self._default_voice = self._tts_voices[0]
                    self._tts_engine = "pyttsx3"
                    self._tts_available = True
                    log.info(f"TTS: pyttsx3 available ({len(self._tts_voices)} voices)")
                    break
                except Exception:
                    pass
            elif engine == "espeak":
                try:
                    r = subprocess.run(
                        ["espeak", "--version"], capture_output=True, timeout=3
                    )
                    if r.returncode == 0:
                        self._tts_engine = "espeak"
                        self._tts_available = True
                        log.info("TTS: espeak available")
                        break
                except Exception:
                    pass

    # ── STT: Audio → Text ─────────────────────────────────────────────────────
    async def transcribe(
        self,
        audio_bytes: bytes,
        language: str = "auto",
        fmt: str = "webm",
    ) -> Dict:
        """Transcribe audio bytes to text using Whisper."""
        if not self._stt_available:
            return {"success": False,
                    "error": "Whisper not installed. Run: pip install faster-whisper"}

        # Save to temp file
        suffix = f".{fmt}" if fmt else ".webm"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(audio_bytes)
            tmp_path = f.name

        try:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None, lambda: self._transcribe_sync(tmp_path, language)
            )
            return result
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    def _transcribe_sync(self, audio_path: str, language: str) -> Dict:
        start = time.time()
        try:
            # Try faster-whisper first
            try:
                from faster_whisper import WhisperModel
                if self._whisper_model is None:
                    log.info("Loading Whisper model (base)…")
                    self._whisper_model = WhisperModel(
                        "base", device="cpu", compute_type="int8"
                    )
                segments, info = self._whisper_model.transcribe(
                    audio_path,
                    language=None if language == "auto" else language,
                    beam_size=5,
                )
                text = " ".join(s.text for s in segments).strip()
                return {
                    "success": True,
                    "text": text,
                    "language": info.language,
                    "duration_s": round(time.time() - start, 2),
                    "engine": "faster-whisper",
                }
            except ImportError:
                pass

            # Fallback: whisper CLI
            cmd = ["whisper", audio_path, "--model", "base",
                   "--output_format", "txt", "--output_dir", str(AUDIO_DIR)]
            if language != "auto":
                cmd += ["--language", language]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if r.returncode != 0:
                return {"success": False, "error": r.stderr}

            txt_file = AUDIO_DIR / (Path(audio_path).stem + ".txt")
            text = txt_file.read_text().strip() if txt_file.exists() else ""
            return {
                "success": True,
                "text": text,
                "duration_s": round(time.time() - start, 2),
                "engine": "whisper-cli",
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── TTS: Text → Audio ─────────────────────────────────────────────────────
    async def synthesise(
        self,
        text: str,
        voice: str = "",
        speed: float = 1.0,
    ) -> Dict:
        """Convert text to speech, return base64 audio."""
        if not self._tts_available:
            return {"success": False,
                    "error": "No TTS engine. Run: pip install edge-tts  OR  pip install pyttsx3"}
        if not text.strip():
            return {"success": False, "error": "Empty text"}

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, lambda: self._synthesise_sync(text.strip(), voice, speed)
        )
        return result

    async def synthesise_stream(
        self, text: str, voice: str = ""
    ) -> AsyncGenerator[bytes, None]:
        """Stream TTS audio chunks (edge-tts only)."""
        if self._tts_engine == "edge-tts":
            try:
                import edge_tts
                v = voice or "en-US-AriaNeural"
                communicate = edge_tts.Communicate(text, v)
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        yield chunk["data"]
            except Exception as e:
                log.error(f"edge-tts stream error: {e}")
        else:
            # Non-streaming engines: synthesise then yield all at once
            result = await self.synthesise(text, voice)
            if result.get("success") and result.get("audio_b64"):
                yield base64.b64decode(result["audio_b64"])

    def _synthesise_sync(self, text: str, voice: str, speed: float) -> Dict:
        start = time.time()
        out_path = AUDIO_DIR / f"tts_{int(time.time())}.mp3"
        try:
            if self._tts_engine == "edge-tts":
                return self._edge_tts(text, voice or "en-US-AriaNeural",
                                      speed, out_path)
            elif self._tts_engine == "pyttsx3":
                return self._pyttsx3_tts(text, voice, speed, out_path)
            elif self._tts_engine == "espeak":
                return self._espeak_tts(text, out_path)
            else:
                return {"success": False, "error": "No TTS engine"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _edge_tts(self, text: str, voice: str, speed: float,
                  out_path: Path) -> Dict:
        import asyncio as _asyncio
        import edge_tts

        rate = f"+{int((speed-1)*100)}%" if speed >= 1 else f"{int((speed-1)*100)}%"

        async def _run():
            communicate = edge_tts.Communicate(text, voice, rate=rate)
            await communicate.save(str(out_path))

        loop = _asyncio.new_event_loop()
        loop.run_until_complete(_run())
        loop.close()

        audio_b64 = base64.b64encode(out_path.read_bytes()).decode()
        out_path.unlink(missing_ok=True)
        return {"success": True, "audio_b64": audio_b64,
                "format": "mp3", "engine": "edge-tts", "voice": voice}

    def _pyttsx3_tts(self, text: str, voice: str, speed: float,
                     out_path: Path) -> Dict:
        import pyttsx3
        engine = pyttsx3.init()
        if voice:
            engine.setProperty("voice", voice)
        engine.setProperty("rate", int(150 * speed))
        engine.save_to_file(text, str(out_path))
        engine.runAndWait()
        if out_path.exists():
            audio_b64 = base64.b64encode(out_path.read_bytes()).decode()
            out_path.unlink(missing_ok=True)
            return {"success": True, "audio_b64": audio_b64,
                    "format": "wav", "engine": "pyttsx3"}
        return {"success": False, "error": "pyttsx3 produced no output"}

    def _espeak_tts(self, text: str, out_path: Path) -> Dict:
        wav_path = out_path.with_suffix(".wav")
        r = subprocess.run(
            ["espeak", "-w", str(wav_path), text],
            capture_output=True, timeout=30
        )
        if r.returncode == 0 and wav_path.exists():
            audio_b64 = base64.b64encode(wav_path.read_bytes()).decode()
            wav_path.unlink(missing_ok=True)
            return {"success": True, "audio_b64": audio_b64,
                    "format": "wav", "engine": "espeak"}
        return {"success": False, "error": r.stderr.decode()}

    # ── Voices List ───────────────────────────────────────────────────────────
    async def list_voices(self) -> Dict:
        voices = []
        if self._tts_engine == "edge-tts":
            try:
                import edge_tts
                all_voices = await edge_tts.list_voices()
                voices = [
                    {"name": v["ShortName"], "lang": v["Locale"],
                     "gender": v["Gender"]}
                    for v in all_voices
                ]
            except Exception:
                voices = [
                    {"name": "en-US-AriaNeural",   "lang": "en-US", "gender": "Female"},
                    {"name": "en-US-GuyNeural",    "lang": "en-US", "gender": "Male"},
                    {"name": "en-GB-SoniaNeural",  "lang": "en-GB", "gender": "Female"},
                    {"name": "id-ID-GadisNeural",  "lang": "id-ID", "gender": "Female"},
                    {"name": "id-ID-ArdiNeural",   "lang": "id-ID", "gender": "Male"},
                ]
        elif self._tts_engine == "pyttsx3":
            voices = [{"name": v, "lang": "?", "gender": "?"} for v in self._tts_voices]
        return {"engine": self._tts_engine or "none", "voices": voices,
                "stt_available": self._stt_available,
                "tts_available": self._tts_available}

    # ── Status ────────────────────────────────────────────────────────────────
    def status(self) -> Dict:
        return {
            "stt_available": self._stt_available,
            "tts_available": self._tts_available,
            "tts_engine":    self._tts_engine,
            "default_voice": self._default_voice,
        }

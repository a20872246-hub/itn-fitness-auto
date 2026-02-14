import vlc
import os
import logging
import threading
import asyncio
import edge_tts

logger = logging.getLogger(__name__)

# 6 Korean announcer voice presets
# pitch/rate 미세 조정으로 톤 차이 구현
VOICE_PRESETS = {
    "sunhi_friendly": {
        "label": "여성 - 선희 (친근한)",
        "voice": "ko-KR-SunHiNeural",
        "pitch": "-2Hz",
        "rate": "+5%",
    },
    "sunhi_cheerful": {
        "label": "여성 - 선희 (밝은)",
        "voice": "ko-KR-SunHiNeural",
        "pitch": "+3Hz",
        "rate": "+8%",
    },
    "injoon_friendly": {
        "label": "남성 - 인준 (친근한)",
        "voice": "ko-KR-InJoonNeural",
        "pitch": "-2Hz",
        "rate": "+5%",
    },
    "injoon_cheerful": {
        "label": "남성 - 인준 (밝은)",
        "voice": "ko-KR-InJoonNeural",
        "pitch": "+3Hz",
        "rate": "+8%",
    },
    "hyunsu_friendly": {
        "label": "남성 - 현수 (친근한)",
        "voice": "ko-KR-HyunsuMultilingualNeural",
        "pitch": "-2Hz",
        "rate": "+5%",
    },
    "hyunsu_cheerful": {
        "label": "남성 - 현수 (밝은)",
        "voice": "ko-KR-HyunsuMultilingualNeural",
        "pitch": "+3Hz",
        "rate": "+8%",
    },
}

DEFAULT_VOICE = "sunhi_friendly"


class AnnouncementPlayer:
    """Plays announcement audio files or generates TTS via edge-tts."""

    def __init__(self, base_dir: str = "assets/announcements",
                 voice_id: str = DEFAULT_VOICE):
        self._instance = vlc.Instance("--no-video", "--quiet")
        self._player = self._instance.media_player_new()
        self._base_dir = base_dir
        self._voice_id = voice_id
        self._rate = None  # None = use preset default
        self._is_playing = False
        self._lock = threading.Lock()
        self._completion_callbacks: list = []
        self._tts_cache_dir = os.path.join(base_dir, ".tts_cache")

        em = self._player.event_manager()
        em.event_attach(vlc.EventType.MediaPlayerEndReached, self._on_finished)

    @property
    def voice_id(self) -> str:
        return self._voice_id

    @voice_id.setter
    def voice_id(self, value: str):
        if value in VOICE_PRESETS:
            self._voice_id = value

    @property
    def rate(self) -> str:
        """Current rate override, or None to use preset default."""
        return self._rate

    @rate.setter
    def rate(self, value: str):
        self._rate = value

    def play_file(self, file_path: str, on_complete=None) -> bool:
        """Play an MP3 file. Returns True if playback started."""
        abs_path = os.path.abspath(file_path)
        if not os.path.exists(abs_path):
            logger.error(f"File not found: {abs_path}")
            return False

        if on_complete:
            self._completion_callbacks.append(on_complete)

        with self._lock:
            media = self._instance.media_new(abs_path)
            self._player.set_media(media)
            self._player.play()
            import time
            time.sleep(0.1)
            self._player.audio_set_volume(100)
            self._is_playing = True
        return True

    def play_announcement(self, category: str, item_id: str,
                          text: str = None, on_complete=None) -> bool:
        """
        Play announcement by category/id.
        Looks for MP3 file first, falls back to TTS from text.
        """
        mp3_path = os.path.join(self._base_dir, category, f"{item_id}.mp3")
        if os.path.exists(mp3_path):
            return self.play_file(mp3_path, on_complete)

        if text:
            return self._play_tts(text, category, item_id, on_complete)

        logger.error(f"No audio file or text for {category}/{item_id}")
        if on_complete:
            on_complete()
        return False

    def _play_tts(self, text: str, category: str, item_id: str,
                  on_complete=None) -> bool:
        """Generate TTS audio via edge-tts and play it. Caches the result."""
        os.makedirs(self._tts_cache_dir, exist_ok=True)
        # Include voice_id and rate in cache filename
        rate_tag = self._rate.replace("+", "p").replace("-", "m").replace("%", "") if self._rate else "default"
        cache_path = os.path.join(
            self._tts_cache_dir, f"{category}_{item_id}_{self._voice_id}_{rate_tag}.mp3"
        )

        if not os.path.exists(cache_path):
            try:
                self._generate_tts_sync(text, cache_path, self._voice_id, self._rate)
                logger.info(f"TTS cached: {cache_path}")
            except Exception as e:
                logger.error(f"TTS generation failed: {e}")
                if on_complete:
                    on_complete()
                return False

        return self.play_file(cache_path, on_complete)

    @staticmethod
    def _generate_tts_sync(text: str, output_path: str, voice_id: str,
                           rate_override: str = None):
        """Generate TTS audio file synchronously using edge-tts."""
        preset = VOICE_PRESETS.get(voice_id, VOICE_PRESETS[DEFAULT_VOICE])
        rate = rate_override if rate_override else preset["rate"]

        async def _gen():
            comm = edge_tts.Communicate(
                text,
                preset["voice"],
                pitch=preset["pitch"],
                rate=rate,
            )
            await comm.save(output_path)

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(_gen())
        finally:
            loop.close()

    @staticmethod
    def generate_tts_file(text: str, output_path: str, voice_id: str,
                          rate_override: str = None):
        """Public API: Generate a TTS audio file with specified voice."""
        AnnouncementPlayer._generate_tts_sync(text, output_path, voice_id, rate_override)

    def stop(self):
        with self._lock:
            self._player.stop()
            self._is_playing = False

    @property
    def is_playing(self) -> bool:
        return self._is_playing

    def _on_finished(self, event):
        self._is_playing = False
        callbacks = self._completion_callbacks.copy()
        self._completion_callbacks.clear()
        for cb in callbacks:
            try:
                cb()
            except Exception as e:
                logger.error(f"Completion callback error: {e}")

    def invalidate_cache(self, category: str, item_id: str):
        """Delete all cached TTS files for this announcement (all voices)."""
        os.makedirs(self._tts_cache_dir, exist_ok=True)
        prefix = f"{category}_{item_id}_"
        for fname in os.listdir(self._tts_cache_dir):
            if fname.startswith(prefix):
                path = os.path.join(self._tts_cache_dir, fname)
                os.remove(path)
                logger.info(f"TTS cache invalidated: {path}")

    def cleanup(self):
        try:
            self._player.stop()
            self._player.release()
            self._instance.release()
        except Exception:
            pass

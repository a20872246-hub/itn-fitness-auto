import vlc
import yt_dlp
import threading
import time
import logging
from enum import Enum

logger = logging.getLogger(__name__)


class BGMState(Enum):
    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"
    LOADING = "loading"
    ERROR = "error"


class BGMPlayer:
    """YouTube audio streaming player with playlist support."""

    def __init__(self, volume: int = 70):
        # Windows audio output fix: explicitly set audio output module
        import platform
        if platform.system() == "Windows":
            logger.info("Initializing BGM player for Windows with DirectSound")
            self._instance = vlc.Instance(
                "--no-video",
                "--quiet",
                "--aout=directsound",  # Windows DirectSound audio output
                "--audio-resampler=samplerate",
                "--directx-audio-device=",  # Use default audio device
                "--mmdevice-audio-device=",  # Use default MMDevice
            )
        else:
            logger.info("Initializing BGM player for macOS/Linux")
            self._instance = vlc.Instance("--no-video", "--quiet")

        self._player = self._instance.media_player_new()
        self._volume = volume
        logger.info(f"BGM player initialized with volume: {volume}")
        self._state = BGMState.STOPPED
        self._current_url = ""
        self._current_title = ""
        self._lock = threading.Lock()
        self._state_callbacks: list = []

        # Playlist
        self._playlist: list[dict] = []  # [{"url": ..., "title": ...}, ...]
        self._playlist_index: int = -1
        self._playlist_callbacks: list = []  # called when track changes

        em = self._player.event_manager()
        em.event_attach(vlc.EventType.MediaPlayerEndReached, self._on_end_reached)
        em.event_attach(vlc.EventType.MediaPlayerEncounteredError, self._on_error)

    # --- Playlist Management ---

    def set_playlist(self, urls: list[str]):
        """Set playlist from a list of YouTube URLs. Titles resolved on play."""
        self._playlist = [{"url": u, "title": "", "duration": 0} for u in urls]
        self._playlist_index = -1

    def get_playlist(self) -> list[dict]:
        return list(self._playlist)

    @property
    def playlist_index(self) -> int:
        return self._playlist_index

    @property
    def playlist_count(self) -> int:
        return len(self._playlist)

    def add_to_playlist(self, url: str):
        """Append a URL to the playlist."""
        self._playlist.append({"url": url, "title": "", "duration": 0})

    def remove_from_playlist(self, index: int):
        """Remove a URL from the playlist by index."""
        if 0 <= index < len(self._playlist):
            self._playlist.pop(index)
            # Adjust current index
            if index < self._playlist_index:
                self._playlist_index -= 1
            elif index == self._playlist_index:
                self._playlist_index = min(self._playlist_index, len(self._playlist) - 1)

    def move_in_playlist(self, from_idx: int, to_idx: int):
        """Move a playlist item from one position to another."""
        if 0 <= from_idx < len(self._playlist) and 0 <= to_idx < len(self._playlist):
            item = self._playlist.pop(from_idx)
            self._playlist.insert(to_idx, item)
            # Update current index
            if self._playlist_index == from_idx:
                self._playlist_index = to_idx
            elif from_idx < self._playlist_index <= to_idx:
                self._playlist_index -= 1
            elif to_idx <= self._playlist_index < from_idx:
                self._playlist_index += 1

    def on_track_change(self, callback):
        """Register callback for when playlist track changes. callback(index, title)"""
        self._playlist_callbacks.append(callback)

    def _notify_track_change(self):
        idx = self._playlist_index
        title = self._current_title
        for cb in self._playlist_callbacks:
            try:
                cb(idx, title)
            except Exception:
                pass

    # --- Playback ---

    def play(self, youtube_url: str = None):
        """Play a specific URL or start playlist from current position."""
        if youtube_url:
            # Direct URL play (also check if it's in playlist)
            for i, item in enumerate(self._playlist):
                if item["url"] == youtube_url:
                    self._playlist_index = i
                    break
            self._set_state(BGMState.LOADING)
            thread = threading.Thread(
                target=self._load_and_play,
                args=(youtube_url,),
                daemon=True,
            )
            thread.start()
        elif self._playlist:
            # Start playlist
            if self._playlist_index < 0:
                self._playlist_index = 0
            self.play_index(self._playlist_index)

    def play_index(self, index: int):
        """Play a specific playlist index."""
        if 0 <= index < len(self._playlist):
            self._playlist_index = index
            url = self._playlist[index]["url"]
            self._set_state(BGMState.LOADING)
            thread = threading.Thread(
                target=self._load_and_play,
                args=(url,),
                daemon=True,
            )
            thread.start()

    def play_next(self):
        """Play next track in playlist."""
        if not self._playlist:
            return
        next_idx = self._playlist_index + 1
        if next_idx >= len(self._playlist):
            next_idx = 0  # Loop back to start
        self.play_index(next_idx)

    def play_prev(self):
        """Play previous track in playlist."""
        if not self._playlist:
            return
        prev_idx = self._playlist_index - 1
        if prev_idx < 0:
            prev_idx = len(self._playlist) - 1
        self.play_index(prev_idx)

    def _load_and_play(self, youtube_url: str):
        try:
            stream_url, title = self._extract_audio_url(youtube_url)
            with self._lock:
                self._current_url = youtube_url
                self._current_title = title
                # Update playlist info if matched
                if 0 <= self._playlist_index < len(self._playlist):
                    if self._playlist[self._playlist_index]["url"] == youtube_url:
                        self._playlist[self._playlist_index]["title"] = title
                        # duration already set in _extract_audio_url
                media = self._instance.media_new(stream_url)
                self._player.set_media(media)
                self._player.audio_set_volume(self._volume)  # Set volume BEFORE play
                self._player.play()
                time.sleep(0.5)  # Increased wait time for Windows
                self._player.audio_set_volume(self._volume)  # Set again after play
            self._set_state(BGMState.PLAYING)
            self._notify_track_change()
        except Exception as e:
            logger.error(f"BGM play failed: {e}")
            self._set_state(BGMState.ERROR)
            # Try next track on error if playlist has more items
            if len(self._playlist) > 1:
                time.sleep(2)
                self.play_next()

    def _extract_audio_url(self, youtube_url: str) -> tuple[str, str]:
        """Use yt-dlp to get direct audio stream URL and title."""
        ydl_opts = {
            "format": "bestaudio/best",
            "quiet": True,
            "no_warnings": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=False)
            title = info.get("title", "Unknown")
            duration = info.get("duration", 0) or 0
            # Store duration in playlist item
            if 0 <= self._playlist_index < len(self._playlist):
                if self._playlist[self._playlist_index]["url"] == youtube_url:
                    self._playlist[self._playlist_index]["duration"] = int(duration)
            return info["url"], title

    def fetch_info(self, index: int, callback=None):
        """Fetch title & duration for a playlist item in background. callback(index, title, duration)"""
        if not (0 <= index < len(self._playlist)):
            return
        url = self._playlist[index]["url"]

        def _fetch():
            try:
                ydl_opts = {"quiet": True, "no_warnings": True, "skip_download": True}
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    title = info.get("title", "Unknown")
                    duration = int(info.get("duration", 0) or 0)
                    if 0 <= index < len(self._playlist):
                        self._playlist[index]["title"] = title
                        self._playlist[index]["duration"] = duration
                    if callback:
                        callback(index, title, duration)
            except Exception as e:
                logger.error(f"fetch_info failed for {url}: {e}")

        threading.Thread(target=_fetch, daemon=True).start()

    @staticmethod
    def format_duration(seconds: int) -> str:
        """Format seconds to H:MM:SS or M:SS string."""
        if seconds <= 0:
            return ""
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"

    def stop(self):
        with self._lock:
            self._player.stop()
        self._set_state(BGMState.STOPPED)

    def pause(self):
        with self._lock:
            self._player.pause()
        state = BGMState.PAUSED if self._state == BGMState.PLAYING else BGMState.PLAYING
        self._set_state(state)

    def resume(self):
        with self._lock:
            self._player.audio_set_volume(self._volume)  # Set volume BEFORE resume
            self._player.play()
            time.sleep(0.2)  # Increased wait time
            self._player.audio_set_volume(self._volume)  # Set again after resume
        self._set_state(BGMState.PLAYING)

    @property
    def volume(self) -> int:
        return self._volume

    @volume.setter
    def volume(self, value: int):
        self._volume = max(0, min(100, value))
        try:
            self._player.audio_set_volume(self._volume)
        except Exception:
            pass

    @property
    def state(self) -> BGMState:
        return self._state

    @property
    def title(self) -> str:
        return self._current_title

    @property
    def player(self):
        """Expose underlying VLC player for volume controller."""
        return self._player

    def on_state_change(self, callback):
        self._state_callbacks.append(callback)

    def _set_state(self, new_state: BGMState):
        self._state = new_state
        for cb in self._state_callbacks:
            try:
                cb(new_state)
            except Exception:
                pass

    def _on_end_reached(self, event):
        """Auto-play next track in playlist, or restart if single."""
        logger.info("BGM stream ended")
        if len(self._playlist) > 1:
            # Play next track
            self.play_next()
        elif self._current_url:
            # Single track: restart
            self.play(self._current_url)

    def _on_error(self, event):
        logger.error("VLC playback error")
        self._set_state(BGMState.ERROR)

    def cleanup(self):
        try:
            self._player.stop()
            self._player.release()
            self._instance.release()
        except Exception:
            pass

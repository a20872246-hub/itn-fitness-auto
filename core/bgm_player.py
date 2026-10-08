import vlc
import yt_dlp
import os
import glob
import threading
import time
import logging
from enum import Enum

logger = logging.getLogger(__name__)

# YouTube rejects VLC's open-ended range requests (HTTP 403), so tracks are
# downloaded with yt-dlp (chunked) and played from this local cache.
CACHE_DIR = os.path.join("cache", "bgm")
CACHE_MAX_FILES = 20  # long mixes are ~100MB each


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

        # Incremented on every play/stop; stale downloads don't start playback
        self._load_seq = 0
        self._fail_count = 0  # consecutive failed tracks
        self._download_locks: dict[str, threading.Lock] = {}
        self._download_locks_guard = threading.Lock()

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

    @staticmethod
    def is_playlist_url(url: str) -> bool:
        return "list=" in url

    @staticmethod
    def expand_url(url: str) -> list[dict]:
        """
        Expand a YouTube playlist URL (list=...) into individual video items.
        Non-playlist URLs are returned as a single item.
        """
        if not BGMPlayer.is_playlist_url(url):
            return [{"url": url, "title": "", "duration": 0}]
        ydl_opts = {"quiet": True, "no_warnings": True,
                    "extract_flat": "in_playlist"}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        items = []
        for entry in info.get("entries") or []:
            if not entry or not entry.get("id"):
                continue
            items.append({
                "url": f"https://www.youtube.com/watch?v={entry['id']}",
                "title": entry.get("title") or "",
                "duration": int(entry.get("duration") or 0),
            })
        logger.info(f"Expanded playlist URL into {len(items)} tracks")
        return items or [{"url": url, "title": "", "duration": 0}]

    def add_url_expanded(self, url: str) -> int:
        """Add a URL, expanding playlist URLs into all their videos.
        Blocks on network for playlist URLs. Returns number of tracks added."""
        items = self.expand_url(url)
        self._playlist.extend(items)
        return len(items)

    def _expand_in_place(self, index: int):
        """Replace a playlist URL item at index with its individual videos."""
        url = self._playlist[index]["url"]
        if not self.is_playlist_url(url):
            return
        try:
            items = self.expand_url(url)
        except Exception as e:
            logger.error(f"Playlist expand failed for {url}: {e}")
            return
        if 0 <= index < len(self._playlist) and self._playlist[index]["url"] == url:
            self._playlist[index:index + 1] = items
            if self._playlist_index > index:
                self._playlist_index += len(items) - 1

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
            else:
                if self.is_playlist_url(youtube_url):
                    # Playlist URL: play all of its videos
                    self.set_playlist([youtube_url])
                    self.play_index(0)
                    return
            self._set_state(BGMState.LOADING)
            self._load_seq += 1
            thread = threading.Thread(
                target=self._load_and_play,
                args=(youtube_url, self._load_seq),
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
            self._set_state(BGMState.LOADING)
            self._load_seq += 1
            seq = self._load_seq

            def _run():
                # Saved playlist URLs are expanded into their videos first
                self._expand_in_place(index)
                if 0 <= index < len(self._playlist):
                    self._load_and_play(self._playlist[index]["url"], seq)

            threading.Thread(target=_run, daemon=True).start()

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

    def _load_and_play(self, youtube_url: str, seq: int):
        try:
            stream_url, title = self._extract_audio_url(youtube_url)
            if seq != self._load_seq:
                logger.info("BGM load cancelled (stopped or another track selected)")
                return
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
            self._fail_count = 0
            self._set_state(BGMState.PLAYING)
            self._notify_track_change()
            self._prefetch_next()
        except Exception as e:
            logger.error(f"BGM play failed: {e}")
            if seq != self._load_seq:
                return
            self._set_state(BGMState.ERROR)
            self._fail_count += 1
            if self._fail_count >= max(len(self._playlist), 1):
                logger.error("All BGM tracks failed, stopping playback")
                self._fail_count = 0
                return
            # Try next track on error if playlist has more items
            if len(self._playlist) > 1:
                time.sleep(2)
                self.play_next()

    def _extract_audio_url(self, youtube_url: str) -> tuple[str, str]:
        """Download audio with yt-dlp into the local cache.
        Returns (local file path, title)."""
        path, info = self._download_audio(youtube_url)
        title = info.get("title", "Unknown")
        duration = info.get("duration", 0) or 0
        # Store duration in playlist item
        if 0 <= self._playlist_index < len(self._playlist):
            if self._playlist[self._playlist_index]["url"] == youtube_url:
                self._playlist[self._playlist_index]["duration"] = int(duration)
        return path, title

    def _download_audio(self, youtube_url: str) -> tuple[str, dict]:
        os.makedirs(CACHE_DIR, exist_ok=True)
        ydl_opts = {
            "format": "bestaudio/best",
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,  # watch?v=...&list=... plays only that video
            "outtmpl": os.path.join(CACHE_DIR, "%(id)s.%(ext)s"),
            "http_chunk_size": 10 * 1024 * 1024,
            "noprogress": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=False)
            path = ydl.prepare_filename(info)
            with self._download_lock(path):
                if not os.path.exists(path):
                    logger.info(f"Downloading BGM: {info.get('title', '')}")
                    ydl.process_info(info)
        os.utime(path)  # mark as recently used
        self._cleanup_cache()
        return path, info

    def _download_lock(self, path: str) -> threading.Lock:
        with self._download_locks_guard:
            return self._download_locks.setdefault(path, threading.Lock())

    def _prefetch_next(self):
        """Download the next playlist track in background to avoid gaps."""
        if len(self._playlist) < 2:
            return
        next_idx = (self._playlist_index + 1) % len(self._playlist)
        url = self._playlist[next_idx]["url"]
        if self.is_playlist_url(url):
            return

        def _fetch():
            try:
                self._download_audio(url)
            except Exception as e:
                logger.warning(f"BGM prefetch failed for {url}: {e}")

        threading.Thread(target=_fetch, daemon=True).start()

    @staticmethod
    def _cleanup_cache():
        """Keep only the most recently used CACHE_MAX_FILES tracks."""
        files = [f for f in glob.glob(os.path.join(CACHE_DIR, "*"))
                 if not f.endswith(".part")]
        files.sort(key=os.path.getmtime, reverse=True)
        for f in files[CACHE_MAX_FILES:]:
            try:
                os.remove(f)
            except OSError:
                pass

    def fetch_info(self, index: int, callback=None):
        """Fetch title & duration for a playlist item in background. callback(index, title, duration)"""
        if not (0 <= index < len(self._playlist)):
            return
        url = self._playlist[index]["url"]

        def _fetch():
            try:
                ydl_opts = {"quiet": True, "no_warnings": True, "skip_download": True,
                            "noplaylist": True}
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
        self._load_seq += 1  # cancel any track still downloading
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

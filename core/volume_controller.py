import threading
import time


class VolumeController:
    """Thread-safe volume fading controller for VLC players."""

    def __init__(self, fade_duration: float = 1.5, steps: int = 30):
        self._fade_duration = fade_duration
        self._steps = steps
        self._fade_thread: threading.Thread | None = None
        self._cancel_event = threading.Event()

    def fade(self, player, from_vol: int, to_vol: int, callback=None):
        """Smoothly fade player volume. Cancels any in-progress fade first."""
        self.cancel()
        self._cancel_event.clear()
        self._fade_thread = threading.Thread(
            target=self._do_fade,
            args=(player, from_vol, to_vol, callback),
            daemon=True,
        )
        self._fade_thread.start()

    def _do_fade(self, player, from_vol: int, to_vol: int, callback):
        step_delay = self._fade_duration / self._steps
        vol_delta = (to_vol - from_vol) / self._steps
        current = float(from_vol)

        for _ in range(self._steps):
            if self._cancel_event.is_set():
                return
            current += vol_delta
            try:
                player.audio_set_volume(max(0, min(100, int(current))))
            except Exception:
                return
            time.sleep(step_delay)

        try:
            player.audio_set_volume(to_vol)
        except Exception:
            pass

        if callback:
            callback()

    def cancel(self):
        """Cancel any in-progress fade."""
        self._cancel_event.set()
        if self._fade_thread and self._fade_thread.is_alive():
            self._fade_thread.join(timeout=2.0)

    def duck(self, player, normal_vol: int, ducked_vol: int, on_ducked=None):
        """Fade down to ducked volume."""
        self.fade(player, normal_vol, ducked_vol, callback=on_ducked)

    def restore(self, player, ducked_vol: int, normal_vol: int, on_restored=None):
        """Fade back up to normal volume."""
        self.fade(player, ducked_vol, normal_vol, callback=on_restored)

import os
import yaml
import logging
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)


class AnnouncementManager:
    """
    Manages announcement catalog (CRUD) and orchestrates the full
    broadcast sequence: duck BGM -> play announcement -> restore BGM.
    """

    def __init__(self, config_path: str, bgm_player, announcement_player,
                 volume_controller, settings: dict):
        self._config_path = config_path
        self._bgm = bgm_player
        self._announcer = announcement_player
        self._volume_ctrl = volume_controller
        self._settings = settings
        self._catalog = self._load_catalog()
        self._broadcasting = False
        self._lock = threading.Lock()

    def _load_catalog(self) -> dict:
        with open(self._config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {"categories": {}}

    def _save_catalog(self):
        with open(self._config_path, "w", encoding="utf-8") as f:
            yaml.dump(self._catalog, f, allow_unicode=True, default_flow_style=False)

    def reload(self):
        self._catalog = self._load_catalog()

    @property
    def categories(self) -> dict:
        return self._catalog.get("categories", {})

    def get_items(self, category: str) -> list:
        cat = self._catalog.get("categories", {}).get(category, {})
        return cat.get("items", [])

    def get_item(self, category: str, item_id: str) -> Optional[dict]:
        for item in self.get_items(category):
            if item["id"] == item_id:
                return item
        return None

    def add_item(self, category: str, item_id: str, label: str,
                 text: str, file_path: Optional[str] = None):
        cats = self._catalog.setdefault("categories", {})
        cat = cats.setdefault(category, {"label": category, "items": []})
        items = cat.setdefault("items", [])
        items.append({
            "id": item_id,
            "label": label,
            "text": text,
            "file": file_path,
        })
        self._save_catalog()

    def remove_item(self, category: str, item_id: str):
        items = self.get_items(category)
        self._catalog["categories"][category]["items"] = [
            i for i in items if i["id"] != item_id
        ]
        self._save_catalog()

    def update_item(self, category: str, item_id: str, **kwargs):
        for item in self.get_items(category):
            if item["id"] == item_id:
                old_text = item.get("text")
                item.update(kwargs)
                if "text" in kwargs and kwargs["text"] != old_text:
                    self._announcer.invalidate_cache(category, item_id)
                break
        self._save_catalog()

    @property
    def is_broadcasting(self) -> bool:
        return self._broadcasting

    def broadcast(self, category: str, item_id: str) -> bool:
        """
        Execute full broadcast sequence:
        1. Duck BGM volume
        2. Play announcement
        3. On completion, restore BGM volume
        """
        with self._lock:
            if self._broadcasting:
                logger.warning("Broadcast already in progress")
                return False
            self._broadcasting = True

        text = None
        for item in self.get_items(category):
            if item["id"] == item_id:
                text = item.get("text")
                break

        bgm_settings = self._settings.get("bgm", {})
        normal_vol = bgm_settings.get("volume", 70)
        ducked_vol = bgm_settings.get("ducked_volume", 15)

        from core.bgm_player import BGMState
        if self._bgm.state != BGMState.PLAYING:
            # No BGM playing, just play announcement directly
            self._announcer.play_announcement(
                category, item_id, text=text,
                on_complete=self._on_announcement_complete_no_bgm,
            )
            return True

        def on_ducked():
            self._announcer.play_announcement(
                category, item_id, text=text,
                on_complete=self._on_announcement_complete,
            )

        self._volume_ctrl.duck(
            self._bgm.player, normal_vol, ducked_vol,
            on_ducked=on_ducked,
        )
        return True

    def _on_announcement_complete(self):
        """Called when announcement finishes playing (BGM was ducked)."""
        bgm_settings = self._settings.get("bgm", {})
        normal_vol = bgm_settings.get("volume", 70)
        ducked_vol = bgm_settings.get("ducked_volume", 15)
        post_delay = self._settings.get("announcements", {}).get("post_delay", 1.0)

        time.sleep(post_delay)

        def on_restored():
            with self._lock:
                self._broadcasting = False

        self._volume_ctrl.restore(
            self._bgm.player, ducked_vol, normal_vol,
            on_restored=on_restored,
        )

    def _on_announcement_complete_no_bgm(self):
        """Called when announcement finishes with no BGM playing."""
        with self._lock:
            self._broadcasting = False

    def broadcast_emergency(self, item_id: str):
        """Emergency broadcast: immediate full mute, max volume, no fade."""
        from core.bgm_player import BGMState

        was_playing = self._bgm.state == BGMState.PLAYING
        if was_playing:
            self._bgm.player.audio_set_volume(0)

        text = None
        for item in self.get_items("emergency"):
            if item["id"] == item_id:
                text = item.get("text")
                break

        def on_complete():
            if was_playing:
                normal_vol = self._settings.get("bgm", {}).get("volume", 70)
                self._bgm.player.audio_set_volume(normal_vol)
            with self._lock:
                self._broadcasting = False

        with self._lock:
            self._broadcasting = True

        self._announcer.play_announcement(
            "emergency", item_id, text=text,
            on_complete=on_complete,
        )

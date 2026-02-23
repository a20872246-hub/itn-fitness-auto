import schedule
import yaml
import threading
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

DAY_NAMES = ["monday", "tuesday", "wednesday", "thursday",
             "friday", "saturday", "sunday"]


class ScheduleManager:
    """
    Loads broadcast schedules from YAML and
    triggers announcements and BGM playlist changes at configured times.
    Each entry has its own list of days it applies to.
    """

    def __init__(self, config_path: str, announcement_manager, bgm_player=None):
        self._config_path = config_path
        self._ann_manager = announcement_manager
        self._bgm_player = bgm_player
        self._config = self._load_config()
        self._running = False
        self._thread: threading.Thread | None = None
        self._scheduled_items: list[dict] = []
        self._bgm_scheduled_items: list[dict] = []

    def _load_config(self) -> dict:
        with open(self._config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def reload(self):
        """Reload config and reschedule all jobs."""
        self._config = self._load_config()
        self._setup_schedules()

    def save_config(self):
        """Persist current config to YAML."""
        with open(self._config_path, "w", encoding="utf-8") as f:
            yaml.dump(self._config, f, allow_unicode=True, default_flow_style=False)

    @property
    def config(self) -> dict:
        return self._config

    def _setup_schedules(self):
        """Register all schedule jobs. Each entry specifies its own days."""
        schedule.clear()
        self._scheduled_items.clear()

        entries = self._config.get("schedules", [])
        if not isinstance(entries, list):
            entries = []

        job_count = 0
        for entry in entries:
            time_str = entry["time"]
            announcement = entry["announcement"]
            label = entry.get("label", announcement)
            days = entry.get("days", [])

            parts = announcement.split("/")
            if len(parts) != 2:
                logger.error(f"Bad announcement path: {announcement}")
                continue
            category, item_id = parts

            bgm_action = entry.get("bgm_action")  # "play", "stop", or None

            # Register a job for each day this entry applies to
            for day_name in days:
                if day_name not in DAY_NAMES:
                    continue
                day_scheduler = getattr(schedule.every(), day_name)
                day_scheduler.at(time_str).do(
                    self._trigger,
                    category=category,
                    item_id=item_id,
                    label=label,
                    bgm_action=bgm_action,
                )
                job_count += 1

            self._scheduled_items.append({
                "time": time_str,
                "category": category,
                "item_id": item_id,
                "label": label,
                "announcement": announcement,
                "days": list(days),
                "bgm_action": bgm_action,
            })

        logger.info(f"Scheduled {len(self._scheduled_items)} entries ({job_count} jobs)")

        self._setup_bgm_schedules()

    def _trigger(self, category: str, item_id: str, label: str,
                 bgm_action: str = None):
        logger.info(f"Triggering scheduled announcement: {label}")

        on_complete = None
        if bgm_action == "play" and self._bgm_player:
            def on_complete():
                if self._bgm_player.playlist_count > 0:
                    logger.info("BGM auto-play after announcement")
                    idx = self._bgm_player.playlist_index
                    self._bgm_player.play_index(idx if idx >= 0 else 0)
                else:
                    logger.warning("BGM play requested but playlist is empty")
        elif bgm_action == "stop" and self._bgm_player:
            def on_complete():
                logger.info("BGM auto-stop after announcement")
                self._bgm_player.stop()

        self._ann_manager.broadcast(category, item_id,
                                     on_broadcast_complete=on_complete)

    def start(self):
        """Start the scheduler loop in a background thread."""
        self._setup_schedules()
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("Scheduler started")

    def _run_loop(self):
        import time as _time
        while self._running:
            schedule.run_pending()
            _time.sleep(1)

    def stop(self):
        self._running = False
        schedule.clear()

    @property
    def scheduled_items(self) -> list[dict]:
        """Return list of scheduled items for UI."""
        return list(self._scheduled_items)

    def get_today_schedule(self) -> list[dict]:
        """Get today's scheduled items sorted by time."""
        today = DAY_NAMES[datetime.now().weekday()]
        items = [
            item for item in self._scheduled_items
            if today in item.get("days", [])
        ]
        items.sort(key=lambda x: x["time"])
        return items

    def get_next_announcement(self) -> dict | None:
        """Get the next upcoming announcement for display."""
        now = datetime.now()
        today_name = DAY_NAMES[now.weekday()]
        now_time = now.strftime("%H:%M")

        upcoming = []
        for item in self._scheduled_items:
            if today_name in item.get("days", []) and item["time"] > now_time:
                upcoming.append(item)

        if upcoming:
            upcoming.sort(key=lambda x: x["time"])
            return upcoming[0]
        return None

    def add_schedule_entry(self, time_str: str, announcement: str,
                           label: str, days: list[str],
                           bgm_action: str = None):
        """Add a new schedule entry with specified days."""
        entries = self._config.setdefault("schedules", [])
        if not isinstance(entries, list):
            entries = []
            self._config["schedules"] = entries

        entry = {
            "time": time_str,
            "announcement": announcement,
            "label": label,
            "days": days,
        }
        if bgm_action:
            entry["bgm_action"] = bgm_action
        entries.append(entry)
        entries.sort(key=lambda x: x["time"])
        self.save_config()
        self.reload()

    def remove_schedule_entry(self, time_str: str, announcement: str):
        """Remove a schedule entry by time and announcement."""
        entries = self._config.get("schedules", [])
        self._config["schedules"] = [
            e for e in entries
            if not (e["time"] == time_str and e["announcement"] == announcement)
        ]
        self.save_config()
        self.reload()

    def update_schedule_entry(self, time_str: str, announcement: str,
                              label: str = None, days: list[str] = None,
                              bgm_action: str = None):
        """Update an existing schedule entry's label, days, or bgm_action."""
        entries = self._config.get("schedules", [])
        for entry in entries:
            if entry["time"] == time_str and entry["announcement"] == announcement:
                if label is not None:
                    entry["label"] = label
                if days is not None:
                    entry["days"] = days
                if bgm_action is not None:
                    if bgm_action:
                        entry["bgm_action"] = bgm_action
                    else:
                        entry.pop("bgm_action", None)
                break
        self.save_config()
        self.reload()

    # --- BGM Schedule ---

    def _setup_bgm_schedules(self):
        """Register BGM playlist change jobs. Each entry has its own days."""
        self._bgm_scheduled_items.clear()

        if not self._bgm_player:
            return

        bgm_entries = self._config.get("bgm_schedules", [])
        if not isinstance(bgm_entries, list):
            bgm_entries = []

        job_count = 0
        for entry in bgm_entries:
            time_str = entry["time"]
            playlist = entry.get("playlist", [])
            label = entry.get("label", f"BGM {time_str}")
            days = entry.get("days", [])

            if not playlist:
                continue

            for day_name in days:
                if day_name not in DAY_NAMES:
                    continue
                day_scheduler = getattr(schedule.every(), day_name)
                day_scheduler.at(time_str).do(
                    self._trigger_bgm,
                    playlist=playlist,
                    label=label,
                )
                job_count += 1

            self._bgm_scheduled_items.append({
                "time": time_str,
                "label": label,
                "playlist": playlist,
                "days": list(days),
            })

        logger.info(f"Scheduled {len(self._bgm_scheduled_items)} BGM entries ({job_count} jobs)")

    def _trigger_bgm(self, playlist: list[str], label: str):
        """Called by schedule library to swap the BGM playlist."""
        logger.info(f"Triggering BGM change: {label} ({len(playlist)} tracks)")
        self._bgm_player.set_playlist(playlist)
        if not self._ann_manager.is_broadcasting:
            self._bgm_player.play()
        else:
            logger.info("Announcement in progress, BGM playback deferred")

    def apply_current_bgm(self):
        """Apply the BGM playlist that should be active now based on day/time."""
        if not self._bgm_player:
            return

        now = datetime.now()
        today = DAY_NAMES[now.weekday()]
        now_time = now.strftime("%H:%M")

        bgm_entries = self._config.get("bgm_schedules", [])
        if not isinstance(bgm_entries, list):
            return

        # Filter entries active today, sorted by time
        today_entries = [
            e for e in bgm_entries
            if today in e.get("days", [])
        ]
        today_entries.sort(key=lambda x: x["time"])

        active_entry = None
        for entry in today_entries:
            if entry["time"] <= now_time:
                active_entry = entry

        if active_entry:
            playlist = active_entry.get("playlist", [])
            if playlist:
                logger.info(f"Applying current BGM: {active_entry.get('label', '')} "
                            f"({len(playlist)} tracks)")
                self._bgm_player.set_playlist(playlist)

    @property
    def bgm_scheduled_items(self) -> list[dict]:
        """Return BGM schedule items for UI."""
        return list(self._bgm_scheduled_items)

    def get_bgm_schedule_for_day(self, day: str) -> list[dict]:
        """Get BGM schedule entries that include a specific day."""
        bgm_entries = self._config.get("bgm_schedules", [])
        if not isinstance(bgm_entries, list):
            return []
        entries = [
            e for e in bgm_entries
            if day in e.get("days", [])
        ]
        return sorted(entries, key=lambda x: x["time"])

    def add_bgm_schedule_entry(self, time_str: str, label: str,
                                playlist: list[str], days: list[str]):
        """Add a BGM schedule entry."""
        bgm_entries = self._config.setdefault("bgm_schedules", [])
        if not isinstance(bgm_entries, list):
            bgm_entries = []
            self._config["bgm_schedules"] = bgm_entries

        # Remove existing entry at same time (replace)
        bgm_entries[:] = [e for e in bgm_entries if e["time"] != time_str]
        bgm_entries.append({
            "time": time_str,
            "label": label,
            "playlist": playlist,
            "days": days,
        })
        bgm_entries.sort(key=lambda x: x["time"])
        self.save_config()
        self.reload()

    def remove_bgm_schedule_entry(self, time_str: str):
        """Remove a BGM schedule entry by time."""
        bgm_entries = self._config.get("bgm_schedules", [])
        if isinstance(bgm_entries, list):
            self._config["bgm_schedules"] = [
                e for e in bgm_entries if e["time"] != time_str
            ]
        self.save_config()
        self.reload()

    def update_bgm_schedule_entry(self, time_str: str,
                                   label: str = None, playlist: list[str] = None,
                                   days: list[str] = None):
        """Update an existing BGM schedule entry."""
        bgm_entries = self._config.get("bgm_schedules", [])
        if not isinstance(bgm_entries, list):
            return
        for entry in bgm_entries:
            if entry["time"] == time_str:
                if label is not None:
                    entry["label"] = label
                if playlist is not None:
                    entry["playlist"] = playlist
                if days is not None:
                    entry["days"] = days
                break
        self.save_config()
        self.reload()

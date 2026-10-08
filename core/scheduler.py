import schedule
import yaml
import threading
import logging
from datetime import datetime, timedelta

try:
    import holidays
except ImportError:  # holidays package missing: only Saturday rule applies
    holidays = None

logger = logging.getLogger(__name__)

DAY_NAMES = ["monday", "tuesday", "wednesday", "thursday",
             "friday", "saturday", "sunday"]


class ScheduleManager:
    """
    Loads broadcast schedules from YAML and
    triggers announcements and BGM playlist changes at configured times.
    Each entry has its own list of days it applies to.
    """

    def __init__(self, config_path: str, announcement_manager, bgm_player=None,
                 settings: dict = None):
        self._config_path = config_path
        self._settings = settings or {}
        self._kr_holidays = holidays.country_holidays("KR") if holidays else None
        if holidays is None:
            logger.warning("holidays package not installed; "
                           "public holiday auto-stop disabled")
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

            # One daily job; _trigger checks the day (public holidays
            # follow the Saturday schedule)
            valid_days = [d for d in days if d in DAY_NAMES]
            if valid_days:
                schedule.every().day.at(time_str).do(
                    self._trigger,
                    category=category,
                    item_id=item_id,
                    label=label,
                    bgm_action=bgm_action,
                    days=valid_days,
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
        self._setup_auto_stop()

    def _trigger(self, category: str, item_id: str, label: str,
                 bgm_action: str = None, days: list[str] = None):
        today = datetime.now().date()
        if self.is_closed_day(today):
            logger.info(f"Closed day, skipping scheduled announcement: {label}")
            return
        if days is not None and self.effective_day_name(today) not in days:
            return
        logger.info(f"Triggering scheduled announcement: {label}")

        on_complete = None
        if bgm_action == "play" and self._bgm_player:
            def on_complete():
                if self.is_closed():
                    logger.info("Closed, skipping BGM auto-play")
                elif self._bgm_player.playlist_count > 0:
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
        today = self.effective_day_name(datetime.now().date())
        items = [
            item for item in self._scheduled_items
            if today in item.get("days", [])
        ]
        items.sort(key=lambda x: x["time"])
        return items

    def get_next_announcement(self) -> dict | None:
        """Get the next upcoming announcement for display."""
        now = datetime.now()
        today_name = self.effective_day_name(now.date())
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
        if self.is_closed():
            logger.info(f"Closed, skipping BGM change: {label}")
            return
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

    # --- Operating hours (BGM auto start/stop) ---

    def _hours_config(self) -> dict:
        cfg = self._settings.get("bgm", {}).get("auto_stop", {})
        return {
            "enabled": cfg.get("enabled", True),
            "weekday_open_time": cfg.get("weekday_open_time", "06:00"),
            "weekday_time": cfg.get("weekday_time", "01:00"),
            "weekend_open_time": cfg.get("weekend_open_time", "09:00"),
            "weekend_time": cfg.get("weekend_time", "19:00"),
            "closed_days": cfg.get("closed_days", ["sunday"]),
        }

    def _setup_auto_stop(self):
        """
        Operating hours:
        weekdays (Mon-Fri) weekday_open_time ~ weekday_time next morning
        (default 06:00 ~ 01:00), Saturdays and public holidays
        weekend_open_time ~ weekend_time (default 09:00 ~ 19:00),
        closed_days (default Sunday) closed.
        BGM starts automatically at opening and is checked every 30 seconds
        and stopped outside operating hours. This also covers app restarts,
        PC sleep and tracks that finish loading after a stop.
        Manual playback on closed days is allowed.
        """
        if not self._bgm_player:
            return

        cfg = self._hours_config()
        if not cfg["enabled"]:
            logger.info("BGM auto start/stop disabled")
            return

        self._pending_open_play = False
        schedule.every().day.at(cfg["weekday_open_time"]).do(
            self._auto_open, weekend=False)
        schedule.every().day.at(cfg["weekend_open_time"]).do(
            self._auto_open, weekend=True)
        schedule.every(30).seconds.do(self._enforce_operating_hours)
        logger.info(f"BGM operating hours: weekdays {cfg['weekday_open_time']}"
                    f"~{cfg['weekday_time']}, Saturdays/holidays "
                    f"{cfg['weekend_open_time']}~{cfg['weekend_time']}, "
                    f"closed {cfg['closed_days']}")

    def is_holiday(self, date) -> bool:
        """True if date is a Korean public holiday (incl. substitute holidays)."""
        return bool(self._kr_holidays is not None and date in self._kr_holidays)

    def is_closed_day(self, date) -> bool:
        """True if the gym is closed all day (e.g. Sunday)."""
        cfg = self._hours_config()
        return cfg["enabled"] and DAY_NAMES[date.weekday()] in cfg["closed_days"]

    def _is_weekday_hours(self, date) -> bool:
        """True if date runs on weekday hours (Mon-Fri, not a holiday/closed day)."""
        return (date.weekday() < 5 and not self.is_holiday(date)
                and not self.is_closed_day(date))

    def effective_day_name(self, date) -> str:
        """Day name whose schedule applies: public holidays follow Saturday."""
        if self.is_holiday(date) and not self.is_closed_day(date):
            return "saturday"
        return DAY_NAMES[date.weekday()]

    def is_closed(self, now: datetime = None) -> bool:
        """True if the gym is outside operating hours at the given time."""
        cfg = self._hours_config()
        if not cfg["enabled"]:
            return False
        now = now or datetime.now()
        now_time = now.strftime("%H:%M")
        today = now.date()

        # After midnight: weekday hours run until weekday_time
        yesterday = today - timedelta(days=1)
        if now_time < cfg["weekday_time"] and self._is_weekday_hours(yesterday):
            return False

        if self.is_closed_day(today):
            return True
        if self._is_weekday_hours(today):
            return now_time < cfg["weekday_open_time"]
        return not (cfg["weekend_open_time"] <= now_time < cfg["weekend_time"])

    def _auto_open(self, weekend: bool):
        """Start BGM at opening time (weekday or Saturday/holiday)."""
        today = datetime.now().date()
        if self.is_closed_day(today) or self._is_weekday_hours(today) == weekend:
            return
        if self._ann_manager.is_broadcasting:
            # Opening announcement in progress: start after it ends
            self._pending_open_play = True
        else:
            self._start_bgm()

    def _start_bgm(self):
        from core.bgm_player import BGMState
        if self._bgm_player.state in (BGMState.PLAYING, BGMState.LOADING):
            return
        if self._bgm_player.playlist_count > 0:
            logger.info("BGM auto-start: opening")
            idx = self._bgm_player.playlist_index
            self._bgm_player.play_index(idx if idx >= 0 else 0)
            return
        default_url = self._settings.get("bgm", {}).get("default_url", "")
        if default_url:
            logger.info("BGM auto-start: opening (default URL)")
            self._bgm_player.play(default_url)
        else:
            logger.warning("BGM auto-start skipped: playlist is empty")

    def _enforce_operating_hours(self):
        from core.bgm_player import BGMState
        if self._pending_open_play and not self._ann_manager.is_broadcasting:
            self._pending_open_play = False
            if not self.is_closed():
                self._start_bgm()

        if self._bgm_player.state in (BGMState.STOPPED, BGMState.ERROR):
            return
        if self.is_closed_day(datetime.now().date()):
            return  # manual playback allowed on closed days
        if self.is_closed():
            logger.info("BGM auto-stop: outside operating hours")
            self._bgm_player.stop()

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

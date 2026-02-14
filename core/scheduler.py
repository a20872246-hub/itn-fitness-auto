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
    Loads day-of-week broadcast schedules from YAML and
    triggers announcements at configured times.
    """

    def __init__(self, config_path: str, announcement_manager):
        self._config_path = config_path
        self._ann_manager = announcement_manager
        self._config = self._load_config()
        self._running = False
        self._thread: threading.Thread | None = None
        self._scheduled_items: list[dict] = []

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
        """Register all schedule jobs based on day_mapping."""
        schedule.clear()
        self._scheduled_items.clear()

        day_mapping = self._config.get("day_mapping", {})
        schedules = self._config.get("schedules", {})

        for day_name in DAY_NAMES:
            template = day_mapping.get(day_name)
            if not template or template not in schedules:
                continue

            entries = schedules[template]
            day_scheduler = getattr(schedule.every(), day_name)

            for entry in entries:
                time_str = entry["time"]
                announcement = entry["announcement"]
                label = entry.get("label", announcement)

                parts = announcement.split("/")
                if len(parts) != 2:
                    logger.error(f"Bad announcement path: {announcement}")
                    continue
                category, item_id = parts

                job = day_scheduler.at(time_str).do(
                    self._trigger,
                    category=category,
                    item_id=item_id,
                    label=label,
                )

                self._scheduled_items.append({
                    "day": day_name,
                    "time": time_str,
                    "category": category,
                    "item_id": item_id,
                    "label": label,
                    "announcement": announcement,
                    "job": job,
                })

        logger.info(f"Scheduled {len(self._scheduled_items)} announcements")

    def _trigger(self, category: str, item_id: str, label: str):
        logger.info(f"Triggering scheduled announcement: {label}")
        self._ann_manager.broadcast(category, item_id)

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
        """Return list of scheduled items (without job objects) for UI."""
        return [
            {k: v for k, v in item.items() if k != "job"}
            for item in self._scheduled_items
        ]

    def get_today_schedule(self) -> list[dict]:
        """Get today's scheduled items sorted by time."""
        today = DAY_NAMES[datetime.now().weekday()]
        items = [
            item for item in self.scheduled_items
            if item["day"] == today
        ]
        items.sort(key=lambda x: x["time"])
        return items

    def get_next_announcement(self) -> dict | None:
        """Get the next upcoming announcement for display."""
        now = datetime.now()
        today_name = DAY_NAMES[now.weekday()]
        now_time = now.strftime("%H:%M")

        upcoming = []
        for item in self.scheduled_items:
            if item["day"] == today_name and item["time"] > now_time:
                upcoming.append(item)

        if upcoming:
            upcoming.sort(key=lambda x: x["time"])
            return upcoming[0]
        return None

    def add_schedule_entry(self, day: str, time_str: str,
                           announcement: str, label: str):
        """Add a new schedule entry for a specific day."""
        day_mapping = self._config.get("day_mapping", {})
        template = day_mapping.get(day)
        if not template:
            return

        schedules = self._config.setdefault("schedules", {})
        entries = schedules.setdefault(template, [])
        entries.append({
            "time": time_str,
            "announcement": announcement,
            "label": label,
        })
        entries.sort(key=lambda x: x["time"])
        self.save_config()
        self.reload()

    def remove_schedule_entry(self, day: str, time_str: str, announcement: str):
        """Remove a schedule entry."""
        day_mapping = self._config.get("day_mapping", {})
        template = day_mapping.get(day)
        if not template:
            return

        schedules = self._config.get("schedules", {})
        entries = schedules.get(template, [])
        schedules[template] = [
            e for e in entries
            if not (e["time"] == time_str and e["announcement"] == announcement)
        ]
        self.save_config()
        self.reload()

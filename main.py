#!/usr/bin/env python3
"""
ITN Fitness Gym Broadcast System
Main entry point - initializes all components and starts the GUI.
"""

import os
import sys
import tkinter as tk
import yaml
import logging
from logging.handlers import RotatingFileHandler

# Ensure working directory is the script's directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))


def setup_logging(settings: dict):
    log_cfg = settings.get("logging", {})
    os.makedirs("logs", exist_ok=True)

    handler = RotatingFileHandler(
        log_cfg.get("file", "logs/broadcast.log"),
        maxBytes=log_cfg.get("max_bytes", 5242880),
        backupCount=log_cfg.get("backup_count", 3),
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    ))

    root_logger = logging.getLogger()
    root_logger.setLevel(log_cfg.get("level", "INFO"))
    root_logger.addHandler(handler)
    root_logger.addHandler(logging.StreamHandler())


def load_settings() -> dict:
    with open("config/settings.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save_settings(settings: dict):
    with open("config/settings.yaml", "w", encoding="utf-8") as f:
        yaml.dump(settings, f, allow_unicode=True, default_flow_style=False)


class ConfigManager:
    """Simple config persistence helper passed to GUI."""

    def __init__(self):
        self.settings = load_settings()

    def save(self):
        save_settings(self.settings)

    def reload(self):
        self.settings = load_settings()


def get_local_ip() -> str:
    """Get the local network IP address."""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "localhost"


def main():
    config_mgr = ConfigManager()
    settings = config_mgr.settings
    setup_logging(settings)

    logger = logging.getLogger(__name__)
    logger.info("ITN Fitness Broadcast System starting...")

    # Create required directories
    os.makedirs("assets/announcements/general", exist_ok=True)
    os.makedirs("assets/announcements/safety", exist_ok=True)
    os.makedirs("assets/announcements/class", exist_ok=True)
    os.makedirs("assets/announcements/event", exist_ok=True)
    os.makedirs("assets/announcements/emergency", exist_ok=True)
    os.makedirs("logs", exist_ok=True)

    # Initialize core components
    from core.volume_controller import VolumeController
    from core.bgm_player import BGMPlayer
    from core.announcement import AnnouncementPlayer
    from core.announcement_manager import AnnouncementManager
    from core.scheduler import ScheduleManager

    volume_ctrl = VolumeController(
        fade_duration=settings.get("bgm", {}).get("fade_duration", 1.5),
    )

    bgm_player = BGMPlayer(
        volume=settings.get("bgm", {}).get("volume", 70),
    )

    ann_player = AnnouncementPlayer(
        base_dir=settings.get("announcements", {}).get("base_dir", "assets/announcements"),
        voice_id=settings.get("announcements", {}).get("voice", "sunhi_friendly"),
        chime_enabled=settings.get("announcements", {}).get("chime_enabled", True),
        chime_type=settings.get("announcements", {}).get("chime_type", "school_bell"),
    )

    ann_manager = AnnouncementManager(
        config_path="config/announcements.yaml",
        bgm_player=bgm_player,
        announcement_player=ann_player,
        volume_controller=volume_ctrl,
        settings=settings,
    )

    sched_manager = ScheduleManager(
        config_path="config/schedules.yaml",
        announcement_manager=ann_manager,
        bgm_player=bgm_player,
    )

    # Start scheduler
    sched_manager.start()

    # Apply BGM playlist for current day/time
    sched_manager.apply_current_bgm()

    # Start remote server (if enabled)
    remote_server = None
    if settings.get("remote", {}).get("enabled", False):
        try:
            from remote.auth import AuthManager
            from remote.server import RemoteServer

            auth_mgr = AuthManager(
                settings.get("remote", {}).get("password_hash", ""),
            )
            remote_server = RemoteServer(
                bgm_player=bgm_player,
                announcement_manager=ann_manager,
                schedule_manager=sched_manager,
                auth_manager=auth_mgr,
                settings=settings,
                save_settings_fn=config_mgr.save,
            )
            remote_server.start()

            port = settings.get("remote", {}).get("port", 8585)
            local_ip = get_local_ip()
            logger.info(f"Remote control: http://{local_ip}:{port}")
            print(f"\n  Remote control: http://{local_ip}:{port}\n")
        except Exception as e:
            logger.error(f"Failed to start remote server: {e}")

    # Auto-play BGM if configured
    if settings.get("bgm", {}).get("auto_play", False):
        default_url = settings.get("bgm", {}).get("default_url", "")
        if default_url:
            bgm_player.play(default_url)

    # Start GUI
    from gui.main_window import MainWindow

    root = tk.Tk()
    app = MainWindow(
        root=root,
        bgm_player=bgm_player,
        announcement_manager=ann_manager,
        schedule_manager=sched_manager,
        volume_controller=volume_ctrl,
        settings=settings,
        config_manager=config_mgr,
    )

    def on_close():
        logger.info("Shutting down...")
        sched_manager.stop()
        bgm_player.cleanup()
        ann_player.cleanup()
        if remote_server:
            remote_server.stop()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)

    logger.info("System ready. GUI starting.")
    root.mainloop()


if __name__ == "__main__":
    main()

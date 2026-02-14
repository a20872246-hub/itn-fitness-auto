import tkinter as tk
from tkinter import ttk
import logging

logger = logging.getLogger(__name__)


class MainWindow:
    """Main application window with tabbed notebook interface."""

    def __init__(self, root: tk.Tk, bgm_player, announcement_manager,
                 schedule_manager, volume_controller, settings: dict,
                 config_manager):
        self._root = root
        self._bgm = bgm_player
        self._ann_manager = announcement_manager
        self._sched_manager = schedule_manager
        self._vol_ctrl = volume_controller
        self._settings = settings
        self._config_mgr = config_manager

        self._setup_window()
        self._create_tabs()
        self._create_status_bar()
        self._start_status_updates()

    def _setup_window(self):
        self._root.title("ITN Fitness 방송 시스템")
        self._root.geometry("950x680")
        self._root.minsize(750, 550)

        style = ttk.Style()
        available = style.theme_names()
        if "aqua" in available:
            style.theme_use("aqua")
        elif "clam" in available:
            style.theme_use("clam")

    def _create_tabs(self):
        self._notebook = ttk.Notebook(self._root)
        self._notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        from gui.bgm_tab import BGMTab
        from gui.schedule_editor import ScheduleEditor
        from gui.announcement_editor import AnnouncementEditor
        from gui.settings_dialog import SettingsTab

        # BGM Tab
        bgm_frame = ttk.Frame(self._notebook)
        self._bgm_tab = BGMTab(bgm_frame, self._bgm, self._settings, self._config_mgr)
        self._notebook.add(bgm_frame, text="  BGM  ")

        # Schedule Tab
        sched_frame = ttk.Frame(self._notebook)
        self._sched_tab = ScheduleEditor(
            sched_frame, self._sched_manager, self._ann_manager,
        )
        self._notebook.add(sched_frame, text="  스케줄  ")

        # Announcements Tab
        ann_frame = ttk.Frame(self._notebook)
        self._ann_tab = AnnouncementEditor(ann_frame, self._ann_manager)
        self._notebook.add(ann_frame, text="  안내방송  ")

        # Settings Tab
        settings_frame = ttk.Frame(self._notebook)
        self._settings_tab = SettingsTab(
            settings_frame, self._settings, self._config_mgr,
        )
        self._notebook.add(settings_frame, text="  설정  ")

    def _create_status_bar(self):
        self._status_frame = ttk.Frame(self._root)
        self._status_frame.pack(fill=tk.X, padx=5, pady=(0, 3))

        sep = ttk.Separator(self._status_frame, orient=tk.HORIZONTAL)
        sep.pack(fill=tk.X, pady=(0, 3))

        bar = ttk.Frame(self._status_frame)
        bar.pack(fill=tk.X)

        self._status_label = ttk.Label(bar, text="BGM: 정지 | 볼륨: 70%")
        self._status_label.pack(side=tk.LEFT)

        self._next_label = ttk.Label(bar, text="", foreground="blue")
        self._next_label.pack(side=tk.RIGHT)

    def _start_status_updates(self):
        def update():
            state_kr = {
                "stopped": "정지",
                "playing": "재생 중",
                "paused": "일시정지",
                "loading": "로딩 중",
                "error": "오류",
            }
            state_text = state_kr.get(self._bgm.state.value, "알 수 없음")
            self._status_label.config(
                text=f"BGM: {state_text} | 볼륨: {self._bgm.volume}%",
            )

            next_ann = self._sched_manager.get_next_announcement()
            if next_ann:
                self._next_label.config(
                    text=f"다음 방송: {next_ann['label']} ({next_ann['time']})",
                )
            else:
                self._next_label.config(text="오늘 남은 방송 없음")

            self._root.after(1000, update)

        update()

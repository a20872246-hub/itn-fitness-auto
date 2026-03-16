import tkinter as tk
from tkinter import ttk, messagebox
import os
import logging

logger = logging.getLogger(__name__)


class SettingsTab:
    """Settings management tab."""

    def __init__(self, parent: ttk.Frame, settings: dict, config_manager):
        self._parent = parent
        self._settings = settings
        self._config_mgr = config_manager
        self._build_ui()

    def _build_ui(self):
        main = ttk.Frame(self._parent, padding=15)
        main.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(main, highlightthickness=0)
        scrollbar = ttk.Scrollbar(main, orient=tk.VERTICAL, command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor=tk.NW)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        bgm_settings = self._settings.get("bgm", {})
        ann_settings = self._settings.get("announcements", {})
        remote_settings = self._settings.get("remote", {})
        log_settings = self._settings.get("logging", {})

        # --- BGM Settings ---
        bgm_frame = ttk.LabelFrame(scroll_frame, text="BGM 설정", padding=10)
        bgm_frame.pack(fill=tk.X, pady=(0, 10), padx=5)

        row = ttk.Frame(bgm_frame)
        row.pack(fill=tk.X, pady=2)
        ttk.Label(row, text="기본 YouTube URL:", width=20).pack(side=tk.LEFT)
        self._bgm_url_var = tk.StringVar(value=bgm_settings.get("default_url", ""))
        ttk.Entry(row, textvariable=self._bgm_url_var).pack(side=tk.LEFT, fill=tk.X, expand=True)

        row = ttk.Frame(bgm_frame)
        row.pack(fill=tk.X, pady=2)
        ttk.Label(row, text="기본 볼륨:", width=20).pack(side=tk.LEFT)
        self._bgm_vol_var = tk.IntVar(value=bgm_settings.get("volume", 70))
        ttk.Spinbox(row, from_=0, to=100, width=6, textvariable=self._bgm_vol_var).pack(side=tk.LEFT)
        ttk.Label(row, text="%").pack(side=tk.LEFT, padx=(3, 0))

        row = ttk.Frame(bgm_frame)
        row.pack(fill=tk.X, pady=2)
        ttk.Label(row, text="안내방송 중 BGM 볼륨:", width=20).pack(side=tk.LEFT)
        self._ducked_vol_var = tk.IntVar(value=bgm_settings.get("ducked_volume", 15))
        ttk.Spinbox(row, from_=0, to=100, width=6, textvariable=self._ducked_vol_var).pack(side=tk.LEFT)
        ttk.Label(row, text="%").pack(side=tk.LEFT, padx=(3, 0))

        row = ttk.Frame(bgm_frame)
        row.pack(fill=tk.X, pady=2)
        ttk.Label(row, text="페이드 시간:", width=20).pack(side=tk.LEFT)
        self._fade_var = tk.DoubleVar(value=bgm_settings.get("fade_duration", 1.5))
        ttk.Spinbox(row, from_=0.1, to=5.0, increment=0.1, width=6,
                     textvariable=self._fade_var).pack(side=tk.LEFT)
        ttk.Label(row, text="초").pack(side=tk.LEFT, padx=(3, 0))

        row = ttk.Frame(bgm_frame)
        row.pack(fill=tk.X, pady=2)
        self._auto_play_var = tk.BooleanVar(value=bgm_settings.get("auto_play", False))
        ttk.Checkbutton(row, text="시작 시 자동 재생", variable=self._auto_play_var).pack(side=tk.LEFT)

        # --- Announcement Settings ---
        ann_frame = ttk.LabelFrame(scroll_frame, text="안내방송 설정", padding=10)
        ann_frame.pack(fill=tk.X, pady=(0, 10), padx=5)

        row = ttk.Frame(ann_frame)
        row.pack(fill=tk.X, pady=2)
        ttk.Label(row, text="방송 후 대기:", width=20).pack(side=tk.LEFT)
        self._post_delay_var = tk.DoubleVar(value=ann_settings.get("post_delay", 1.0))
        ttk.Spinbox(row, from_=0, to=5.0, increment=0.1, width=6,
                     textvariable=self._post_delay_var).pack(side=tk.LEFT)
        ttk.Label(row, text="초").pack(side=tk.LEFT, padx=(3, 0))

        row = ttk.Frame(ann_frame)
        row.pack(fill=tk.X, pady=2)
        self._chime_enabled_var = tk.BooleanVar(value=ann_settings.get("chime_enabled", True))
        ttk.Checkbutton(row, text="방송 전 효과음 재생", variable=self._chime_enabled_var).pack(side=tk.LEFT)

        row = ttk.Frame(ann_frame)
        row.pack(fill=tk.X, pady=2)
        ttk.Label(row, text="효과음 종류:", width=20).pack(side=tk.LEFT)
        from core.announcement import CHIME_PRESETS, DEFAULT_CHIME
        self._chime_keys = list(CHIME_PRESETS.keys())
        self._chime_labels = list(CHIME_PRESETS.values())
        current_chime = ann_settings.get("chime_type", DEFAULT_CHIME)
        current_idx = self._chime_keys.index(current_chime) if current_chime in self._chime_keys else 0
        self._chime_var = tk.StringVar(value=self._chime_labels[current_idx])
        chime_combo = ttk.Combobox(row, textvariable=self._chime_var, width=20,
                                    values=self._chime_labels, state="readonly")
        chime_combo.pack(side=tk.LEFT)
        chime_combo.current(current_idx)
        ttk.Button(row, text="미리듣기", command=self._preview_chime).pack(side=tk.LEFT, padx=(8, 0))

        # --- Remote Settings ---
        remote_frame = ttk.LabelFrame(scroll_frame, text="원격 제어 설정", padding=10)
        remote_frame.pack(fill=tk.X, pady=(0, 10), padx=5)

        row = ttk.Frame(remote_frame)
        row.pack(fill=tk.X, pady=2)
        self._remote_enabled_var = tk.BooleanVar(value=remote_settings.get("enabled", False))
        ttk.Checkbutton(row, text="원격 제어 활성화 (재시작 필요)",
                         variable=self._remote_enabled_var).pack(side=tk.LEFT)

        row = ttk.Frame(remote_frame)
        row.pack(fill=tk.X, pady=2)
        ttk.Label(row, text="포트:", width=20).pack(side=tk.LEFT)
        self._port_var = tk.IntVar(value=remote_settings.get("port", 8585))
        ttk.Spinbox(row, from_=1024, to=65535, width=8,
                     textvariable=self._port_var).pack(side=tk.LEFT)

        row = ttk.Frame(remote_frame)
        row.pack(fill=tk.X, pady=2)
        ttk.Label(row, text="새 비밀번호:", width=20).pack(side=tk.LEFT)
        self._password_var = tk.StringVar()
        ttk.Entry(row, textvariable=self._password_var, show="*").pack(
            side=tk.LEFT, fill=tk.X, expand=True)

        # --- Logging Settings ---
        log_frame = ttk.LabelFrame(scroll_frame, text="로그 설정", padding=10)
        log_frame.pack(fill=tk.X, pady=(0, 10), padx=5)

        row = ttk.Frame(log_frame)
        row.pack(fill=tk.X, pady=2)
        ttk.Label(row, text="로그 레벨:", width=20).pack(side=tk.LEFT)
        self._log_level_var = tk.StringVar(value=log_settings.get("level", "INFO"))
        ttk.Combobox(row, textvariable=self._log_level_var, width=10,
                      values=["DEBUG", "INFO", "WARNING", "ERROR"],
                      state="readonly").pack(side=tk.LEFT)

        # --- Save/Reset buttons ---
        btn_frame = ttk.Frame(scroll_frame)
        btn_frame.pack(fill=tk.X, pady=10, padx=5)

        ttk.Button(btn_frame, text="설정 저장", command=self._save).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(btn_frame, text="기본값 복원", command=self._reset).pack(side=tk.LEFT)

    def _save(self):
        s = self._settings

        s.setdefault("bgm", {})
        s["bgm"]["default_url"] = self._bgm_url_var.get()
        s["bgm"]["volume"] = self._bgm_vol_var.get()
        s["bgm"]["ducked_volume"] = self._ducked_vol_var.get()
        s["bgm"]["fade_duration"] = self._fade_var.get()
        s["bgm"]["auto_play"] = self._auto_play_var.get()

        s.setdefault("announcements", {})
        s["announcements"]["post_delay"] = self._post_delay_var.get()
        s["announcements"]["chime_enabled"] = self._chime_enabled_var.get()
        selected_label = self._chime_var.get()
        if selected_label in self._chime_labels:
            idx = self._chime_labels.index(selected_label)
            s["announcements"]["chime_type"] = self._chime_keys[idx]

        s.setdefault("remote", {})
        s["remote"]["enabled"] = self._remote_enabled_var.get()
        s["remote"]["port"] = self._port_var.get()

        pw = self._password_var.get()
        if pw:
            import bcrypt
            hash_str = bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()
            s["remote"]["password_hash"] = hash_str

        s.setdefault("logging", {})
        s["logging"]["level"] = self._log_level_var.get()

        self._config_mgr.save()
        messagebox.showinfo("저장 완료", "설정이 저장되었습니다.\n일부 설정은 재시작 후 적용됩니다.")

    def _reset(self):
        if messagebox.askyesno("기본값 복원", "모든 설정을 기본값으로 복원하시겠습니까?"):
            self._bgm_url_var.set("")
            self._bgm_vol_var.set(70)
            self._ducked_vol_var.set(15)
            self._fade_var.set(1.5)
            self._auto_play_var.set(False)
            self._post_delay_var.set(1.0)
            self._chime_enabled_var.set(True)
            from core.announcement import DEFAULT_CHIME, CHIME_PRESETS
            default_idx = self._chime_keys.index(DEFAULT_CHIME) if DEFAULT_CHIME in self._chime_keys else 0
            self._chime_var.set(self._chime_labels[default_idx])
            self._remote_enabled_var.set(False)
            self._port_var.set(8585)
            self._log_level_var.set("INFO")

    def _preview_chime(self):
        """Play the currently selected chime sound."""
        selected_label = self._chime_var.get()
        if selected_label not in self._chime_labels:
            return
        idx = self._chime_labels.index(selected_label)
        chime_key = self._chime_keys[idx]

        chimes_dir = os.path.join(
            self._settings.get("announcements", {}).get("base_dir", "assets/announcements"),
            "chimes",
        )
        path = None
        for ext in ("wav", "mp3"):
            candidate = os.path.join(chimes_dir, f"{chime_key}.{ext}")
            if os.path.exists(candidate):
                path = candidate
                break

        if not path:
            messagebox.showwarning("파일 없음", f"효과음 파일을 찾을 수 없습니다: {chime_key}")
            return

        import threading
        def _play():
            try:
                import vlc
                import platform
                # Windows audio output fix
                if platform.system() == "Windows":
                    instance = vlc.Instance(
                        "--no-video",
                        "--quiet",
                        "--aout=directsound",
                        "--audio-resampler=samplerate",
                        "--directx-audio-device=",
                        "--mmdevice-audio-device=",
                    )
                else:
                    instance = vlc.Instance("--no-video", "--quiet")

                player = instance.media_player_new()
                media = instance.media_new(os.path.abspath(path))
                player.set_media(media)
                player.audio_set_volume(100)  # Set volume BEFORE play
                player.play()
                import time
                time.sleep(0.2)  # Increased wait time for Windows
                player.audio_set_volume(100)  # Set again after play
                # Wait for playback to finish (max 5 seconds)
                for _ in range(50):
                    time.sleep(0.1)
                    if player.get_state() == vlc.State.Ended:
                        break
                player.release()
                instance.release()
            except Exception as e:
                logger.error(f"Chime preview error: {e}")

        threading.Thread(target=_play, daemon=True).start()

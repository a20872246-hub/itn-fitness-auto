import tkinter as tk
from tkinter import ttk, messagebox
import logging

logger = logging.getLogger(__name__)


class BGMTab:
    """BGM player control tab with playlist support."""

    def __init__(self, parent: ttk.Frame, bgm_player, settings: dict, config_manager=None):
        self._parent = parent
        self._bgm = bgm_player
        self._settings = settings
        self._config_mgr = config_manager
        self._root = parent.winfo_toplevel()
        self._build_ui()
        self._load_playlist()
        self._register_callbacks()

    def _build_ui(self):
        main = ttk.Frame(self._parent, padding=10)
        main.pack(fill=tk.BOTH, expand=True)

        # --- Status Section ---
        status_frame = ttk.LabelFrame(main, text="상태", padding=8)
        status_frame.pack(fill=tk.X, pady=(0, 8))

        row1 = ttk.Frame(status_frame)
        row1.pack(fill=tk.X)
        ttk.Label(row1, text="상태:").pack(side=tk.LEFT)
        self._state_label = ttk.Label(row1, text="정지", font=("", 12, "bold"))
        self._state_label.pack(side=tk.LEFT, padx=(8, 0))

        row2 = ttk.Frame(status_frame)
        row2.pack(fill=tk.X, pady=(4, 0))
        ttk.Label(row2, text="재생 중:").pack(side=tk.LEFT)
        self._title_label = ttk.Label(row2, text="없음", foreground="gray")
        self._title_label.pack(side=tk.LEFT, padx=(8, 0))

        row3 = ttk.Frame(status_frame)
        row3.pack(fill=tk.X, pady=(2, 0))
        ttk.Label(row3, text="트랙:").pack(side=tk.LEFT)
        self._track_label = ttk.Label(row3, text="- / -", foreground="gray")
        self._track_label.pack(side=tk.LEFT, padx=(8, 0))

        # --- Playlist Section ---
        pl_frame = ttk.LabelFrame(main, text="재생목록", padding=8)
        pl_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        # URL input row
        url_row = ttk.Frame(pl_frame)
        url_row.pack(fill=tk.X, pady=(0, 6))

        self._url_var = tk.StringVar()
        self._url_entry = tk.Entry(url_row, textvariable=self._url_var, font=("", 12))
        self._url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        self._url_entry.insert(0, "YouTube URL을 붙여넣기 하세요")
        self._url_entry.config(fg="gray")
        self._url_entry.bind("<FocusIn>", self._on_url_focus_in)
        self._url_entry.bind("<FocusOut>", self._on_url_focus_out)
        self._url_entry.bind("<Return>", lambda e: self._add_url())
        # Enable Cmd+V paste on macOS
        self._url_entry.bind("<Command-v>", self._on_paste)
        self._url_entry.bind("<Control-v>", self._on_paste)
        # Right-click context menu
        self._url_entry.bind("<Button-2>", self._show_context_menu)  # macOS right-click
        self._url_entry.bind("<Button-3>", self._show_context_menu)  # fallback

        ttk.Button(url_row, text="추가", command=self._add_url).pack(side=tk.RIGHT)

        # Playlist listbox
        list_frame = ttk.Frame(pl_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)

        self._playlist_listbox = tk.Listbox(
            list_frame, font=("", 11), height=6,
            selectmode=tk.SINGLE, activestyle="none",
        )
        self._playlist_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._playlist_listbox.bind("<Double-1>", self._on_double_click)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL,
                                   command=self._playlist_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._playlist_listbox.config(yscrollcommand=scrollbar.set)

        # Playlist buttons
        pl_btn_row = ttk.Frame(pl_frame)
        pl_btn_row.pack(fill=tk.X, pady=(6, 0))

        ttk.Button(pl_btn_row, text="선택 재생", command=self._play_selected).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(pl_btn_row, text="삭제", command=self._remove_selected).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(pl_btn_row, text="위로", command=self._move_up).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(pl_btn_row, text="아래로", command=self._move_down).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(pl_btn_row, text="저장", command=self._save_playlist).pack(side=tk.RIGHT)
        ttk.Button(pl_btn_row, text="정보 가져오기", command=self._fetch_all_info).pack(side=tk.RIGHT, padx=(0, 4))

        # --- Controls ---
        ctrl_frame = ttk.LabelFrame(main, text="제어", padding=8)
        ctrl_frame.pack(fill=tk.X, pady=(0, 8))

        btn_row = ttk.Frame(ctrl_frame)
        btn_row.pack(fill=tk.X)

        ttk.Button(btn_row, text="⏮ 이전", command=self._prev).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(btn_row, text="▶ 재생", command=self._play).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(btn_row, text="⏸ 일시정지", command=self._pause).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(btn_row, text="⏹ 정지", command=self._stop).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(btn_row, text="⏭ 다음", command=self._next).pack(side=tk.LEFT)

        # --- Seek Bar (재생 구간) ---
        seek_frame = ttk.Frame(ctrl_frame)
        seek_frame.pack(fill=tk.X, pady=(6, 0))

        self._time_current_label = ttk.Label(seek_frame, text="0:00", width=7, anchor=tk.E)
        self._time_current_label.pack(side=tk.LEFT)

        self._seeking = False
        self._seek_var = tk.DoubleVar(value=0)
        self._seek_scale = ttk.Scale(
            seek_frame, from_=0, to=1000, orient=tk.HORIZONTAL,
            variable=self._seek_var,
            command=self._on_seek_drag,
        )
        self._seek_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        self._seek_scale.bind("<ButtonPress-1>", lambda e: setattr(self, '_seeking', True))
        self._seek_scale.bind("<ButtonRelease-1>", self._on_seek_release)

        self._time_total_label = ttk.Label(seek_frame, text="0:00", width=7, anchor=tk.W)
        self._time_total_label.pack(side=tk.LEFT)

        # Start position update timer
        self._update_seek_bar()

        # --- Volume ---
        vol_frame = ttk.LabelFrame(main, text="볼륨", padding=8)
        vol_frame.pack(fill=tk.X, pady=(0, 8))

        vol_row = ttk.Frame(vol_frame)
        vol_row.pack(fill=tk.X)

        ttk.Label(vol_row, text="0").pack(side=tk.LEFT)
        self._volume_var = tk.IntVar(value=self._bgm.volume)
        self._volume_scale = ttk.Scale(
            vol_row, from_=0, to=100, orient=tk.HORIZONTAL,
            variable=self._volume_var, command=self._on_volume_change,
        )
        self._volume_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)
        ttk.Label(vol_row, text="100").pack(side=tk.LEFT)

        self._volume_label = ttk.Label(vol_row, text=f"{self._bgm.volume}%",
                                        font=("", 12, "bold"), width=5)
        self._volume_label.pack(side=tk.RIGHT)

        # --- Quick Settings ---
        qs_frame = ttk.LabelFrame(main, text="빠른 설정", padding=8)
        qs_frame.pack(fill=tk.X)

        qs_row = ttk.Frame(qs_frame)
        qs_row.pack(fill=tk.X)

        ttk.Label(qs_row, text="안내방송 중 BGM 볼륨:").pack(side=tk.LEFT)
        self._ducked_var = tk.IntVar(
            value=self._settings.get("bgm", {}).get("ducked_volume", 15)
        )
        ttk.Spinbox(qs_row, from_=0, to=100, width=5,
                     textvariable=self._ducked_var).pack(side=tk.LEFT, padx=(8, 4))
        ttk.Label(qs_row, text="%").pack(side=tk.LEFT)

    # --- Context menu & paste support ---

    def _show_context_menu(self, event):
        """Show right-click context menu with paste/copy/cut/select all."""
        menu = tk.Menu(self._root, tearoff=0)
        menu.add_command(label="잘라내기", command=lambda: self._url_entry.event_generate("<<Cut>>"))
        menu.add_command(label="복사", command=lambda: self._url_entry.event_generate("<<Copy>>"))
        menu.add_command(label="붙여넣기", command=self._paste_from_menu)
        menu.add_separator()
        menu.add_command(label="전체 선택", command=lambda: (
            self._url_entry.select_range(0, tk.END),
            self._url_entry.icursor(tk.END),
        ))
        # Focus the entry first so paste goes to the right widget
        self._url_entry.focus_set()
        if self._url_entry.cget("fg") == "gray":
            self._url_entry.delete(0, tk.END)
            self._url_entry.config(fg="black")
        menu.tk_popup(event.x_root, event.y_root)

    def _paste_from_menu(self):
        """Paste from clipboard via right-click menu."""
        try:
            clipboard = self._root.clipboard_get()
            if self._url_entry.cget("fg") == "gray":
                self._url_entry.delete(0, tk.END)
                self._url_entry.config(fg="black")
            try:
                self._url_entry.delete(tk.SEL_FIRST, tk.SEL_LAST)
            except tk.TclError:
                pass
            self._url_entry.insert(tk.INSERT, clipboard)
        except tk.TclError:
            pass

    def _on_paste(self, event):
        """Handle Cmd+V / Ctrl+V paste."""
        try:
            clipboard = self._root.clipboard_get()
            # If placeholder text is shown, clear it first
            if self._url_entry.cget("fg") == "gray":
                self._url_entry.delete(0, tk.END)
                self._url_entry.config(fg="black")
            # If there's a selection, replace it
            try:
                self._url_entry.delete(tk.SEL_FIRST, tk.SEL_LAST)
            except tk.TclError:
                pass
            self._url_entry.insert(tk.INSERT, clipboard)
            return "break"  # Prevent default paste handler duplication
        except tk.TclError:
            pass

    def _on_url_focus_in(self, event):
        if self._url_entry.cget("fg") == "gray":
            self._url_entry.delete(0, tk.END)
            self._url_entry.config(fg="black")

    def _on_url_focus_out(self, event):
        if not self._url_var.get().strip():
            self._url_entry.insert(0, "YouTube URL을 붙여넣기 하세요")
            self._url_entry.config(fg="gray")

    # --- Playlist management ---

    def _load_playlist(self):
        """Load saved playlist from settings."""
        urls = self._settings.get("bgm", {}).get("playlist", [])
        if urls:
            self._bgm.set_playlist(urls)
            self._refresh_listbox()

    def _save_playlist(self):
        """Save current playlist to settings."""
        urls = [item["url"] for item in self._bgm.get_playlist()]
        self._settings.setdefault("bgm", {})["playlist"] = urls
        if self._config_mgr:
            self._config_mgr.save()
        messagebox.showinfo("저장 완료", f"재생목록 {len(urls)}곡이 저장되었습니다.")

    def _refresh_listbox(self):
        """Refresh the listbox display from BGMPlayer playlist."""
        self._playlist_listbox.delete(0, tk.END)
        playlist = self._bgm.get_playlist()
        current_idx = self._bgm.playlist_index
        from core.bgm_player import BGMPlayer

        total_duration = 0
        for i, item in enumerate(playlist):
            title = item.get("title") or self._shorten_url(item["url"])
            duration = item.get("duration", 0)
            total_duration += duration
            dur_str = f"  [{BGMPlayer.format_duration(duration)}]" if duration > 0 else ""
            prefix = "▶ " if i == current_idx else f"{i + 1}. "
            self._playlist_listbox.insert(tk.END, f"{prefix}{title}{dur_str}")

            if i == current_idx:
                self._playlist_listbox.itemconfig(i, fg="#007AFF")

        # Update track label with total duration
        count = len(playlist)
        if total_duration > 0:
            total_str = BGMPlayer.format_duration(total_duration)
            self._track_label.config(text=f"총 {count}곡 ({total_str})")
        elif count > 0:
            self._track_label.config(text=f"총 {count}곡")

    def _shorten_url(self, url: str) -> str:
        """Shorten URL for display."""
        if len(url) > 60:
            return url[:57] + "..."
        return url

    def _add_url(self):
        url = self._url_var.get().strip()
        if not url or url == "YouTube URL을 붙여넣기 하세요":
            messagebox.showwarning("URL 필요", "YouTube URL을 입력해주세요.")
            return

        # Ensure it looks like a URL
        if not url.startswith("http"):
            url = "https://" + url

        self._bgm.add_to_playlist(url)
        new_idx = self._bgm.playlist_count - 1
        self._url_entry.delete(0, tk.END)
        self._refresh_listbox()

        # Fetch title & duration in background
        self._bgm.fetch_info(new_idx, callback=lambda i, t, d: self._root.after(0, self._refresh_listbox))

    def _fetch_all_info(self):
        """Fetch title & duration for all playlist items that don't have it yet."""
        playlist = self._bgm.get_playlist()
        count = 0
        for i, item in enumerate(playlist):
            if not item.get("title") or item.get("duration", 0) == 0:
                self._bgm.fetch_info(i, callback=lambda idx, t, d: self._root.after(0, self._refresh_listbox))
                count += 1
        if count == 0:
            messagebox.showinfo("정보", "모든 곡의 정보가 이미 로드되어 있습니다.")
        else:
            messagebox.showinfo("정보 가져오기", f"{count}곡의 정보를 가져오는 중...\n잠시 후 목록이 업데이트됩니다.")

    def _remove_selected(self):
        selection = self._playlist_listbox.curselection()
        if not selection:
            return
        idx = selection[0]
        self._bgm.remove_from_playlist(idx)
        self._refresh_listbox()

    def _move_up(self):
        selection = self._playlist_listbox.curselection()
        if not selection or selection[0] == 0:
            return
        idx = selection[0]
        self._bgm.move_in_playlist(idx, idx - 1)
        self._refresh_listbox()
        self._playlist_listbox.selection_set(idx - 1)

    def _move_down(self):
        selection = self._playlist_listbox.curselection()
        if not selection or selection[0] >= self._bgm.playlist_count - 1:
            return
        idx = selection[0]
        self._bgm.move_in_playlist(idx, idx + 1)
        self._refresh_listbox()
        self._playlist_listbox.selection_set(idx + 1)

    def _on_double_click(self, event):
        """Double-click a playlist item to play it."""
        selection = self._playlist_listbox.curselection()
        if selection:
            self._bgm.play_index(selection[0])

    def _play_selected(self):
        selection = self._playlist_listbox.curselection()
        if selection:
            self._bgm.play_index(selection[0])
        elif self._bgm.playlist_count > 0:
            self._bgm.play_index(0)

    # --- Playback controls ---

    def _register_callbacks(self):
        self._bgm.on_state_change(self._on_state_change)
        self._bgm.on_track_change(self._on_track_change)

    def _on_state_change(self, state):
        self._root.after(0, self._update_state_display, state)

    def _on_track_change(self, index, title):
        self._root.after(0, self._update_track_display, index, title)

    def _update_state_display(self, state):
        state_map = {
            "stopped": ("정지", "gray"),
            "playing": ("재생 중", "green"),
            "paused": ("일시정지", "orange"),
            "loading": ("로딩 중...", "blue"),
            "error": ("오류", "red"),
        }
        text, color = state_map.get(state.value, ("알 수 없음", "gray"))
        self._state_label.config(text=text, foreground=color)
        self._title_label.config(text=self._bgm.title or "없음")

    def _update_track_display(self, index, title):
        """Update UI when playlist track changes."""
        total = self._bgm.playlist_count
        if total > 0 and index >= 0:
            self._track_label.config(text=f"{index + 1} / {total}")
        else:
            self._track_label.config(text="- / -")
        self._title_label.config(text=title or "없음")
        self._refresh_listbox()

    def _play(self):
        if self._bgm.playlist_count > 0:
            if self._bgm.playlist_index < 0:
                self._bgm.play_index(0)
            else:
                self._bgm.play_index(self._bgm.playlist_index)
        else:
            messagebox.showwarning("재생목록 비어있음", "먼저 YouTube URL을 추가해주세요.")

    def _pause(self):
        self._bgm.pause()

    def _stop(self):
        self._bgm.stop()

    def _next(self):
        self._bgm.play_next()

    def _prev(self):
        self._bgm.play_prev()

    # --- Seek bar ---

    def _update_seek_bar(self):
        """Periodically update the seek bar position (every 500ms)."""
        from core.bgm_player import BGMPlayer, BGMState
        try:
            if self._bgm.state == BGMState.PLAYING and not self._seeking:
                player = self._bgm.player
                pos = player.get_time()  # ms, -1 if not available
                length = player.get_length()  # ms

                if pos >= 0 and length > 0:
                    # Update scale position (0-1000 range)
                    scale_pos = (pos / length) * 1000
                    self._seek_var.set(scale_pos)

                    # Update time labels
                    self._time_current_label.config(
                        text=BGMPlayer.format_duration(pos // 1000)
                    )
                    self._time_total_label.config(
                        text=BGMPlayer.format_duration(length // 1000)
                    )
                elif pos < 0:
                    # Streaming with no length info - show elapsed only
                    pass
            elif self._bgm.state == BGMState.STOPPED:
                self._seek_var.set(0)
                self._time_current_label.config(text="0:00")
                self._time_total_label.config(text="0:00")
        except Exception:
            pass

        self._root.after(500, self._update_seek_bar)

    def _on_seek_drag(self, val):
        """Called while dragging the seek bar - update time label only."""
        if not self._seeking:
            return
        try:
            player = self._bgm.player
            length = player.get_length()
            if length > 0:
                from core.bgm_player import BGMPlayer
                pos_ms = int((float(val) / 1000) * length)
                self._time_current_label.config(
                    text=BGMPlayer.format_duration(pos_ms // 1000)
                )
        except Exception:
            pass

    def _on_seek_release(self, event):
        """Called when user releases the seek bar - actually seek."""
        self._seeking = False
        try:
            player = self._bgm.player
            length = player.get_length()
            if length > 0:
                position = float(self._seek_var.get()) / 1000  # 0.0 ~ 1.0
                player.set_position(position)
        except Exception:
            pass

    def _on_volume_change(self, val):
        vol = int(float(val))
        self._bgm.volume = vol
        self._volume_label.config(text=f"{vol}%")

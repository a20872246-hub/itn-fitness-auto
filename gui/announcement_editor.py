import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import shutil
import logging

logger = logging.getLogger(__name__)


class AnnouncementEditor:
    """Announcement catalog management tab."""

    def __init__(self, parent: ttk.Frame, announcement_manager):
        self._parent = parent
        self._ann = announcement_manager
        self._root = parent.winfo_toplevel()
        self._build_ui()
        self._refresh_tree()

    def _build_ui(self):
        main = ttk.Frame(self._parent, padding=10)
        main.pack(fill=tk.BOTH, expand=True)

        # Left: Category tree
        left = ttk.Frame(main, width=250)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        left.pack_propagate(False)

        ttk.Label(left, text="안내방송 목록", font=("", 11, "bold")).pack(anchor=tk.W, pady=(0, 5))

        self._tree = ttk.Treeview(left, show="tree", height=18)
        self._tree.pack(fill=tk.BOTH, expand=True)
        self._tree.bind("<<TreeviewSelect>>", self._on_select)

        tree_btn_row = ttk.Frame(left)
        tree_btn_row.pack(fill=tk.X, pady=(5, 0))
        ttk.Button(tree_btn_row, text="추가", command=self._add_item).pack(side=tk.LEFT, padx=(0, 3))
        ttk.Button(tree_btn_row, text="삭제", command=self._delete_item).pack(side=tk.LEFT)
        ttk.Button(tree_btn_row, text="새로고침", command=self._refresh_tree).pack(side=tk.RIGHT)

        # Right: Detail panel
        right = ttk.Frame(main)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._detail_frame = ttk.LabelFrame(right, text="상세 정보", padding=10)
        self._detail_frame.pack(fill=tk.BOTH, expand=True)

        # ID
        row = ttk.Frame(self._detail_frame)
        row.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(row, text="ID:", width=10).pack(side=tk.LEFT)
        self._id_var = tk.StringVar()
        self._id_entry = ttk.Entry(row, textvariable=self._id_var, state="readonly")
        self._id_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Category
        row = ttk.Frame(self._detail_frame)
        row.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(row, text="카테고리:", width=10).pack(side=tk.LEFT)
        self._cat_var = tk.StringVar()
        self._cat_entry = ttk.Entry(row, textvariable=self._cat_var, state="readonly")
        self._cat_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Label
        row = ttk.Frame(self._detail_frame)
        row.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(row, text="이름:", width=10).pack(side=tk.LEFT)
        self._label_var = tk.StringVar()
        ttk.Entry(row, textvariable=self._label_var).pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Text
        ttk.Label(self._detail_frame, text="멘트 텍스트:").pack(anchor=tk.W, pady=(5, 2))
        self._text_widget = tk.Text(self._detail_frame, height=4, font=("", 11), wrap=tk.WORD)
        self._text_widget.pack(fill=tk.X, pady=(0, 5))

        # File
        row = ttk.Frame(self._detail_frame)
        row.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(row, text="음성 파일:", width=10).pack(side=tk.LEFT)
        self._file_var = tk.StringVar()
        ttk.Entry(row, textvariable=self._file_var, state="readonly").pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Button(row, text="파일 선택", command=self._import_file).pack(side=tk.RIGHT)

        # Voice selector
        voice_row = ttk.Frame(self._detail_frame)
        voice_row.pack(fill=tk.X, pady=(8, 0))
        ttk.Label(voice_row, text="음성:", width=10).pack(side=tk.LEFT)

        from core.announcement import VOICE_PRESETS, DEFAULT_VOICE
        self._voice_keys = list(VOICE_PRESETS.keys())
        self._voice_labels = [VOICE_PRESETS[k]["label"] for k in self._voice_keys]
        current_voice = self._ann._announcer.voice_id
        current_idx = self._voice_keys.index(current_voice) if current_voice in self._voice_keys else 0

        self._voice_var = tk.StringVar(value=self._voice_labels[current_idx])
        voice_combo = ttk.Combobox(voice_row, textvariable=self._voice_var, width=28,
                                    values=self._voice_labels, state="readonly")
        voice_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        voice_combo.current(current_idx)

        # Speed slider
        speed_row = ttk.Frame(self._detail_frame)
        speed_row.pack(fill=tk.X, pady=(8, 0))
        ttk.Label(speed_row, text="속도:", width=10).pack(side=tk.LEFT)

        self._speed_var = tk.IntVar(value=0)
        self._speed_scale = ttk.Scale(
            speed_row, from_=-30, to=50, orient=tk.HORIZONTAL,
            variable=self._speed_var,
            command=self._on_speed_change,
        )
        self._speed_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self._speed_label = ttk.Label(speed_row, text="0%", width=6)
        self._speed_label.pack(side=tk.LEFT)
        ttk.Button(speed_row, text="초기화", width=6,
                   command=lambda: self._speed_var.set(0) or self._on_speed_change(0)
                   ).pack(side=tk.LEFT, padx=(3, 0))

        # Action buttons
        action_row = ttk.Frame(self._detail_frame)
        action_row.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(action_row, text="저장", command=self._save_item).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(action_row, text="테스트 재생", command=self._test_play).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(action_row, text="TTS 생성", command=self._generate_tts).pack(side=tk.LEFT)

    def _refresh_tree(self):
        self._tree.delete(*self._tree.get_children())
        for cat_key, cat in self._ann.categories.items():
            cat_node = self._tree.insert(
                "", tk.END, iid=f"cat_{cat_key}",
                text=f"{cat.get('label', cat_key)} ({len(cat.get('items', []))})",
                open=True,
            )
            for item in cat.get("items", []):
                self._tree.insert(
                    cat_node, tk.END,
                    iid=f"item_{cat_key}_{item['id']}",
                    text=item.get("label", item["id"]),
                )

    def _on_select(self, event):
        selected = self._tree.selection()
        if not selected:
            return
        iid = selected[0]
        if not iid.startswith("item_"):
            return

        parts = iid.split("_", 2)
        cat_key = parts[1]
        item_id = parts[2]

        item = self._ann.get_item(cat_key, item_id)
        if not item:
            return

        self._id_var.set(item["id"])
        self._cat_var.set(cat_key)
        self._label_var.set(item.get("label", ""))
        self._text_widget.delete("1.0", tk.END)
        self._text_widget.insert("1.0", item.get("text", ""))
        self._file_var.set(item.get("file", "") or "없음 (TTS 사용)")

    def _save_item(self):
        cat = self._cat_var.get()
        item_id = self._id_var.get()
        if not cat or not item_id:
            return

        label = self._label_var.get()
        text = self._text_widget.get("1.0", tk.END).strip()

        self._ann.update_item(cat, item_id, label=label, text=text)
        self._refresh_tree()
        messagebox.showinfo("저장 완료", "안내방송 정보가 저장되었습니다.")

    def _on_speed_change(self, val):
        """Update speed label when slider moves."""
        speed = int(float(val))
        self._speed_var.set(speed)
        sign = "+" if speed >= 0 else ""
        self._speed_label.config(text=f"{sign}{speed}%")

    def _get_rate_string(self) -> str:
        """Get edge-tts rate string from speed slider value."""
        speed = self._speed_var.get()
        sign = "+" if speed >= 0 else ""
        return f"{sign}{speed}%"

    def _get_selected_voice_id(self) -> str:
        """Get voice_id from the dropdown selection."""
        voice_label = self._voice_var.get()
        for i, lbl in enumerate(self._voice_labels):
            if lbl == voice_label:
                return self._voice_keys[i]
        return self._voice_keys[0]

    def _test_play(self):
        cat = self._cat_var.get()
        item_id = self._id_var.get()
        if not cat or not item_id:
            messagebox.showwarning("선택 필요", "재생할 안내방송을 선택해주세요.")
            return
        # Apply selected voice and speed before playing
        self._ann._announcer.voice_id = self._get_selected_voice_id()
        self._ann._announcer.rate = self._get_rate_string()
        self._ann.broadcast(cat, item_id)

    def _generate_tts(self):
        cat = self._cat_var.get()
        item_id = self._id_var.get()
        text = self._text_widget.get("1.0", tk.END).strip()
        if not text:
            messagebox.showwarning("텍스트 필요", "멘트 텍스트를 입력해주세요.")
            return

        # Save first
        self._ann.update_item(cat, item_id, text=text)

        # Invalidate old cache for all voices
        self._ann._announcer.invalidate_cache(cat, item_id)

        # Generate TTS with selected voice and speed
        from core.announcement import AnnouncementPlayer, VOICE_PRESETS
        voice_id = self._get_selected_voice_id()
        rate_str = self._get_rate_string()
        self._ann._announcer.voice_id = voice_id
        self._ann._announcer.rate = rate_str
        cache_dir = os.path.join(
            self._ann._announcer._base_dir, ".tts_cache"
        )
        os.makedirs(cache_dir, exist_ok=True)
        rate_tag = rate_str.replace("+", "p").replace("-", "m").replace("%", "")
        cache_path = os.path.join(cache_dir, f"{cat}_{item_id}_{voice_id}_{rate_tag}.mp3")

        try:
            AnnouncementPlayer.generate_tts_file(text, cache_path, voice_id, rate_str)
            voice_label = VOICE_PRESETS.get(voice_id, {}).get("label", voice_id)
            messagebox.showinfo("TTS 생성 완료",
                                f"음성 파일이 생성되었습니다.\n음성: {voice_label}\n속도: {rate_str}\n{cache_path}")
        except Exception as e:
            messagebox.showerror("TTS 오류", f"TTS 생성 실패: {e}")

    def _import_file(self):
        cat = self._cat_var.get()
        item_id = self._id_var.get()
        if not cat or not item_id:
            return

        file_path = filedialog.askopenfilename(
            title="음성 파일 선택",
            filetypes=[("Audio files", "*.mp3 *.wav *.m4a"), ("All files", "*.*")],
        )
        if not file_path:
            return

        dest_dir = os.path.join("assets", "announcements", cat)
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, f"{item_id}.mp3")
        shutil.copy2(file_path, dest)

        self._ann.update_item(cat, item_id, file=dest)
        self._file_var.set(dest)
        messagebox.showinfo("파일 가져오기", f"음성 파일이 복사되었습니다.\n{dest}")

    def _add_item(self):
        dialog = tk.Toplevel(self._parent)
        dialog.title("안내방송 추가")
        dialog.geometry("380x300")
        dialog.transient(self._root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=15)
        frame.pack(fill=tk.BOTH, expand=True)

        # Category
        ttk.Label(frame, text="카테고리:").pack(anchor=tk.W)
        cat_var = tk.StringVar()
        categories = list(self._ann.categories.keys())
        cat_combo = ttk.Combobox(frame, textvariable=cat_var, values=categories, state="readonly")
        cat_combo.pack(fill=tk.X, pady=(0, 8))
        if categories:
            cat_combo.current(0)

        # ID
        ttk.Label(frame, text="ID (영문):").pack(anchor=tk.W)
        id_var = tk.StringVar()
        ttk.Entry(frame, textvariable=id_var).pack(fill=tk.X, pady=(0, 8))

        # Label
        ttk.Label(frame, text="표시 이름:").pack(anchor=tk.W)
        label_var = tk.StringVar()
        ttk.Entry(frame, textvariable=label_var).pack(fill=tk.X, pady=(0, 8))

        # Text
        ttk.Label(frame, text="멘트 텍스트:").pack(anchor=tk.W)
        text_widget = tk.Text(frame, height=3, font=("", 11))
        text_widget.pack(fill=tk.X, pady=(0, 8))

        def save():
            cat = cat_var.get()
            item_id = id_var.get().strip()
            label = label_var.get().strip()
            text = text_widget.get("1.0", tk.END).strip()

            if not item_id:
                messagebox.showwarning("ID 필요", "ID를 입력해주세요.")
                return
            if not label:
                label = item_id

            self._ann.add_item(cat, item_id, label, text)
            dialog.destroy()
            self._refresh_tree()

        ttk.Button(frame, text="추가", command=save).pack(pady=(5, 0))

    def _delete_item(self):
        selected = self._tree.selection()
        if not selected:
            return
        iid = selected[0]
        if not iid.startswith("item_"):
            messagebox.showinfo("항목 선택", "삭제할 안내방송 항목을 선택해주세요.")
            return

        parts = iid.split("_", 2)
        cat_key = parts[1]
        item_id = parts[2]

        item = self._ann.get_item(cat_key, item_id)
        label = item.get("label", item_id) if item else item_id

        if messagebox.askyesno("삭제 확인", f"'{label}'을(를) 삭제하시겠습니까?"):
            self._ann.remove_item(cat_key, item_id)
            self._refresh_tree()

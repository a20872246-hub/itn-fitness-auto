import tkinter as tk
from tkinter import ttk, messagebox
import logging

logger = logging.getLogger(__name__)

DAY_LABELS = {
    "monday": "월요일",
    "tuesday": "화요일",
    "wednesday": "수요일",
    "thursday": "목요일",
    "friday": "금요일",
    "saturday": "토요일",
    "sunday": "일요일",
}

DAY_SHORT = {
    "monday": "월",
    "tuesday": "화",
    "wednesday": "수",
    "thursday": "목",
    "friday": "금",
    "saturday": "토",
    "sunday": "일",
}

DAY_ORDER = ["monday", "tuesday", "wednesday", "thursday",
             "friday", "saturday", "sunday"]


BGM_ACTION_LABELS = {
    "": "없음",
    "play": "BGM 재생",
    "stop": "BGM 정지",
}

BGM_ACTION_OPTIONS = ["없음", "BGM 재생", "BGM 정지"]
BGM_ACTION_MAP = {"없음": "", "BGM 재생": "play", "BGM 정지": "stop"}
BGM_ACTION_REVERSE = {"": "없음", "play": "BGM 재생", "stop": "BGM 정지"}


def days_to_short(days: list[str]) -> str:
    """Convert list of day names to short Korean string like '월화수목금'."""
    return "".join(DAY_SHORT.get(d, "") for d in DAY_ORDER if d in days)


class ScheduleEditor:
    """Schedule editing tab."""

    def __init__(self, parent: ttk.Frame, schedule_manager, announcement_manager):
        self._parent = parent
        self._sched = schedule_manager
        self._ann = announcement_manager
        self._updating_checkboxes = False
        self._build_ui()
        self._refresh_schedule()

    def _build_ui(self):
        main = ttk.Frame(self._parent, padding=10)
        main.pack(fill=tk.BOTH, expand=True)

        # Left: Day checkboxes to edit selected entry's days
        left = ttk.Frame(main, width=130)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        left.pack_propagate(False)

        ttk.Label(left, text="요일 설정", font=("", 11, "bold")).pack(pady=(0, 8))

        self._day_vars = {}
        self._day_cbs = {}
        for day in DAY_ORDER:
            var = tk.BooleanVar(value=False)
            cb = ttk.Checkbutton(
                left, text=DAY_LABELS[day], variable=var,
                command=self._on_day_checkbox_toggled,
                state="disabled",
            )
            cb.pack(anchor=tk.W, pady=2)
            self._day_vars[day] = var
            self._day_cbs[day] = cb

        ttk.Separator(left, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)

        # Quick select buttons
        self._quick_btns = []
        for text, cmd in [("평일 선택", self._quick_weekdays),
                          ("주말 선택", self._quick_weekend),
                          ("전체 선택", self._quick_all)]:
            btn = ttk.Button(left, text=text, command=cmd, state="disabled")
            btn.pack(fill=tk.X, pady=1)
            self._quick_btns.append(btn)

        self._day_info_label = ttk.Label(left, text="← 항목을 먼저\n   선택하세요",
                                          foreground="gray", wraplength=110,
                                          font=("", 10))
        self._day_info_label.pack(pady=(10, 0))

        # Right: Schedule tables
        right = ttk.Frame(main)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # --- Announcement Schedule ---
        ann_frame = ttk.LabelFrame(right, text="안내방송 스케줄", padding=5)
        ann_frame.pack(fill=tk.BOTH, expand=True)

        cols = ("time", "label", "days", "announcement", "bgm_action")
        self._tree = ttk.Treeview(ann_frame, columns=cols, show="headings", height=8)
        self._tree.heading("time", text="시간")
        self._tree.heading("label", text="방송 이름")
        self._tree.heading("days", text="요일")
        self._tree.heading("announcement", text="방송 종류")
        self._tree.heading("bgm_action", text="BGM")
        self._tree.column("time", width=60, anchor=tk.CENTER)
        self._tree.column("label", width=160)
        self._tree.column("days", width=90, anchor=tk.CENTER)
        self._tree.column("announcement", width=130)
        self._tree.column("bgm_action", width=80, anchor=tk.CENTER)
        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._tree.bind("<<TreeviewSelect>>", self._on_ann_select)

        scrollbar = ttk.Scrollbar(ann_frame, orient=tk.VERTICAL, command=self._tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._tree.configure(yscrollcommand=scrollbar.set)

        btn_row = ttk.Frame(ann_frame)
        btn_row.pack(fill=tk.X, pady=(5, 0))

        ttk.Button(btn_row, text="추가", command=self._add_entry).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_row, text="편집", command=self._edit_entry).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_row, text="삭제", command=self._remove_entry).pack(side=tk.LEFT, padx=(0, 5))

        # --- BGM Schedule ---
        bgm_frame = ttk.LabelFrame(right, text="BGM 스케줄", padding=5)
        bgm_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        bgm_cols = ("time", "label", "days", "tracks")
        self._bgm_tree = ttk.Treeview(bgm_frame, columns=bgm_cols,
                                        show="headings", height=5)
        self._bgm_tree.heading("time", text="시간")
        self._bgm_tree.heading("label", text="재생목록 이름")
        self._bgm_tree.heading("days", text="요일")
        self._bgm_tree.heading("tracks", text="곡 수")
        self._bgm_tree.column("time", width=60, anchor=tk.CENTER)
        self._bgm_tree.column("label", width=180)
        self._bgm_tree.column("days", width=90, anchor=tk.CENTER)
        self._bgm_tree.column("tracks", width=60, anchor=tk.CENTER)
        self._bgm_tree.pack(fill=tk.BOTH, expand=True)
        self._bgm_tree.bind("<<TreeviewSelect>>", self._on_bgm_select)

        bgm_btn_row = ttk.Frame(bgm_frame)
        bgm_btn_row.pack(fill=tk.X, pady=(5, 0))

        ttk.Button(bgm_btn_row, text="추가",
                   command=self._add_bgm_entry).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(bgm_btn_row, text="편집",
                   command=self._edit_bgm_entry).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(bgm_btn_row, text="삭제",
                   command=self._remove_bgm_entry).pack(side=tk.LEFT)

        # Bottom info
        bottom = ttk.Frame(right)
        bottom.pack(fill=tk.X, pady=(8, 0))

        self._next_label = ttk.Label(bottom, text="", foreground="blue")
        self._next_label.pack(side=tk.LEFT)

        ttk.Button(bottom, text="새로고침",
                   command=self._refresh_schedule).pack(side=tk.RIGHT)

    # --- Left panel checkbox logic ---

    def _on_ann_select(self, event):
        """Announcement entry selected -> show its days in left checkboxes."""
        for sel in self._bgm_tree.selection():
            self._bgm_tree.selection_remove(sel)
        entry = self._find_selected_ann_entry()
        if entry:
            self._set_checkboxes(entry.get("days", []))
            self._day_info_label.config(text=entry.get("label", ""), foreground="black")
        else:
            self._clear_checkboxes()

    def _on_bgm_select(self, event):
        """BGM entry selected -> show its days in left checkboxes."""
        for sel in self._tree.selection():
            self._tree.selection_remove(sel)
        entry = self._find_selected_bgm_entry()
        if entry:
            self._set_checkboxes(entry.get("days", []))
            self._day_info_label.config(text=entry.get("label", ""), foreground="black")
        else:
            self._clear_checkboxes()

    def _find_selected_ann_entry(self):
        selected = self._tree.selection()
        if not selected:
            return None
        values = self._tree.item(selected[0], "values")
        time_str = values[0]
        announcement = values[3]
        for item in self._sched.scheduled_items:
            if item["time"] == time_str and item["announcement"] == announcement:
                return item
        return None

    def _find_selected_bgm_entry(self):
        selected = self._bgm_tree.selection()
        if not selected:
            return None
        values = self._bgm_tree.item(selected[0], "values")
        time_str = values[0]
        for item in self._sched.bgm_scheduled_items:
            if item["time"] == time_str:
                return item
        return None

    def _enable_day_panel(self):
        for cb in self._day_cbs.values():
            cb.config(state="normal")
        for btn in self._quick_btns:
            btn.config(state="normal")

    def _disable_day_panel(self):
        for cb in self._day_cbs.values():
            cb.config(state="disabled")
        for btn in self._quick_btns:
            btn.config(state="disabled")

    def _set_checkboxes(self, days: list[str]):
        self._updating_checkboxes = True
        for day in DAY_ORDER:
            self._day_vars[day].set(day in days)
        self._updating_checkboxes = False
        self._enable_day_panel()

    def _clear_checkboxes(self):
        self._updating_checkboxes = True
        for var in self._day_vars.values():
            var.set(False)
        self._updating_checkboxes = False
        self._disable_day_panel()
        self._day_info_label.config(text="← 항목을 먼저\n   선택하세요",
                                     foreground="gray")

    def _get_checked_days(self) -> list[str]:
        return [day for day in DAY_ORDER if self._day_vars[day].get()]

    def _on_day_checkbox_toggled(self):
        """Checkbox toggled -> save days to selected entry immediately."""
        if self._updating_checkboxes:
            return
        days = self._get_checked_days()

        ann_entry = self._find_selected_ann_entry()
        if ann_entry:
            self._sched.update_schedule_entry(
                ann_entry["time"], ann_entry["announcement"], days=days)
            self._refresh_keep_selection("ann", ann_entry["time"], ann_entry["announcement"])
            return

        bgm_entry = self._find_selected_bgm_entry()
        if bgm_entry:
            self._sched.update_bgm_schedule_entry(bgm_entry["time"], days=days)
            self._refresh_keep_selection("bgm", bgm_entry["time"])
            return

    def _quick_weekdays(self):
        self._set_checkboxes(["monday", "tuesday", "wednesday", "thursday", "friday"])
        self._on_day_checkbox_toggled()

    def _quick_weekend(self):
        self._set_checkboxes(["saturday", "sunday"])
        self._on_day_checkbox_toggled()

    def _quick_all(self):
        self._set_checkboxes(DAY_ORDER)
        self._on_day_checkbox_toggled()

    # --- Refresh ---

    def _refresh_schedule(self):
        self._clear_checkboxes()

        for item in self._tree.get_children():
            self._tree.delete(item)
        for item in self._sched.scheduled_items:
            action_label = BGM_ACTION_LABELS.get(item.get("bgm_action") or "", "")
            self._tree.insert("", tk.END, values=(
                item["time"],
                item["label"],
                days_to_short(item.get("days", [])),
                item["announcement"],
                action_label,
            ))

        for item in self._bgm_tree.get_children():
            self._bgm_tree.delete(item)
        for entry in self._sched.bgm_scheduled_items:
            track_count = len(entry.get("playlist", []))
            self._bgm_tree.insert("", tk.END, values=(
                entry["time"],
                entry.get("label", ""),
                days_to_short(entry.get("days", [])),
                f"{track_count}곡",
            ))

        next_ann = self._sched.get_next_announcement()
        if next_ann:
            self._next_label.config(
                text=f"다음 방송: {next_ann['label']} ({next_ann['time']})")
        else:
            self._next_label.config(text="오늘 남은 방송 없음")

    def _refresh_keep_selection(self, entry_type: str, time_str: str,
                                 announcement: str = None):
        for item in self._tree.get_children():
            self._tree.delete(item)
        reselect_ann = None
        for item in self._sched.scheduled_items:
            action_label = BGM_ACTION_LABELS.get(item.get("bgm_action") or "", "")
            iid = self._tree.insert("", tk.END, values=(
                item["time"],
                item["label"],
                days_to_short(item.get("days", [])),
                item["announcement"],
                action_label,
            ))
            if entry_type == "ann" and item["time"] == time_str and item["announcement"] == announcement:
                reselect_ann = iid

        for item in self._bgm_tree.get_children():
            self._bgm_tree.delete(item)
        reselect_bgm = None
        for entry in self._sched.bgm_scheduled_items:
            track_count = len(entry.get("playlist", []))
            iid = self._bgm_tree.insert("", tk.END, values=(
                entry["time"],
                entry.get("label", ""),
                days_to_short(entry.get("days", [])),
                f"{track_count}곡",
            ))
            if entry_type == "bgm" and entry["time"] == time_str:
                reselect_bgm = iid

        if reselect_ann:
            self._tree.selection_set(reselect_ann)
            self._tree.focus(reselect_ann)
        elif reselect_bgm:
            self._bgm_tree.selection_set(reselect_bgm)
            self._bgm_tree.focus(reselect_bgm)

    # --- Announcement CRUD ---

    def _add_entry(self):
        dialog = tk.Toplevel(self._parent)
        dialog.title("스케줄 추가")
        dialog.geometry("380x440")
        dialog.transient(self._parent.winfo_toplevel())
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=15)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="시간 (HH:MM):").pack(anchor=tk.W)
        time_row = ttk.Frame(frame)
        time_row.pack(fill=tk.X, pady=(0, 10))
        hour_var = tk.StringVar(value="09")
        min_var = tk.StringVar(value="00")
        ttk.Spinbox(time_row, from_=0, to=23, width=4, format="%02.0f",
                     textvariable=hour_var).pack(side=tk.LEFT)
        ttk.Label(time_row, text=" : ").pack(side=tk.LEFT)
        ttk.Spinbox(time_row, from_=0, to=59, width=4, format="%02.0f",
                     textvariable=min_var).pack(side=tk.LEFT)

        # Days checkboxes
        ttk.Label(frame, text="요일:").pack(anchor=tk.W)
        day_frame = ttk.Frame(frame)
        day_frame.pack(fill=tk.X, pady=(0, 5))
        dlg_days = {}
        for day in DAY_ORDER:
            var = tk.BooleanVar(value=day in ["monday","tuesday","wednesday","thursday","friday"])
            ttk.Checkbutton(day_frame, text=DAY_SHORT[day], variable=var).pack(side=tk.LEFT, padx=2)
            dlg_days[day] = var

        quick = ttk.Frame(frame)
        quick.pack(fill=tk.X, pady=(0, 10))
        ttk.Button(quick, text="평일", command=lambda: [
            dlg_days[d].set(d in ["monday","tuesday","wednesday","thursday","friday"]) for d in DAY_ORDER
        ]).pack(side=tk.LEFT, padx=(0, 3))
        ttk.Button(quick, text="주말", command=lambda: [
            dlg_days[d].set(d in ["saturday","sunday"]) for d in DAY_ORDER
        ]).pack(side=tk.LEFT, padx=(0, 3))
        ttk.Button(quick, text="전체", command=lambda: [
            dlg_days[d].set(True) for d in DAY_ORDER
        ]).pack(side=tk.LEFT)

        ttk.Label(frame, text="카테고리:").pack(anchor=tk.W)
        cat_var = tk.StringVar()
        categories = list(self._ann.categories.keys())
        cat_combo = ttk.Combobox(frame, textvariable=cat_var, values=categories, state="readonly")
        cat_combo.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(frame, text="안내방송:").pack(anchor=tk.W)
        item_var = tk.StringVar()
        item_combo = ttk.Combobox(frame, textvariable=item_var, state="readonly")
        item_combo.pack(fill=tk.X, pady=(0, 10))

        def update_items(*args):
            cat = cat_var.get()
            items = self._ann.get_items(cat)
            item_combo["values"] = [f"{i['id']} - {i['label']}" for i in items]
            if items:
                item_combo.current(0)

        cat_var.trace_add("write", update_items)
        if categories:
            cat_combo.current(0)
            update_items()

        ttk.Label(frame, text="표시 이름:").pack(anchor=tk.W)
        label_var = tk.StringVar()
        ttk.Entry(frame, textvariable=label_var).pack(fill=tk.X, pady=(0, 10))

        ttk.Label(frame, text="BGM 동작:").pack(anchor=tk.W)
        bgm_action_var = tk.StringVar(value="없음")
        ttk.Combobox(frame, textvariable=bgm_action_var,
                      values=BGM_ACTION_OPTIONS,
                      state="readonly", width=15).pack(anchor=tk.W, pady=(0, 10))

        def save():
            days = [d for d in DAY_ORDER if dlg_days[d].get()]
            if not days:
                messagebox.showwarning("요일 선택", "최소 하나의 요일을 선택해주세요.")
                return
            h = hour_var.get().zfill(2)
            m = min_var.get().zfill(2)
            time_str = f"{h}:{m}"
            cat = cat_var.get()
            item_sel = item_var.get()
            if not item_sel:
                messagebox.showwarning("선택 필요", "안내방송을 선택해주세요.")
                return
            item_id = item_sel.split(" - ")[0]
            announcement = f"{cat}/{item_id}"
            label = label_var.get() or item_sel.split(" - ")[-1]
            bgm_action = BGM_ACTION_MAP.get(bgm_action_var.get(), "")
            self._sched.add_schedule_entry(time_str, announcement, label, days,
                                            bgm_action=bgm_action or None)
            dialog.destroy()
            self._refresh_schedule()

        ttk.Button(frame, text="저장", command=save).pack(pady=(5, 0))

    def _remove_entry(self):
        selected = self._tree.selection()
        if not selected:
            messagebox.showinfo("선택 필요", "삭제할 항목을 선택해주세요.")
            return
        values = self._tree.item(selected[0], "values")
        time_str, label = values[0], values[1]
        announcement = values[3]
        if messagebox.askyesno("삭제 확인", f"'{label}' ({time_str}) 을(를) 삭제하시겠습니까?"):
            self._sched.remove_schedule_entry(time_str, announcement)
            self._refresh_schedule()

    def _edit_entry(self):
        """Edit an existing announcement schedule entry."""
        entry = self._find_selected_ann_entry()
        if not entry:
            messagebox.showinfo("선택 필요", "편집할 항목을 선택해주세요.")
            return

        old_time = entry["time"]
        old_announcement = entry["announcement"]

        dialog = tk.Toplevel(self._parent)
        dialog.title("스케줄 편집")
        dialog.geometry("380x300")
        dialog.transient(self._parent.winfo_toplevel())
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=15)
        frame.pack(fill=tk.BOTH, expand=True)

        # Time
        ttk.Label(frame, text="시간 (HH:MM):").pack(anchor=tk.W)
        time_row = ttk.Frame(frame)
        time_row.pack(fill=tk.X, pady=(0, 10))
        parts = old_time.split(":")
        hour_var = tk.StringVar(value=parts[0])
        min_var = tk.StringVar(value=parts[1])
        ttk.Spinbox(time_row, from_=0, to=23, width=4, format="%02.0f",
                     textvariable=hour_var).pack(side=tk.LEFT)
        ttk.Label(time_row, text=" : ").pack(side=tk.LEFT)
        ttk.Spinbox(time_row, from_=0, to=59, width=4, format="%02.0f",
                     textvariable=min_var).pack(side=tk.LEFT)

        # Label
        ttk.Label(frame, text="표시 이름:").pack(anchor=tk.W)
        label_var = tk.StringVar(value=entry.get("label", ""))
        ttk.Entry(frame, textvariable=label_var).pack(fill=tk.X, pady=(0, 10))

        # Announcement (read-only display)
        ttk.Label(frame, text="방송 종류:").pack(anchor=tk.W)
        ann_label = ttk.Label(frame, text=old_announcement, foreground="gray")
        ann_label.pack(anchor=tk.W, pady=(0, 10))

        # BGM action
        ttk.Label(frame, text="BGM 동작:").pack(anchor=tk.W)
        current_action = BGM_ACTION_REVERSE.get(entry.get("bgm_action") or "", "없음")
        bgm_action_var = tk.StringVar(value=current_action)
        ttk.Combobox(frame, textvariable=bgm_action_var,
                      values=BGM_ACTION_OPTIONS,
                      state="readonly", width=15).pack(anchor=tk.W, pady=(0, 10))

        def save():
            h = hour_var.get().zfill(2)
            m = min_var.get().zfill(2)
            new_time = f"{h}:{m}"
            new_label = label_var.get() or entry.get("label", "")
            bgm_action = BGM_ACTION_MAP.get(bgm_action_var.get(), "")

            if new_time != old_time:
                # Time changed: remove old, add new
                self._sched.remove_schedule_entry(old_time, old_announcement)
                self._sched.add_schedule_entry(
                    new_time, old_announcement, new_label,
                    entry.get("days", []),
                    bgm_action=bgm_action or None)
            else:
                self._sched.update_schedule_entry(
                    old_time, old_announcement,
                    label=new_label, bgm_action=bgm_action)
            dialog.destroy()
            self._refresh_schedule()

        ttk.Button(frame, text="저장", command=save).pack(pady=(5, 0))

    # --- BGM Schedule CRUD ---

    def _add_bgm_entry(self):
        self._open_bgm_dialog()

    def _edit_bgm_entry(self):
        selected = self._bgm_tree.selection()
        if not selected:
            messagebox.showinfo("선택 필요", "편집할 BGM 항목을 선택해주세요.")
            return
        values = self._bgm_tree.item(selected[0], "values")
        time_str = values[0]
        for item in self._sched.bgm_scheduled_items:
            if item["time"] == time_str:
                self._open_bgm_dialog(existing=item)
                return

    def _open_bgm_dialog(self, existing: dict = None):
        is_edit = existing is not None
        dialog = tk.Toplevel(self._parent)
        dialog.title("BGM 스케줄 편집" if is_edit else "BGM 스케줄 추가")
        dialog.geometry("500x520")
        dialog.transient(self._parent.winfo_toplevel())
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=15)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="시간 (HH:MM):").pack(anchor=tk.W)
        time_row = ttk.Frame(frame)
        time_row.pack(fill=tk.X, pady=(0, 10))
        if is_edit:
            parts = existing["time"].split(":")
            h_val, m_val = parts[0], parts[1]
        else:
            h_val, m_val = "09", "00"
        hour_var = tk.StringVar(value=h_val)
        min_var = tk.StringVar(value=m_val)
        hour_spin = ttk.Spinbox(time_row, from_=0, to=23, width=4, format="%02.0f",
                                textvariable=hour_var)
        hour_spin.pack(side=tk.LEFT)
        ttk.Label(time_row, text=" : ").pack(side=tk.LEFT)
        min_spin = ttk.Spinbox(time_row, from_=0, to=59, width=4, format="%02.0f",
                               textvariable=min_var)
        min_spin.pack(side=tk.LEFT)
        if is_edit:
            hour_spin.config(state="disabled")
            min_spin.config(state="disabled")

        # Days checkboxes
        ttk.Label(frame, text="요일:").pack(anchor=tk.W)
        day_frame = ttk.Frame(frame)
        day_frame.pack(fill=tk.X, pady=(0, 5))
        dlg_days = {}
        init_days = existing.get("days", []) if is_edit else \
            ["monday","tuesday","wednesday","thursday","friday"]
        for day in DAY_ORDER:
            var = tk.BooleanVar(value=day in init_days)
            ttk.Checkbutton(day_frame, text=DAY_SHORT[day], variable=var).pack(side=tk.LEFT, padx=2)
            dlg_days[day] = var

        quick = ttk.Frame(frame)
        quick.pack(fill=tk.X, pady=(0, 10))
        ttk.Button(quick, text="평일", command=lambda: [
            dlg_days[d].set(d in ["monday","tuesday","wednesday","thursday","friday"]) for d in DAY_ORDER
        ]).pack(side=tk.LEFT, padx=(0, 3))
        ttk.Button(quick, text="주말", command=lambda: [
            dlg_days[d].set(d in ["saturday","sunday"]) for d in DAY_ORDER
        ]).pack(side=tk.LEFT, padx=(0, 3))
        ttk.Button(quick, text="전체", command=lambda: [
            dlg_days[d].set(True) for d in DAY_ORDER
        ]).pack(side=tk.LEFT)

        ttk.Label(frame, text="재생목록 이름:").pack(anchor=tk.W)
        label_var = tk.StringVar(value=existing.get("label", "") if is_edit else "")
        ttk.Entry(frame, textvariable=label_var).pack(fill=tk.X, pady=(0, 10))

        ttk.Label(frame, text="YouTube URL (한 줄에 하나씩):").pack(anchor=tk.W)
        url_text = tk.Text(frame, height=10, font=("", 11))
        url_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        def _do_paste():
            try:
                clipboard = dialog.clipboard_get()
                try:
                    url_text.delete(tk.SEL_FIRST, tk.SEL_LAST)
                except tk.TclError:
                    pass
                url_text.insert(tk.INSERT, clipboard)
            except tk.TclError:
                pass

        def _paste_event(event):
            _do_paste()
            return "break"

        url_text.bind("<Command-v>", _paste_event)
        url_text.bind("<Command-V>", _paste_event)
        url_text.bind("<Control-v>", _paste_event)
        url_text.bind("<Control-V>", _paste_event)
        url_text.bind("<<Paste>>", _paste_event)

        def _show_menu(event):
            menu = tk.Menu(dialog, tearoff=0)
            menu.add_command(label="붙여넣기", command=_do_paste)
            menu.add_command(label="전체 선택", command=lambda: (
                url_text.tag_add(tk.SEL, "1.0", tk.END),
            ))
            menu.tk_popup(event.x_root, event.y_root)

        url_text.bind("<Button-2>", _show_menu)
        url_text.bind("<Button-3>", _show_menu)

        if is_edit:
            for url in existing.get("playlist", []):
                url_text.insert(tk.END, url + "\n")

        def save():
            days = [d for d in DAY_ORDER if dlg_days[d].get()]
            if not days:
                messagebox.showwarning("요일 선택", "최소 하나의 요일을 선택해주세요.")
                return
            h = hour_var.get().zfill(2)
            m = min_var.get().zfill(2)
            time_str = f"{h}:{m}"
            label = label_var.get().strip() or f"BGM {time_str}"
            urls = [line.strip() for line in url_text.get("1.0", tk.END).splitlines()
                    if line.strip() and line.strip().startswith("http")]
            if not urls:
                messagebox.showwarning("URL 필요", "최소 하나의 YouTube URL을 입력해주세요.")
                return
            if is_edit:
                self._sched.update_bgm_schedule_entry(
                    time_str, label=label, playlist=urls, days=days)
            else:
                self._sched.add_bgm_schedule_entry(time_str, label, urls, days)
            dialog.destroy()
            self._refresh_schedule()

        ttk.Button(frame, text="저장", command=save).pack(pady=(5, 0))

    def _remove_bgm_entry(self):
        selected = self._bgm_tree.selection()
        if not selected:
            messagebox.showinfo("선택 필요", "삭제할 BGM 항목을 선택해주세요.")
            return
        values = self._bgm_tree.item(selected[0], "values")
        time_str, label, _days, _ = values
        if messagebox.askyesno("삭제 확인",
                               f"'{label}' ({time_str}) BGM 스케줄을 삭제하시겠습니까?"):
            self._sched.remove_bgm_schedule_entry(time_str)
            self._refresh_schedule()

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

DAY_ORDER = ["monday", "tuesday", "wednesday", "thursday",
             "friday", "saturday", "sunday"]


class ScheduleEditor:
    """Schedule editing tab."""

    def __init__(self, parent: ttk.Frame, schedule_manager, announcement_manager):
        self._parent = parent
        self._sched = schedule_manager
        self._ann = announcement_manager
        self._selected_day = "monday"
        self._build_ui()
        self._refresh_schedule()

    def _build_ui(self):
        main = ttk.Frame(self._parent, padding=10)
        main.pack(fill=tk.BOTH, expand=True)

        # Left: Day selector
        left = ttk.Frame(main, width=120)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        left.pack_propagate(False)

        ttk.Label(left, text="요일 선택", font=("", 11, "bold")).pack(pady=(0, 5))

        self._day_buttons = {}
        for day in DAY_ORDER:
            btn = ttk.Button(
                left, text=DAY_LABELS[day],
                command=lambda d=day: self._select_day(d),
            )
            btn.pack(fill=tk.X, pady=1)
            self._day_buttons[day] = btn

        # Right: Schedule table
        right = ttk.Frame(main)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._day_label = ttk.Label(right, text="월요일 스케줄",
                                     font=("", 13, "bold"))
        self._day_label.pack(anchor=tk.W, pady=(0, 8))

        # Treeview
        cols = ("time", "label", "announcement")
        self._tree = ttk.Treeview(right, columns=cols, show="headings", height=12)
        self._tree.heading("time", text="시간")
        self._tree.heading("label", text="방송 이름")
        self._tree.heading("announcement", text="카테고리/ID")
        self._tree.column("time", width=70, anchor=tk.CENTER)
        self._tree.column("label", width=200)
        self._tree.column("announcement", width=150)
        self._tree.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(right, orient=tk.VERTICAL, command=self._tree.yview)
        self._tree.configure(yscrollcommand=scrollbar.set)

        # Button row
        btn_row = ttk.Frame(right)
        btn_row.pack(fill=tk.X, pady=(8, 0))

        ttk.Button(btn_row, text="추가", command=self._add_entry).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_row, text="삭제", command=self._remove_entry).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_row, text="새로고침", command=self._refresh_schedule).pack(side=tk.RIGHT)

        # Next announcement info
        self._next_label = ttk.Label(right, text="", foreground="blue")
        self._next_label.pack(anchor=tk.W, pady=(5, 0))

    def _select_day(self, day: str):
        self._selected_day = day
        self._day_label.config(text=f"{DAY_LABELS[day]} 스케줄")
        self._refresh_schedule()

    def _refresh_schedule(self):
        for item in self._tree.get_children():
            self._tree.delete(item)

        items = self._sched.scheduled_items
        for item in items:
            if item["day"] == self._selected_day:
                self._tree.insert("", tk.END, values=(
                    item["time"],
                    item["label"],
                    item["announcement"],
                ))

        next_ann = self._sched.get_next_announcement()
        if next_ann:
            self._next_label.config(
                text=f"다음 방송: {next_ann['label']} ({next_ann['time']})"
            )
        else:
            self._next_label.config(text="오늘 남은 방송 없음")

    def _add_entry(self):
        dialog = tk.Toplevel(self._parent)
        dialog.title("스케줄 추가")
        dialog.geometry("350x280")
        dialog.transient(self._parent.winfo_toplevel())
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=15)
        frame.pack(fill=tk.BOTH, expand=True)

        # Time
        ttk.Label(frame, text="시간 (HH:MM):").pack(anchor=tk.W)
        time_row = ttk.Frame(frame)
        time_row.pack(fill=tk.X, pady=(0, 10))
        hour_var = tk.StringVar(value="09")
        min_var = tk.StringVar(value="00")
        hour_spin = ttk.Spinbox(time_row, from_=0, to=23, width=4, format="%02.0f",
                                textvariable=hour_var)
        hour_spin.pack(side=tk.LEFT)
        ttk.Label(time_row, text=" : ").pack(side=tk.LEFT)
        min_spin = ttk.Spinbox(time_row, from_=0, to=59, width=4, format="%02.0f",
                               textvariable=min_var)
        min_spin.pack(side=tk.LEFT)

        # Category
        ttk.Label(frame, text="카테고리:").pack(anchor=tk.W)
        cat_var = tk.StringVar()
        categories = list(self._ann.categories.keys())
        cat_combo = ttk.Combobox(frame, textvariable=cat_var, values=categories, state="readonly")
        cat_combo.pack(fill=tk.X, pady=(0, 10))
        if categories:
            cat_combo.current(0)

        # Announcement item
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
            update_items()

        # Label
        ttk.Label(frame, text="표시 이름:").pack(anchor=tk.W)
        label_var = tk.StringVar()
        ttk.Entry(frame, textvariable=label_var).pack(fill=tk.X, pady=(0, 10))

        def save():
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

            self._sched.add_schedule_entry(self._selected_day, time_str, announcement, label)
            dialog.destroy()
            self._refresh_schedule()

        ttk.Button(frame, text="저장", command=save).pack(pady=(5, 0))

    def _remove_entry(self):
        selected = self._tree.selection()
        if not selected:
            messagebox.showinfo("선택 필요", "삭제할 항목을 선택해주세요.")
            return

        values = self._tree.item(selected[0], "values")
        time_str, label, announcement = values

        if messagebox.askyesno("삭제 확인", f"'{label}' ({time_str}) 을(를) 삭제하시겠습니까?"):
            self._sched.remove_schedule_entry(self._selected_day, time_str, announcement)
            self._refresh_schedule()

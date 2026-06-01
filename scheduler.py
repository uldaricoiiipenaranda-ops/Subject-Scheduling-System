import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

DB_NAME = "schedule.db"
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]


def _to_24h(t_str):
    return datetime.strptime(t_str, "%I:%M %p").strftime("%H:%M")


def _to_12h(t_str):
    return datetime.strptime(t_str, "%H:%M").strftime("%I:%M %p")


class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DB_NAME)
        self.cur = self.conn.cursor()
        self.cur.execute("""
            CREATE TABLE IF NOT EXISTS subjects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                teacher TEXT NOT NULL,
                day TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                room TEXT NOT NULL
            )
        """)
        self.conn.commit()

    def fetch_all(self, search=""):
        if search:
            self.cur.execute("""
                SELECT * FROM subjects
                WHERE id LIKE ? OR code LIKE ? OR name LIKE ? OR teacher LIKE ? OR room LIKE ?
                ORDER BY day, start_time
            """, (f"%{search}%", f"%{search}%", f"%{search}%", f"%{search}%", f"%{search}%"))
        else:
            self.cur.execute("SELECT * FROM subjects ORDER BY day, start_time")
        return self.cur.fetchall()

    def fetch_by_id(self, sid):
        self.cur.execute("SELECT * FROM subjects WHERE id = ?", (sid,))
        return self.cur.fetchone()

    def add(self, code, name, teacher, day, start_time, end_time, room):
        self.cur.execute("""
            INSERT INTO subjects (code, name, teacher, day, start_time, end_time, room)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (code, name, teacher, day, start_time, end_time, room))
        self.conn.commit()

    def update(self, sid, code, name, teacher, day, start_time, end_time, room):
        self.cur.execute("""
            UPDATE subjects
            SET code=?, name=?, teacher=?, day=?, start_time=?, end_time=?, room=?
            WHERE id=?
        """, (code, name, teacher, day, start_time, end_time, room, sid))
        self.conn.commit()

    def delete(self, sid):
        self.cur.execute("DELETE FROM subjects WHERE id = ?", (sid,))
        self.conn.commit()

    def time_conflict(self, day, start_time, end_time, exclude_id=None):
        self.cur.execute("""
            SELECT * FROM subjects
            WHERE day = ? AND id != ?
              AND start_time < ? AND end_time > ?
        """, (day, exclude_id or -1, end_time, start_time))
        return self.cur.fetchone()

    def __del__(self):
        if hasattr(self, 'conn'):
            self.conn.close()


class SchedulerApp:
    def __init__(self, root):
        self.db = Database()
        self.root = root
        self.root.title("Subject Scheduler")
        self.root.geometry("900x600")
        self.root.minsize(800, 500)

        self.selected_id = None
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.refresh_table())

        self._build_ui()
        self.refresh_table()

    def _build_ui(self):
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        top = ttk.Frame(main_frame)
        top.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(top, text="Search:").pack(side=tk.LEFT, padx=(0, 5))
        ttk.Entry(top, textvariable=self.search_var, width=40).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(top, text="Clear", command=lambda: self.search_var.set("")).pack(side=tk.LEFT)

        ttk.Button(top, text="+ Add Subject", command=self.open_add).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(top, text="Edit", command=self.open_edit).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(top, text="Delete", command=self.delete_subject).pack(side=tk.RIGHT, padx=(5, 0))

        columns = ("id", "code", "name", "teacher", "day", "start_time", "end_time", "room")
        self.tree = ttk.Treeview(main_frame, columns=columns, show="headings", selectmode="browse")
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        col_widths = {"id": 40, "code": 100, "name": 180, "teacher": 150, "day": 100, "start_time": 90, "end_time": 90, "room": 100}
        headings = {"id": "ID", "code": "Code", "name": "Subject", "teacher": "Teacher", "day": "Day", "start_time": "Start", "end_time": "End", "room": "Room"}

        for col in columns:
            self.tree.heading(col, text=headings[col], command=lambda c=col: self._sort_by(c))
            self.tree.column(col, width=col_widths[col], minwidth=col_widths[col])

        scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self.tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.sort_col = None
        self.sort_asc = True

        status = ttk.Frame(main_frame)
        status.pack(fill=tk.X, pady=(5, 0))
        self.status_label = ttk.Label(status, text="")
        self.status_label.pack(side=tk.LEFT)

    def _on_select(self, _):
        sel = self.tree.selection()
        if sel:
            self.selected_id = self.tree.item(sel[0])["values"][0]
        else:
            self.selected_id = None

    def _sort_by(self, col):
        if self.sort_col == col:
            self.sort_asc = not self.sort_asc
        else:
            self.sort_col = col
            self.sort_asc = True

        rows = [(self.tree.set(child, col), child) for child in self.tree.get_children("")]
        rows.sort(reverse=not self.sort_asc)
        for idx, (_, child) in enumerate(rows):
            self.tree.move(child, "", idx)

    def refresh_table(self):
        for row in self.tree.get_children():
            self.tree.delete(row)

        search = self.search_var.get().strip()
        records = self.db.fetch_all(search)

        for r in records:
            r = list(r)
            r[5] = _to_12h(r[5])
            r[6] = _to_12h(r[6])
            self.tree.insert("", tk.END, values=tuple(r))

        self.status_label.config(text=f"{len(records)} subject(s)")
        self.selected_id = None

    def open_add(self):
        AddEditDialog(self.root, self.db, self.refresh_table, "Add Subject")

    def open_edit(self):
        if not self.selected_id:
            messagebox.showwarning("No Selection", "Please select a subject to edit.")
            return
        record = self.db.fetch_by_id(self.selected_id)
        if record:
            AddEditDialog(self.root, self.db, self.refresh_table, "Edit Subject", record)

    def delete_subject(self):
        if not self.selected_id:
            messagebox.showwarning("No Selection", "Please select a subject to delete.")
            return
        if messagebox.askyesno("Confirm Delete", "Delete this subject from the schedule?"):
            self.db.delete(self.selected_id)
            self.refresh_table()


class AddEditDialog(tk.Toplevel):
    def __init__(self, parent, db, refresh_cb, title, record=None):
        super().__init__(parent)
        self.db = db
        self.refresh_cb = refresh_cb
        self.record = record
        self.title(title)
        self.geometry("500x380")
        self.resizable(False, False)
        self.grab_set()

        frame = ttk.Frame(self, padding=15)
        frame.pack(fill=tk.BOTH, expand=True)

        fields = [
            ("Subject Code:", "code"),
            ("Subject Name:", "name"),
            ("Teacher:", "teacher"),
            ("Day:", "day"),
            ("Start Time (HH:MM AM/PM):", "start_time"),
            ("End Time (HH:MM AM/PM):", "end_time"),
            ("Room:", "room"),
        ]

        self.entries = {}
        vals = record if record else [None, "", "", "", "", "", "", ""]

        for i, (label, key) in enumerate(fields):
            ttk.Label(frame, text=label).grid(row=i, column=0, sticky=tk.W, pady=4, padx=(0, 10))
            if key == "day":
                self.entries[key] = ttk.Combobox(frame, values=DAYS, state="readonly", width=27)
                self.entries[key].grid(row=i, column=1, sticky=tk.EW, pady=4)
            else:
                self.entries[key] = ttk.Entry(frame, width=30)
                self.entries[key].grid(row=i, column=1, sticky=tk.EW, pady=4)
            self.entries[key].insert(0, vals[i + 1] if vals[i + 1] else "")

        frame.columnconfigure(1, weight=1)

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=len(fields), column=0, columnspan=2, pady=(15, 0))
        ttk.Button(btn_frame, text="Save", command=self.save).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side=tk.LEFT)

    def save(self):
        data = {}
        for key in ("code", "name", "teacher", "day", "start_time", "end_time", "room"):
            data[key] = self.entries[key].get().strip()

        missing = [k for k, v in data.items() if not v]
        if missing:
            messagebox.showerror("Validation Error", f"Fields cannot be empty: {', '.join(missing)}")
            return

        for tf in ("start_time", "end_time"):
            try:
                datetime.strptime(data[tf], "%I:%M %p")
            except ValueError:
                messagebox.showerror("Validation Error", f"{tf.replace('_', ' ').title()} must be HH:MM AM/PM (12h)")
                return

        data["start_time"] = _to_24h(data["start_time"])
        data["end_time"] = _to_24h(data["end_time"])

        if data["start_time"] >= data["end_time"]:
            messagebox.showerror("Validation Error", "End time must be after start time.")
            return

        exclude = self.record[0] if self.record else None
        if self.db.time_conflict(data["day"], data["start_time"], data["end_time"], exclude):
            messagebox.showerror("Conflict", "Time slot conflicts with another subject on the same day.")
            return

        try:
            if self.record:
                self.db.update(self.record[0], data["code"], data["name"], data["teacher"],
                               data["day"], data["start_time"], data["end_time"], data["room"])
            else:
                self.db.add(data["code"], data["name"], data["teacher"],
                            data["day"], data["start_time"], data["end_time"], data["room"])
        except sqlite3.IntegrityError:
            messagebox.showerror("Error", f"Subject code '{data['code']}' already exists.")
            return

        self.refresh_cb()
        self.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    SchedulerApp(root)
    root.mainloop()

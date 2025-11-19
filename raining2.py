"""
student_planner.py

Student Planner with:
- Add / Edit / Delete tasks
- Alarm system (background thread) with popup and optional sound
- Calendar date picker and time dropdowns
- Database schema upgrade (safe add columns)
- Recurrence support (none, daily, weekly) with C-A behavior:
    When a recurring task triggers, DO NOT mark the original completed.
    Instead, auto-create the next occurrence (same fields) with completed=0.
- Auto-clean old tasks: manual button to remove tasks older than 30 days.
  Optional daily silent auto-clean can be enabled by setting AUTO_CLEAN_DAILY = True.
"""

import tkinter as tk
from tkinter import messagebox, ttk
from tkcalendar import DateEntry
import sqlite3
import threading
import datetime
import time
import os

# Optional sound: uses playsound if available
try:
    from playsound import playsound
    HAS_PLAYSOUND = True
except Exception:
    HAS_PLAYSOUND = False

DB_FILE = "student_planner.db"
ALARM_SOUND = "alarm.mp3"  # Optional: put an alarm.mp3 next to this file

# Auto-clean scheduler toggle:
# If True -> the app will run a silent auto-clean every 24 hours (no confirmation).
# If False -> only manual cleaning via button will be available.
AUTO_CLEAN_DAILY = False

# ---------------------------
# Database helpers & migration
# ---------------------------
def get_conn():
    # allow thread-safe access from background thread
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def ensure_schema(conn):
    """
    Creates tasks table if not exists and ensures newer columns exist.
    Columns: id, title, date, time, description, completed, recurrence
    recurrence values: 'none', 'daily', 'weekly'
    """
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY,
        title TEXT NOT NULL,
        date TEXT NOT NULL,     -- YYYY-MM-DD
        time TEXT NOT NULL,     -- HH:MM (24h)
        description TEXT DEFAULT '',
        completed INTEGER DEFAULT 0,
        recurrence TEXT DEFAULT 'none'
    )
    """)
    conn.commit()

    # Ensure columns exist (in case of older DB). Use PRAGMA
    cur.execute("PRAGMA table_info(tasks)")
    cols = [r["name"] for r in cur.fetchall()]
    if "description" not in cols:
        cur.execute("ALTER TABLE tasks ADD COLUMN description TEXT DEFAULT ''")
    if "completed" not in cols:
        cur.execute("ALTER TABLE/tasks ADD COLUMN completed INTEGER DEFAULT 0") if False else None
        # The above line is intentionally inert for safety on odd DBs; ensure again using safer method:
        cur.execute("PRAGMA table_info(tasks)")
        cols = [r["name"] for r in cur.fetchall()]
        if "completed" not in cols:
            cur.execute("ALTER TABLE tasks ADD COLUMN completed INTEGER DEFAULT 0")
    if "recurrence" not in cols:
        cur.execute("ALTER TABLE tasks ADD COLUMN recurrence TEXT DEFAULT 'none'")
    conn.commit()

# ---------------------------
# Alarm checker (background)
# ---------------------------
def compute_next_date(date_str, recurrence):
    """
    date_str: 'YYYY-MM-DD'
    recurrence: 'daily' or 'weekly'
    returns next date string 'YYYY-MM-DD'
    """
    d = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
    if recurrence == "daily":
        nd = d + datetime.timedelta(days=1)
    elif recurrence == "weekly":
        nd = d + datetime.timedelta(weeks=1)
    else:
        return None
    return nd.strftime("%Y-%m-%d")

def alarm_checker(stop_event, conn, main_root_ref):
    """
    Background thread: checks every 20-30 seconds for tasks scheduled
    for the current minute (date + time) and triggers popup/sound.
    For recurring tasks (daily/weekly) it will auto-create a future task
    with the same fields and completed=0, but will NOT mark the original completed.
    """
    cur = conn.cursor()
    # Keep a small in-memory set of already-handled task (id, minute-key) to avoid duplicates within same minute
    handled_this_minute = set()
    while not stop_event.is_set():
        now = datetime.datetime.now()
        current_key = now.strftime("%Y-%m-%d %H:%M")
        try:
            cur.execute("SELECT * FROM tasks WHERE date || ' ' || time = ?", (current_key,))
            matches = cur.fetchall()
            for m in matches:
                task_id = m["id"]
                unique = (task_id, current_key)
                if unique in handled_this_minute:
                    continue  # already processed in this minute
                handled_this_minute.add(unique)

                title = m["title"]
                desc = m["description"]
                recurrence = m["recurrence"] if "recurrence" in m.keys() else "none"

                # Play sound if available (non-blocking)
                try:
                    if HAS_PLAYSOUND and os.path.exists(ALARM_SOUND):
                        threading.Thread(target=playsound, args=(ALARM_SOUND,), daemon=True).start()
                    else:
                        # fallback bell in console (may not be audible)
                        print("\a", end="")
                except Exception as e:
                    print("Sound error:", e)

                # Schedule popup on main thread (tkinter must be used on main thread)
                if main_root_ref and main_root_ref.winfo_exists():
                    try:
                        main_root_ref.after(100, lambda t=title, d=desc: messagebox.showinfo("Reminder", f"{t}\n\n{d}"))
                    except Exception:
                        pass

                # If recurrence is daily/weekly, create next occurrence (C-A)
                if recurrence and recurrence.lower() in ("daily", "weekly"):
                    next_date = compute_next_date(m["date"], recurrence.lower())
                    if next_date:
                        # Avoid duplicating the next occurrence if it already exists (same title/date/time/recurrence)
                        cur.execute("""
                            SELECT COUNT(*) as c FROM tasks
                            WHERE title=? AND date=? AND time=? AND recurrence=?
                        """, (m["title"], next_date, m["time"], recurrence))
                        count_row = cur.fetchone()
                        count = count_row["c"] if count_row else 0
                        if count == 0:
                            # Insert new task with completed = 0 (do NOT copy completed flag)
                            cur.execute("""
                                INSERT INTO tasks (title, date, time, description, completed, recurrence)
                                VALUES (?, ?, ?, ?, 0, ?)
                            """, (m["title"], next_date, m["time"], m["description"], recurrence))
                            conn.commit()
        except Exception as e:
            print("Alarm checker error:", e)

        # Clear handled set every 70 seconds (keeps it bounded; ensures per-minute processing)
        # Sleep loop with short sleeps to be responsive to stop_event
        for i in range(7):
            if stop_event.is_set():
                break
            time.sleep(10)
        handled_this_minute.clear()

# ---------------------------
# GUI Application
# ---------------------------
class PlannerApp:
    instance = None  # store single instance for thread scheduling popups

    def __init__(self, root):
        PlannerApp.instance = self
        self.root = root
        self.root.title("Student Planner")
        self.root.geometry("760x520")
        self.conn = get_conn()
        ensure_schema(self.conn)
        self.cursor = self.conn.cursor()

        self.stop_event = threading.Event()

        self._build_ui()

        # Start alarm thread
        self.alarm_thread = threading.Thread(target=alarm_checker, args=(self.stop_event, self.conn, self.root), daemon=True)
        self.alarm_thread.start()

        # Refresh upcoming panel periodically
        self.root.after(2000, self.refresh_upcoming_panel)

        # Optional daily silent auto-clean
        if AUTO_CLEAN_DAILY:
            # wait a few seconds before first silent run
            self.root.after(5000, self.schedule_daily_autoclean)

    def _build_ui(self):
        main = ttk.Frame(self.root, padding=10)
        main.pack(fill="both", expand=True)

        # Left side: Add task
        left = ttk.Frame(main)
        left.pack(side="left", fill="both", expand=True, padx=(0,10))

        ttk.Label(left, text="Add / Schedule Task", font=("TkDefaultFont", 12, "bold")).pack(anchor="w")

        # Title
        ttk.Label(left, text="Title:").pack(anchor="w", pady=(8,0))
        self.title_entry = ttk.Entry(left, width=44)
        self.title_entry.pack(anchor="w", pady=2)

        # Description
        ttk.Label(left, text="Description (optional):").pack(anchor="w", pady=(6,0))
        self.desc_entry = ttk.Entry(left, width=44)
        self.desc_entry.pack(anchor="w", pady=2)

        # Date
        ttk.Label(left, text="Date:").pack(anchor="w", pady=(6,0))
        self.date_entry = DateEntry(left, date_pattern="yyyy-mm-dd", width=18)
        self.date_entry.pack(anchor="w", pady=2)

        # Time pickers
        ttk.Label(left, text="Time (24h):").pack(anchor="w", pady=(6,0))
        tf = ttk.Frame(left)
        tf.pack(anchor="w", pady=2)
        self.hour_var = tk.StringVar(value=datetime.datetime.now().strftime("%H"))
        self.min_var = tk.StringVar(value=datetime.datetime.now().strftime("%M"))
        ttk.OptionMenu(tf, self.hour_var, self.hour_var.get(), *[f"{i:02d}" for i in range(24)]).pack(side="left")
        ttk.Label(tf, text=" : ").pack(side="left")
        ttk.OptionMenu(tf, self.min_var, self.min_var.get(), *[f"{i:02d}" for i in range(60)]).pack(side="left")

        # Recurrence dropdown
        ttk.Label(left, text="Recurrence:").pack(anchor="w", pady=(6,0))
        self.recur_var = tk.StringVar(value="none")
        ttk.OptionMenu(left, self.recur_var, self.recur_var.get(), "none", "daily", "weekly").pack(anchor="w", pady=2)

        # Buttons
        btn_frame = ttk.Frame(left)
        btn_frame.pack(anchor="w", pady=10)
        ttk.Button(btn_frame, text="Add Task", command=self.add_task).pack(side="left")
        ttk.Button(btn_frame, text="Show All Tasks", command=self.show_tasks).pack(side="left", padx=6)
        ttk.Button(btn_frame, text="Export Tasks (CSV)", command=self.export_tasks_csv).pack(side="left", padx=6)
        ttk.Button(btn_frame, text="Clean Old Tasks (30 days)", command=self.auto_clean_old_tasks).pack(side="left", padx=6)

        # Right side: upcoming tasks and controls
        right = ttk.Frame(main, width=300)
        right.pack(side="left", fill="y", padx=(10,0))

        ttk.Label(right, text="Upcoming Tasks", font=("TkDefaultFont", 12, "bold")).pack(anchor="w")
        self.up_container = ttk.Frame(right)
        self.up_container.pack(anchor="w", pady=6, fill="both")

        ttk.Button(right, text="Quit", command=self.on_quit).pack(side="bottom", pady=10, anchor="s")

        # initial refresh
        self.refresh_upcoming_panel()

    # ----------------------
    # CRUD operations
    # ----------------------
    def add_task(self):
        title = self.title_entry.get().strip()
        desc = self.desc_entry.get().strip()
        date = self.date_entry.get().strip()
        time_str = f"{self.hour_var.get()}:{self.min_var.get()}"
        recurrence = self.recur_var.get()

        if not title:
            messagebox.showwarning("Missing", "Please enter a title.")
            return

        # validate date/time
        try:
            datetime.datetime.strptime(f"{date} {time_str}", "%Y-%m-%d %H:%M")
        except ValueError:
            messagebox.showwarning("Invalid", "Please select a valid date and time.")
            return

        self.cursor.execute("""
            INSERT INTO tasks (title, date, time, description, completed, recurrence)
            VALUES (?, ?, ?, ?, 0, ?)
        """, (title, date, time_str, desc, recurrence))
        self.conn.commit()
        messagebox.showinfo("Added", f"Task '{title}' added for {date} {time_str}.")
        self.title_entry.delete(0, tk.END)
        self.desc_entry.delete(0, tk.END)
        self.refresh_upcoming_panel()

    def delete_task(self, task_id):
        confirm = messagebox.askyesno("Delete", "Delete this task?")
        if not confirm:
            return
        self.cursor.execute("DELETE FROM tasks WHERE id=?", (task_id,))
        self.conn.commit()
        self.refresh_upcoming_panel()

    def update_task(self, task_id, new_title, new_date, new_time, new_desc, new_recurrence):
        # validate
        try:
            datetime.datetime.strptime(f"{new_date} {new_time}", "%Y-%m-%d %H:%M")
        except ValueError:
            messagebox.showwarning("Invalid", "Please choose a valid date & time.")
            return
        self.cursor.execute("""
            UPDATE tasks SET title=?, date=?, time=?, description=?, recurrence=?
            WHERE id=?
        """, (new_title, new_date, new_time, new_desc, new_recurrence, task_id))
        self.conn.commit()
        self.refresh_upcoming_panel()

    # ----------------------
    # Task viewer & editor
    # ----------------------
    def show_tasks(self):
        win = tk.Toplevel(self.root)
        win.title("All Tasks")
        win.geometry("820x440")

        cont = ttk.Frame(win, padding=8)
        cont.pack(fill="both", expand=True)

        cols = ("id", "title", "date", "time", "description", "recurrence", "completed")
        tree = ttk.Treeview(cont, columns=cols, show="headings", selectmode="browse")
        for c in cols:
            tree.heading(c, text=c.capitalize())
        tree.column("id", width=40, anchor="center")
        tree.column("title", width=240)
        tree.column("date", width=90, anchor="center")
        tree.column("time", width=70, anchor="center")
        tree.column("description", width=220)
        tree.column("recurrence", width=80, anchor="center")
        tree.column("completed", width=70, anchor="center")

        tree.pack(fill="both", expand=True, side="left")

        vsb = ttk.Scrollbar(cont, orient="vertical", command=tree.yview)
        tree.configure(yscroll=vsb.set)
        vsb.pack(side="left", fill="y")

        btns = ttk.Frame(win, padding=6)
        btns.pack(fill="x", side="bottom")

        def load():
            for r in tree.get_children():
                tree.delete(r)
            self.cursor.execute("SELECT * FROM tasks ORDER BY date, time")
            for row in self.cursor.fetchall():
                tree.insert("", "end", values=(row["id"], row["title"], row["date"], row["time"], row["description"], row["recurrence"], "Yes" if row["completed"] else "No"))

        def on_edit():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("Select", "Select a task to edit.")
                return
            item = tree.item(sel[0])["values"]
            tid = item[0]
            self.open_edit_window(tid, parent=win, refresh_cb=load)

        def on_delete():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("Select", "Select a task to delete.")
                return
            item = tree.item(sel[0])["values"]
            tid = item[0]
            self.delete_task(tid)
            load()

        ttk.Button(btns, text="Edit Selected", command=on_edit).pack(side="left", padx=4)
        ttk.Button(btns, text="Delete Selected", command=on_delete).pack(side="left", padx=4)
        ttk.Button(btns, text="Refresh", command=load).pack(side="left", padx=4)
        ttk.Button(btns, text="Close", command=win.destroy).pack(side="right", padx=4)

        load()

    def open_edit_window(self, task_id, parent=None, refresh_cb=None):
        self.cursor.execute("SELECT * FROM tasks WHERE id=?", (task_id,))
        row = self.cursor.fetchone()
        if not row:
            messagebox.showerror("Not found", "Task not found.")
            return

        ew = tk.Toplevel(self.root)
        ew.title("Edit Task")
        ew.geometry("470x360")
        frm = ttk.Frame(ew, padding=8)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="Title:").pack(anchor="w")
        title_e = ttk.Entry(frm, width=58)
        title_e.insert(0, row["title"])
        title_e.pack(anchor="w", pady=2)

        ttk.Label(frm, text="Description:").pack(anchor="w")
        desc_e = ttk.Entry(frm, width=58)
        desc_e.insert(0, row["description"])
        desc_e.pack(anchor="w", pady=2)

        ttk.Label(frm, text="Date:").pack(anchor="w", pady=(6,0))
        date_e = DateEntry(frm, date_pattern="yyyy-mm-dd", width=18)
        date_e.set_date(row["date"])
        date_e.pack(anchor="w", pady=2)

        ttk.Label(frm, text="Time:").pack(anchor="w", pady=(6,0))
        tf = ttk.Frame(frm)
        tf.pack(anchor="w")
        old_h, old_m = row["time"].split(":")
        hvar = tk.StringVar(value=old_h)
        mvar = tk.StringVar(value=old_m)
        ttk.OptionMenu(tf, hvar, hvar.get(), *[f"{i:02d}" for i in range(24)]).pack(side="left")
        ttk.Label(tf, text=" : ").pack(side="left")
        ttk.OptionMenu(tf, mvar, mvar.get(), *[f"{i:02d}" for i in range(60)]).pack(side="left")

        ttk.Label(frm, text="Recurrence:").pack(anchor="w", pady=(6,0))
        rvar = tk.StringVar(value=row["recurrence"] if row["recurrence"] else "none")
        ttk.OptionMenu(frm, rvar, rvar.get(), "none", "daily", "weekly").pack(anchor="w", pady=2)

        def save_and_close():
            new_title = title_e.get().strip()
            new_desc = desc_e.get().strip()
            new_date = date_e.get().strip()
            new_time = f"{hvar.get()}:{mvar.get()}"
            new_recur = rvar.get()
            if not new_title:
                messagebox.showwarning("Missing", "Title required.")
                return
            self.update_task(task_id, new_title, new_date, new_time, new_desc, new_recur)
            if refresh_cb:
                refresh_cb()
            messagebox.showinfo("Saved", "Task updated.")
            ew.destroy()

        ttk.Button(frm, text="Save Changes", command=save_and_close).pack(pady=10)
        ttk.Button(frm, text="Cancel", command=ew.destroy).pack()

    # ----------------------
    # Upcoming tasks panel
    # ----------------------
    def refresh_upcoming_panel(self):
        for c in self.up_container.winfo_children():
            c.destroy()

        now_key = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        self.cursor.execute("""
            SELECT * FROM tasks WHERE (date || ' ' || time) >= ? ORDER BY date, time LIMIT 6
        """, (now_key,))
        rows = self.cursor.fetchall()

        if not rows:
            ttk.Label(self.up_container, text="No upcoming tasks.").pack(anchor="w")
        else:
            for r in rows:
                txt = f"{r['date']} {r['time']}  -  {r['title']}"
                fr = ttk.Frame(self.up_container)
                fr.pack(anchor="w", pady=2, fill="x")
                ttk.Label(fr, text=txt, wraplength=320).pack(side="left", anchor="w")
                ttk.Button(fr, text="Edit", width=6, command=lambda tid=r["id"]: self.open_edit_window(tid, refresh_cb=self.refresh_upcoming_panel)).pack(side="left", padx=6)
                ttk.Button(fr, text="Del", width=6, command=lambda tid=r["id"]: (self.delete_task(tid), self.refresh_upcoming_panel())).pack(side="left")

        # schedule next refresh
        if not self.stop_event.is_set():
            self.root.after(60000, self.refresh_upcoming_panel)  # every 60 seconds

    # ----------------------
    # Auto-clean old tasks (manual)
    # ----------------------
    def auto_clean_old_tasks(self):
        """Remove tasks older than 30 days (based on date only). Requires user confirmation."""
        today = datetime.date.today()
        cutoff_date = today - datetime.timedelta(days=30)
        cutoff_str = cutoff_date.strftime("%Y-%m-%d")

        self.cursor.execute("SELECT COUNT(*) as c FROM tasks WHERE date < ?", (cutoff_str,))
        count_row = self.cursor.fetchone()
        count = count_row["c"] if count_row else 0

        if count == 0:
            messagebox.showinfo("Clean Old Tasks", "No old tasks to clean.")
            return

        confirm = messagebox.askyesno(
            "Clean Old Tasks",
            f"{count} tasks older than 30 days (before {cutoff_str}) will be permanently removed.\n\nContinue?"
        )
        if not confirm:
            return

        self.cursor.execute("DELETE FROM tasks WHERE date < ?", (cutoff_str,))
        self.conn.commit()
        messagebox.showinfo("Cleaned", f"Removed {count} old tasks older than 30 days.")
        self.refresh_upcoming_panel()

    def _auto_clean_old_tasks_silent(self):
        """Silent cleanup without confirmation (used by scheduled auto-clean)."""
        today = datetime.date.today()
        cutoff_date = today - datetime.timedelta(days=30)
        cutoff_str = cutoff_date.strftime("%Y-%m-%d")
        self.cursor.execute("DELETE FROM tasks WHERE date < ?", (cutoff_str,))
        self.conn.commit()
        # refresh UI if visible
        self.refresh_upcoming_panel()

    def schedule_daily_autoclean(self):
        """Run silent auto-clean now and schedule next run 24 hours later."""
        try:
            self._auto_clean_old_tasks_silent()
        except Exception as e:
            print("Auto-clean error:", e)
        # schedule next silent clean in 24 hours (milliseconds)
        if not self.stop_event.is_set():
            self.root.after(86400000, self.schedule_daily_autoclean)  # 24 * 60 * 60 * 1000

    # ----------------------
    # Export tasks CSV
    # ----------------------
    def export_tasks_csv(self):
        import csv
        filename = f"tasks_export_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        self.cursor.execute("SELECT * FROM tasks ORDER BY date, time")
        rows = self.cursor.fetchall()
        if not rows:
            messagebox.showinfo("Export", "No tasks to export.")
            return
        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "title", "date", "time", "description", "recurrence", "completed"])
            for r in rows:
                writer.writerow([r["id"], r["title"], r["date"], r["time"], r["description"], r["recurrence"], r["completed"]])
        messagebox.showinfo("Exported", f"Tasks exported to {filename}")

    # ----------------------
    # Cleanup
    # ----------------------
    def on_quit(self):
        if messagebox.askokcancel("Quit", "Exit the planner?"):
            self.stop_event.set()
            try:
                if self.alarm_thread.is_alive():
                    self.alarm_thread.join(timeout=1)
            except Exception:
                pass
            try:
                self.conn.close()
            except Exception:
                pass
            self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = PlannerApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_quit)
    root.mainloop()

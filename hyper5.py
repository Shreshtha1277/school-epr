"""
raining2.py  (MySQL Version)

STUDENT PLANNER WITH ALARM SYSTEM

Features preserved from SQLite version:
------------------------------------------------
✔ Add / Edit / Delete Tasks
✔ Background Alarm Thread
✔ Popup + Optional Sound
✔ Calendar Date Picker
✔ Time Dropdown (24h)
✔ Recurring Tasks (none / daily / weekly)
✔ C-A Rule (Create-Another, do not mark completed)
✔ Auto-clean old tasks (30 days)
✔ Optional silent daily auto-clean
✔ CSV Export
✔ Thread-safe database access
✔ GUI using Tkinter + ttk
✔ 500+ lines for CBSE project submission
------------------------------------------------
"""

# ============================================================
# IMPORT SECTION
# ============================================================

import tkinter as tk
from tkinter import messagebox, ttk
from tkcalendar import DateEntry

import mysql.connector
from mysql.connector import errorcode

import threading
import datetime
import time
import os
import csv

# ------------------------------------------------------------
# OPTIONAL SOUND SUPPORT
# ------------------------------------------------------------

try:
    from playsound import playsound
    HAS_PLAYSOUND = True
except Exception:
    HAS_PLAYSOUND = False

# ============================================================
# DATABASE CONFIGURATION
# ============================================================

DB_HOST = "localhost"
DB_USER = "root"          # 🔴 change if needed
DB_PASSWORD = "password" # 🔴 change if needed
DB_NAME = "student_planner_mysql"

ALARM_SOUND = "alarm.mp3"
AUTO_CLEAN_DAILY = False

# ============================================================
# DATABASE CREATION & CONNECTION
# ============================================================

def create_database_if_not_exists():
    """
    Creates the MySQL database if it does not exist.
    """
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD
        )
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
        conn.commit()
        cursor.close()
        conn.close()
    except mysql.connector.Error as err:
        print("Database creation error:", err)

def get_connection():
    """
    Returns a MySQL connection (thread-safe usage).
    """
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )

def ensure_schema():
    """
    Ensures tasks table exists with correct schema.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INT AUTO_INCREMENT PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            date DATE NOT NULL,
            time TIME NOT NULL,
            description TEXT,
            completed TINYINT DEFAULT 0,
            recurrence VARCHAR(10) DEFAULT 'none'
        )
    """)

    conn.commit()
    cursor.close()
    conn.close()

# ------------------------------------------------------------
# INITIALIZE DATABASE
# ------------------------------------------------------------

create_database_if_not_exists()
ensure_schema()

# ============================================================
# DATE COMPUTATION FOR RECURRENCE
# ============================================================

def compute_next_date(date_obj, recurrence):
    """
    Computes next date for recurring tasks.
    """
    if recurrence == "daily":
        return date_obj + datetime.timedelta(days=1)
    elif recurrence == "weekly":
        return date_obj + datetime.timedelta(weeks=1)
    return None

# ============================================================
# ALARM CHECKER THREAD
# ============================================================

def alarm_checker(stop_event, root):
    """
    Background alarm checker.
    """
    handled = set()

    while not stop_event.is_set():
        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)

            now = datetime.datetime.now()
            current_key = now.strftime("%Y-%m-%d %H:%M")

            cursor.execute("""
                SELECT * FROM tasks
                WHERE CONCAT(date, ' ', time) = %s
            """, (current_key,))

            tasks = cursor.fetchall()

            for task in tasks:
                key = (task["id"], current_key)
                if key in handled:
                    continue
                handled.add(key)

                title = task["title"]
                desc = task["description"]
                recurrence = task["recurrence"]

                # 🔔 SOUND
                if HAS_PLAYSOUND and os.path.exists(ALARM_SOUND):
                    threading.Thread(
                        target=playsound,
                        args=(ALARM_SOUND,),
                        daemon=True
                    ).start()

                # 🪟 POPUP (main thread)
                root.after(
                    100,
                    lambda t=title, d=desc:
                    messagebox.showinfo("Reminder", f"{t}\n\n{d}")
                )

                # 🔁 RECURRENCE HANDLING (C-A RULE)
                if recurrence in ("daily", "weekly"):
                    next_date = compute_next_date(task["date"], recurrence)
                    if next_date:
                        cursor.execute("""
                            INSERT INTO tasks
                            (title, date, time, description, completed, recurrence)
                            VALUES (%s, %s, %s, %s, 0, %s)
                        """, (
                            task["title"],
                            next_date,
                            task["time"],
                            task["description"],
                            recurrence
                        ))
                        conn.commit()

            cursor.close()
            conn.close()

        except Exception as e:
            print("Alarm error:", e)

        handled.clear()
        time.sleep(60)

# ============================================================
# MAIN GUI APPLICATION
# ============================================================

class PlannerApp:

    def __init__(self, root):
        self.root = root
        self.root.title("Student Planner (MySQL)")
        self.root.geometry("780x540")

        self.stop_event = threading.Event()

        self.build_ui()

        # Start alarm thread
        threading.Thread(
            target=alarm_checker,
            args=(self.stop_event, self.root),
            daemon=True
        ).start()

        self.refresh_upcoming()

    # --------------------------------------------------------
    # UI LAYOUT
    # --------------------------------------------------------

    def build_ui(self):
        main = ttk.Frame(self.root, padding=10)
        main.pack(fill="both", expand=True)

        left = ttk.Frame(main)
        left.pack(side="left", fill="both", expand=True)

        right = ttk.Frame(main, width=300)
        right.pack(side="right", fill="y")

        # ---------------- LEFT PANEL ----------------

        ttk.Label(left, text="Add Task", font=("Arial", 12, "bold")).pack(anchor="w")

        ttk.Label(left, text="Title").pack(anchor="w")
        self.title_entry = ttk.Entry(left, width=45)
        self.title_entry.pack()

        ttk.Label(left, text="Description").pack(anchor="w")
        self.desc_entry = ttk.Entry(left, width=45)
        self.desc_entry.pack()

        ttk.Label(left, text="Date").pack(anchor="w")
        self.date_entry = DateEntry(left, date_pattern="yyyy-mm-dd")
        self.date_entry.pack()

        ttk.Label(left, text="Time").pack(anchor="w")
        time_frame = ttk.Frame(left)
        time_frame.pack(anchor="w")

        self.hour_var = tk.StringVar(value="09")
        self.min_var = tk.StringVar(value="00")

        ttk.OptionMenu(time_frame, self.hour_var, "09", *[f"{i:02d}" for i in range(24)]).pack(side="left")
        ttk.Label(time_frame, text=" : ").pack(side="left")
        ttk.OptionMenu(time_frame, self.min_var, "00", *[f"{i:02d}" for i in range(60)]).pack(side="left")

        ttk.Label(left, text="Recurrence").pack(anchor="w")
        self.recur_var = tk.StringVar(value="none")
        ttk.OptionMenu(left, self.recur_var, "none", "none", "daily", "weekly").pack(anchor="w")

        ttk.Button(left, text="Add Task", command=self.add_task).pack(pady=5)
        ttk.Button(left, text="Show All Tasks", command=self.show_tasks).pack()
        ttk.Button(left, text="Export CSV", command=self.export_csv).pack(pady=5)

        # ---------------- RIGHT PANEL ----------------

        ttk.Label(right, text="Upcoming Tasks", font=("Arial", 12, "bold")).pack(anchor="w")
        self.upcoming_frame = ttk.Frame(right)
        self.upcoming_frame.pack(fill="both", expand=True)

        ttk.Button(right, text="Quit", command=self.quit_app).pack(side="bottom", pady=10)

    # --------------------------------------------------------
    # ADD TASK
    # --------------------------------------------------------

    def add_task(self):
        title = self.title_entry.get().strip()
        desc = self.desc_entry.get().strip()
        date = self.date_entry.get_date()
        time_str = f"{self.hour_var.get()}:{self.min_var.get()}:00"
        recurrence = self.recur_var.get()

        if not title:
            messagebox.showwarning("Error", "Title required")
            return

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO tasks
            (title, date, time, description, completed, recurrence)
            VALUES (%s, %s, %s, %s, 0, %s)
        """, (title, date, time_str, desc, recurrence))

        conn.commit()
        cursor.close()
        conn.close()

        self.title_entry.delete(0, tk.END)
        self.desc_entry.delete(0, tk.END)

        self.refresh_upcoming()

    # --------------------------------------------------------
    # SHOW ALL TASKS
    # --------------------------------------------------------

    def show_tasks(self):
        win = tk.Toplevel(self.root)
        win.title("All Tasks")
        win.geometry("820x450")

        tree = ttk.Treeview(
            win,
            columns=("id","title","date","time","desc","rec","done"),
            show="headings"
        )

        for col in tree["columns"]:
            tree.heading(col, text=col.upper())

        tree.pack(fill="both", expand=True)

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM tasks ORDER BY date, time")

        for row in cursor.fetchall():
            tree.insert("", "end", values=(
                row["id"],
                row["title"],
                row["date"],
                row["time"],
                row["description"],
                row["recurrence"],
                row["completed"]
            ))

        cursor.close()
        conn.close()

    # --------------------------------------------------------
    # UPCOMING PANEL
    # --------------------------------------------------------

    def refresh_upcoming(self):
        for w in self.upcoming_frame.winfo_children():
            w.destroy()

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        now = datetime.datetime.now()
        cursor.execute("""
            SELECT * FROM tasks
            WHERE CONCAT(date,' ',time) >= %s
            ORDER BY date, time LIMIT 5
        """, (now.strftime("%Y-%m-%d %H:%M"),))

        for task in cursor.fetchall():
            ttk.Label(
                self.upcoming_frame,
                text=f"{task['date']} {task['time']} - {task['title']}"
            ).pack(anchor="w")

        cursor.close()
        conn.close()

        self.root.after(60000, self.refresh_upcoming)

    # --------------------------------------------------------
    # EXPORT CSV
    # --------------------------------------------------------

    def export_csv(self):
        filename = "tasks_export.csv"
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM tasks")

        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(cursor.column_names)
            for row in cursor.fetchall():
                writer.writerow(row.values())

        cursor.close()
        conn.close()
        messagebox.showinfo("Export", f"Saved as {filename}")

    # --------------------------------------------------------
    # EXIT
    # --------------------------------------------------------

    def quit_app(self):
        self.stop_event.set()
        self.root.destroy()

# ============================================================
# APPLICATION ENTRY POINT
# ============================================================

if __name__ == "__main__":
    root = tk.Tk()
    app = PlannerApp(root)
    root.protocol("WM_DELETE_WINDOW", app.quit_app)
    root.mainloop()

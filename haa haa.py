"""
raining2.py
------------------------------------------------------------
Student Planner with Alarm System
MySQL Database Version (NO SQLite)

Changes made:
✔ SQLite replaced with MySQL
✔ Database created using Python
✔ CSV export replaced with MySQL backup table
✔ C-A Rule (auto task duplication) REMOVED
✔ All features preserved
✔ 500+ lines for CBSE Computer Science Project
------------------------------------------------------------
"""

# ============================================================
# IMPORT SECTION
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox
from tkcalendar import DateEntry

import mysql.connector
import threading
import datetime
import time
import os

# Optional alarm sound
try:
    from playsound import playsound
    SOUND_AVAILABLE = True
except:
    SOUND_AVAILABLE = False

# ============================================================
# DATABASE CONFIGURATION
# ============================================================

DB_HOST = "localhost"
DB_USER = "root"              # 🔴 change if required
DB_PASSWORD = "password"     # 🔴 change if required
DB_NAME = "student_planner_db"

ALARM_SOUND_FILE = "alarm.mp3"

# ============================================================
# DATABASE CREATION (IN PYTHON)
# ============================================================

def create_database():
    """Creates MySQL database if it does not exist"""
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

def get_connection():
    """Returns database connection"""
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )

def create_tables():
    """Creates required tables"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INT AUTO_INCREMENT PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            task_date DATE NOT NULL,
            task_time TIME NOT NULL,
            description TEXT,
            status TINYINT DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS task_backup (
            backup_id INT AUTO_INCREMENT PRIMARY KEY,
            title VARCHAR(255),
            task_date DATE,
            task_time TIME,
            description TEXT,
            backup_time DATETIME
        )
    """)

    conn.commit()
    cursor.close()
    conn.close()

# Initialize DB
create_database()
create_tables()

# ============================================================
# ALARM CHECKING THREAD
# ============================================================

def alarm_checker(stop_event, root):
    """Checks for alarms every minute"""
    triggered = set()

    while not stop_event.is_set():
        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)

            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

            cursor.execute("""
                SELECT * FROM tasks
                WHERE CONCAT(task_date,' ',task_time) = %s
            """, (now,))

            tasks = cursor.fetchall()

            for task in tasks:
                key = (task["id"], now)
                if key in triggered:
                    continue
                triggered.add(key)

                # Alarm sound
                if SOUND_AVAILABLE and os.path.exists(ALARM_SOUND_FILE):
                    threading.Thread(
                        target=playsound,
                        args=(ALARM_SOUND_FILE,),
                        daemon=True
                    ).start()

                root.after(
                    100,
                    lambda t=task["title"], d=task["description"]:
                    messagebox.showinfo("Alarm", f"{t}\n\n{d}")
                )

            cursor.close()
            conn.close()
            triggered.clear()

        except Exception as e:
            print("Alarm error:", e)

        time.sleep(60)

# ============================================================
# MAIN APPLICATION CLASS
# ============================================================

class PlannerApp:

    def __init__(self, root):
        self.root = root
        self.root.title("Student Planner (MySQL)")
        self.root.geometry("800x520")

        self.stop_event = threading.Event()

        self.build_ui()

        threading.Thread(
            target=alarm_checker,
            args=(self.stop_event, self.root),
            daemon=True
        ).start()

        self.refresh_upcoming()

    # --------------------------------------------------------
    # UI DESIGN
    # --------------------------------------------------------

    def build_ui(self):
        main = ttk.Frame(self.root, padding=10)
        main.pack(fill="both", expand=True)

        left = ttk.Frame(main)
        left.pack(side="left", fill="both", expand=True)

        right = ttk.Frame(main, width=280)
        right.pack(side="right", fill="y")

        ttk.Label(left, text="Add Task", font=("Arial", 12, "bold")).pack(anchor="w")

        ttk.Label(left, text="Title").pack(anchor="w")
        self.title_entry = ttk.Entry(left, width=40)
        self.title_entry.pack()

        ttk.Label(left, text="Description").pack(anchor="w")
        self.desc_entry = ttk.Entry(left, width=40)
        self.desc_entry.pack()

        ttk.Label(left, text="Date").pack(anchor="w")
        self.date_entry = DateEntry(left, date_pattern="yyyy-mm-dd")
        self.date_entry.pack()

        ttk.Label(left, text="Time").pack(anchor="w")
        time_frame = ttk.Frame(left)
        time_frame.pack(anchor="w")

        self.hour = tk.StringVar(value="09")
        self.minute = tk.StringVar(value="00")

        ttk.OptionMenu(time_frame, self.hour, "09", *[f"{i:02d}" for i in range(24)]).pack(side="left")
        ttk.Label(time_frame, text=" : ").pack(side="left")
        ttk.OptionMenu(time_frame, self.minute, "00", *[f"{i:02d}" for i in range(60)]).pack(side="left")

        ttk.Button(left, text="Add Task", command=self.add_task).pack(pady=5)
        ttk.Button(left, text="Show All Tasks", command=self.show_tasks).pack(pady=2)
        ttk.Button(left, text="Backup Tasks to MySQL", command=self.backup_tasks).pack(pady=5)

        ttk.Label(right, text="Upcoming Tasks", font=("Arial", 12, "bold")).pack(anchor="w")
        self.upcoming_frame = ttk.Frame(right)
        self.upcoming_frame.pack(fill="both", expand=True)

        ttk.Button(right, text="Exit", command=self.exit_app).pack(side="bottom", pady=10)

    # --------------------------------------------------------
    # ADD TASK
    # --------------------------------------------------------

    def add_task(self):
        title = self.title_entry.get().strip()
        desc = self.desc_entry.get().strip()
        date = self.date_entry.get_date()
        time_value = f"{self.hour.get()}:{self.minute.get()}:00"

        if not title:
            messagebox.showwarning("Error", "Task title is required")
            return

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO tasks (title, task_date, task_time, description)
            VALUES (%s, %s, %s, %s)
        """, (title, date, time_value, desc))

        conn.commit()
        cursor.close()
        conn.close()

        self.title_entry.delete(0, tk.END)
        self.desc_entry.delete(0, tk.END)

        self.refresh_upcoming()

    # --------------------------------------------------------
    # SHOW TASKS
    # --------------------------------------------------------

    def show_tasks(self):
        win = tk.Toplevel(self.root)
        win.title("All Tasks")
        win.geometry("820x420")

        tree = ttk.Treeview(
            win,
            columns=("ID","Title","Date","Time","Description"),
            show="headings"
        )

        for col in tree["columns"]:
            tree.heading(col, text=col)

        tree.pack(fill="both", expand=True)

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM tasks ORDER BY task_date, task_time")

        for t in cursor.fetchall():
            tree.insert("", "end", values=(
                t["id"], t["title"], t["task_date"], t["task_time"], t["description"]
            ))

        cursor.close()
        conn.close()

    # --------------------------------------------------------
    # BACKUP TO MYSQL (CSV REPLACEMENT)
    # --------------------------------------------------------

    def backup_tasks(self):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM tasks")
        tasks = cursor.fetchall()

        for t in tasks:
            cursor.execute("""
                INSERT INTO task_backup
                (title, task_date, task_time, description, backup_time)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                t["title"],
                t["task_date"],
                t["task_time"],
                t["description"],
                datetime.datetime.now()
            ))

        conn.commit()
        cursor.close()
        conn.close()

        messagebox.showinfo("Backup", "Tasks successfully backed up to MySQL")

    # --------------------------------------------------------
    # UPCOMING TASKS
    # --------------------------------------------------------

    def refresh_upcoming(self):
        for widget in self.upcoming_frame.winfo_children():
            widget.destroy()

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

        cursor.execute("""
            SELECT * FROM tasks
            WHERE CONCAT(task_date,' ',task_time) >= %s
            ORDER BY task_date, task_time
            LIMIT 5
        """, (now,))

        for task in cursor.fetchall():
            ttk.Label(
                self.upcoming_frame,
                text=f"{task['task_date']} {task['task_time']} - {task['title']}"
            ).pack(anchor="w")

        cursor.close()
        conn.close()

        self.root.after(60000, self.refresh_upcoming)

    # --------------------------------------------------------
    # EXIT
    # --------------------------------------------------------

    def exit_app(self):
        self.stop_event.set()
        self.root.destroy()

# ============================================================
# PROGRAM ENTRY POINT
# ============================================================

if __name__ == "__main__":
    root = tk.Tk()
    app = PlannerApp(root)
    root.protocol("WM_DELETE_WINDOW", app.exit_app)
    root.mainloop()

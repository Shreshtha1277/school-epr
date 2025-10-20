import tkinter as tk
from tkinter import messagebox
import sqlite3
import datetime
import threading
from playsound import playsound

# Create DB if not exists
conn = sqlite3.connect("planner.db")
cursor = conn.cursor()
#cursor.execute("DROP TABLE IF EXISTS tasks")


cursor.execute("""

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY,
    title TEXT,
    date TEXT,
    time TEXT,
    note TEXT
)
""")
conn.commit()

def play_alarm(title):
    messagebox.showinfo("Alarm", f"Reminder: {title}")
    threading.Thread(target=lambda: playsound("new-notification-on-your-device-138695.mp3"), daemon=True).start()

def check_alarms():
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    cursor.execute("SELECT * FROM tasks WHERE date || ' ' || time = ?", (now,))
    for task in cursor.fetchall():
        play_alarm(task[1])
    root.after(60000, check_alarms)  # check every 60 seconds

class PlannerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Alarm Planner")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)  # handle window close

        tk.Label(root, text="Task Title:").pack()
        self.title_entry = tk.Entry(root)
        self.title_entry.pack()

        tk.Label(root, text="Date (YYYY-MM-DD):").pack()
        self.date_entry = tk.Entry(root)
        self.date_entry.pack()

        tk.Label(root, text="Time (HH:MM 24h):").pack()
        self.time_entry = tk.Entry(root)
        self.time_entry.pack()

        tk.Label(root, text="Note:").pack()
        self.note_entry = tk.Entry(root)
        self.note_entry.pack()

        tk.Button(root, text="Add Task", command=self.add_task).pack(pady=5)
        tk.Button(root, text="Show Tasks", command=self.show_tasks).pack(pady=5)

        check_alarms()  # start periodic check

    def add_task(self):
        title = self.title_entry.get().strip()
        date = self.date_entry.get().strip()
        time_ = self.time_entry.get().strip()
        note = self.note_entry.get().strip()

        if not all([title, date, time_, note]):
            messagebox.showwarning("Input Error", "All fields are required!")
            return

        # Validate date format
        try:
            datetime.datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            messagebox.showwarning("Input Error", "Date format is incorrect! Use YYYY-MM-DD.")
            return

        # Validate time format
        try:
            datetime.datetime.strptime(time_, "%H:%M")
        except ValueError:
            messagebox.showwarning("Input Error", "Time format is incorrect! Use HH:MM (24h).")
            return

        # Insert with correct column ordering
        cursor.execute("INSERT INTO tasks (title, date, time, note) VALUES (?, ?, ?, ?)",
                       (title, date, time_, note))
        conn.commit()
        messagebox.showinfo("Success", "Task Added!")

        # Clear fields (optional)
        self.title_entry.delete(0, tk.END)
        self.date_entry.delete(0, tk.END)
        self.time_entry.delete(0, tk.END)
        self.note_entry.delete(0, tk.END)

    def show_tasks(self):
        win = tk.Toplevel(self.root)
        win.title("Scheduled Tasks")
        cursor.execute("SELECT * FROM tasks ORDER BY date, time")
        for task in cursor.fetchall():
            # task fields: id, title, date, time, note
            tk.Label(win, text=f"{task[1]} - {task[2]} {task[3]} | {task[4]}").pack()

    def on_close(self):
        # Close DB connection cleanly, then exit
        conn.close()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = PlannerApp(root)
    root.mainloop()

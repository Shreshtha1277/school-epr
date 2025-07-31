# working but run only on chatgpt also chatgpt can't form GUI .
# you can't delet the added task
# no alarm system
# poor graphic 
import tkinter as tk
from tkinter import messagebox
import sqlite3
import threading
import datetime
import time
from playsound import playsound

# Create DB if not exists
conn = sqlite3.connect("planner.db")
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY,
    title TEXT,
               
    date TEXT,
    time TEXT
)
""")
conn.commit()

# Alarm checking function
def alarm_checker():
    while True:
        now = datetime.datetime.now()
        current_time = now.strftime("%Y-%m-%d %H:%M")
        cursor.execute("SELECT * FROM tasks WHERE date || ' ' || time = ?", (current_time,))
        tasks = cursor.fetchall()
        for task in tasks:
            messagebox.showinfo("Alarm", f"Reminder: {task[1]}")
            playsound("alarm.mp3")  # make sure 'alarm.mp3' is in your directory
        time.sleep(60)  # check every minute

# GUI application
class PlannerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Alarm Planner")

        # Title entry
        tk.Label(root, text="Task Title:").pack()
        self.title_entry = tk.Entry(root)
        self.title_entry.pack()

        # Date and time entry
        tk.Label(root, text="Date (YYYY-MM-DD):").pack()
        self.date_entry = tk.Entry(root)
        self.date_entry.pack()

        tk.Label(root, text="Time (HH:MM in 24h):").pack()
        self.time_entry = tk.Entry(root)
        self.time_entry.pack()

        # Buttons
        tk.Button(root, text="Add Task", command=self.add_task).pack(pady=5)
        tk.Button(root, text="Show Tasks", command=self.show_tasks).pack(pady=5)

    def add_task(self):
        title = self.title_entry.get()
        date = self.date_entry.get()
        time_ = self.time_entry.get()

        if not title or not date or not time_:
            messagebox.showwarning("Input Error", "All fields are required!")
            return

        cursor.execute("INSERT INTO tasks (title, date, time) VALUES (?, ?, ?)", (title, date, time_))
        conn.commit()
        messagebox.showinfo("Success", "Task Added!")

    def show_tasks(self):
        tasks_win = tk.Toplevel(self.root)
        tasks_win.title("Scheduled Tasks")

        cursor.execute("SELECT * FROM tasks ORDER BY date, time")
        tasks = cursor.fetchall()

        for task in tasks:
            tk.Label(tasks_win, text=f"{task[1]} - {task[2]} {task[3]}").pack()

# Start alarm thread
threading.Thread(target=alarm_checker, daemon=True).start()

# Run app
root = tk.Tk()
app = PlannerApp(root)
root.mainloop()

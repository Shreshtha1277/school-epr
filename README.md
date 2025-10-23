<html>
<head>
<title>school-epr</title>
</head>
<body>
<h3>The planner in your summer.py file has these main features:</h3>
<p>✅ Current Features</p>
<p>GUI with Tkinter –
Provides a simple graphical interface for adding and viewing tasks.</p>
<p>SQLite Database Integration –
Stores tasks (title, date, and time) in a local database (planner.db).</p>
<p>Task Scheduling –
Allows users to add tasks with a specific date and time.</p>
<p>Alarm System –
A background thread continuously checks the current time and triggers an alarm when it matches a stored task time.</p>
<p>Popup Reminder –
Uses messagebox.showinfo() to alert the user when a scheduled time is reached.</p>
<p>Sound Notification –
Plays an alarm sound (alarm.mp3) using the playsound module when the reminder time arrives.</p>
<p>Task Viewing Window –
Opens a separate window displaying all saved tasks (ordered by date and time).</p>
<p>⚠️ Limitations Mentioned in Code</p>
<p>❌ Cannot delete tasks once added.</p>
<p>❌ Requires alarm.mp3 file in the same directory to work.</p>
<h3>The planner in your winter.py file has these main features:</h3>
<p>Key changes include:</p>
<p>Alarm Functionality Improvements: The alarm checking mechanism has been revamped. Instead of a separate thread running alarm_checker, the application now uses root.after to periodically call check_alarms, integrating more seamlessly with the Tkinter event loop. The play_alarm function also now uses threading to play sounds, preventing the GUI from freezing. 5 6</p>
<p>Database Schema Update: The SQLite database schema has been updated to include a "note" field for each task, allowing users to store additional details. 4</p>
<p>GUI Enhancements: A new label and entry field for "Note" have been added to the main application window. 10</p>
<p>Input Validation: The add_task method now checks if all fields, including the new "note" field, are filled before adding a task. 13</p>
<p>Task Display Update: The task display window now correctly shows all task details, including the note. The order of displayed fields has also been adjusted. 16</p>
<p>Code Organization: Some commented-out debugging or old code related to GUI limitations has been removed. The import of the datetime module was moved and re-added. 1 2 3</p>

<h3>The planner in your autumn.py file has these main features:</h3>
<p>This update primarily focuses on improving input validation, error handling, and the application's graceful shutdown.</p>
<p>The core changes include:</p>
<p>Enhanced Input Validation: The application now validates the date and time formats provided by the user. 5 If the date is not in YYYY-MM-DD format or the time is not in HH:MM (24-hour) format, an error message will be displayed, and the task will not be added.</p>
<p>Improved String Handling: User input for task fields now has leading and trailing whitespace removed using .strip(). 4</p>
<p>Corrected Database Column Order: The INSERT statement for adding tasks now correctly matches the defined column order in the database schema. 5</p>
<p>Clearer Task Display: The show_tasks function now displays the task details in a more readable format, ensuring the title, date, time, and note are presented logically. 7</p>
<p>Graceful Application Shutdown: A new on_close method is implemented to ensure the database connection is properly closed when the application window is shut down. 8</p>
<p>Code Cleanup: Some commented-out code related to dropping tables has been removed, and the application now explicitly handles window closing events. 1 3</p>
<p>UI Enhancements: Fields are now cleared after a task is successfully added. 6</p>

<h3>The planner in your raining.py file has these main features:</h3>
<p>1. Edit & Delete Tasks</p>
<p>Allow users to edit or remove existing tasks from the list.</p>
<p>Add “Edit” and “Delete” buttons beside each task in the “Show Tasks” window.</p>
<p>Update or remove entries in the SQLite database dynamically.</p>
</body>
</html>



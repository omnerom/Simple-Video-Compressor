import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import subprocess
import os
import threading
import webbrowser
import tempfile
from PIL import Image, ImageTk
import cv2
import time

DEFAULT_SIZE_MB = 10
DEFAULT_RESOLUTION = "720p"


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


def get_video_duration(input_file):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", input_file],
        capture_output=True, text=True
    )
    return float(result.stdout.strip())


def get_resolution(res_str):
    return {
        "480p": "854:480",
        "720p": "1280:720",
        "1080p": "1920:1080"
    }.get(res_str, "1280:720")


def generate_output_path(input_path, output_dir):
    base, ext = os.path.splitext(os.path.basename(input_path))
    output_path = os.path.join(output_dir, f"{base} - (Compressed){ext}")
    return output_path


def process_video(input_file, start_time, end_time, target_size_mb, resolution_str, output_dir):
    temp_file = None
    source_file = input_file

    if start_time > 0 or (end_time > 0 and end_time < get_video_duration(input_file)):
        temp_fd, temp_file = tempfile.mkstemp(suffix='.mp4')
        os.close(temp_fd)

        duration = end_time - start_time if end_time > 0 else None
        duration_param = ["-t", str(duration)] if duration else []

        subprocess.run([
                           "ffmpeg", "-y", "-i", input_file, "-ss", str(start_time)
                       ] + duration_param + [
                           "-c", "copy", temp_file
                       ])

        source_file = temp_file

    duration = get_video_duration(source_file)

    target_size_mb = target_size_mb * 0.98

    target_size_kb = target_size_mb * 1024
    target_bitrate = ((target_size_kb * 8) / duration) - 128
    resolution = get_resolution(resolution_str)
    output_file = generate_output_path(input_file, output_dir)
    passlog = "ffmpeg2pass"

    subprocess.run([
        "ffmpeg", "-y", "-i", source_file,
        "-b:v", f"{int(target_bitrate)}k", "-pass", "1",
        "-vf", f"scale={resolution}",
        "-an", "-f", "mp4", os.devnull
    ])

    subprocess.run([
        "ffmpeg", "-y", "-i", source_file,
        "-b:v", f"{int(target_bitrate)}k", "-pass", "2",
        "-vf", f"scale={resolution}",
        "-c:v", "libx264", "-preset", "slow",
        "-c:a", "aac", "-b:a", "128k",
        output_file
    ])

    for file in [f"{passlog}-0.log", f"{passlog}-0.log.mbtree"]:
        if os.path.exists(file):
            os.remove(file)

    if temp_file and os.path.exists(temp_file):
        os.remove(temp_file)

    messagebox.showinfo("Done", f"Output saved as:\n{output_file}")

def browse_file(entry, output_dir_entry, app):
    file_path = filedialog.askopenfilename(filetypes=[("Video files", "*.mp4 *.avi *.mkv *.mov")])
    if file_path:
        entry.delete(0, tk.END)
        entry.insert(0, file_path)

        input_folder = os.path.dirname(file_path)
        output_dir_entry.delete(0, tk.END)
        output_dir_entry.insert(0, input_folder)

        update_resolution_dropdown(file_path, app.resolution_var)
        app.load_video(file_path)

def browse_output_folder(output_dir_entry):
    folder_path = filedialog.askdirectory()
    if folder_path:
        output_dir_entry.delete(0, tk.END)
        output_dir_entry.insert(0, folder_path)

def start_processing(app):
    try:
        input_path = app.input_entry.get()
        size = int(app.size_entry.get())
        resolution = app.resolution_var.get().split()[0]
        output_dir = app.output_dir_entry.get()
        start_time = app.start_time
        end_time = app.end_time if app.end_time > app.start_time else 0

        threading.Thread(target=process_video,
                         args=(input_path, start_time, end_time, size, resolution, output_dir)).start()
    except Exception as e:
        messagebox.showerror("Error", str(e))

def open_github_repo():
    webbrowser.open("https://github.com/omnerom/Simple-Video-Compressor")

def get_resolution_for_duration(duration):
    if duration < 30:
        return "1080p", ["1080p (Recommended)", "720p", "480p"]
    elif 30 <= duration < 60:
        return "720p", ["1080p", "720p (Recommended)", "480p"]
    else:
        return "480p", ["1080p", "720p", "480p (Recommended)"]

def update_resolution_dropdown(input_path, resolution_var):
    try:
        duration = get_video_duration(input_path)
        recommended_res, resolutions = get_resolution_for_duration(duration)

        resolution_var['values'] = resolutions
        resolution_var.set(recommended_res)
    except Exception:
        resolution_var['values'] = ["1080p", "720p", "480p"]
        resolution_var.set("720p")

class VideoPlayerFrame(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.cap = None
        self.playing = False
        self.frame_interval = 24
        self.canvas_width = 480
        self.canvas_height = 270

        self.canvas = tk.Canvas(self, width=self.canvas_width, height=self.canvas_height, bg="black")
        self.canvas.pack(pady=5)

        self.controls_frame = tk.Frame(self)
        self.controls_frame.pack(fill="x", padx=5, pady=5)

        self.timeline_var = tk.DoubleVar()
        self.timeline = ttk.Scale(self, from_=0, to=100, orient="horizontal",
                                  variable=self.timeline_var, command=self.on_timeline_change)
        self.timeline.pack(fill="x", padx=10, pady=5)

        self.btn_play = ttk.Button(self.controls_frame, text="▶", width=3, command=self.toggle_play)
        self.btn_play.pack(side="left", padx=5)

        self.time_frame = tk.Frame(self.controls_frame)
        self.time_frame.pack(side="left", fill="x", expand=True)

        self.current_time_label = tk.Label(self.time_frame, text="00:00.000")
        self.current_time_label.pack(side="left", padx=5)

        self.duration_label = tk.Label(self.time_frame, text="/00:00.000")
        self.duration_label.pack(side="left")

        self.trim_frame = tk.Frame(self)
        self.trim_frame.pack(fill="x", padx=5, pady=5)

        self.btn_set_start = ttk.Button(self.trim_frame, text="Set Start", command=self.set_start_trim)
        self.btn_set_start.pack(side="left", padx=5)

        self.btn_set_end = ttk.Button(self.trim_frame, text="Set End", command=self.set_end_trim)
        self.btn_set_end.pack(side="left", padx=5)

        self.btn_reset_trim = ttk.Button(self.trim_frame, text="Reset Trim", command=self.reset_trim)
        self.btn_reset_trim.pack(side="left", padx=5)

        self.trim_indicator_frame = tk.Frame(self)
        self.trim_indicator_frame.pack(fill="x", padx=5, pady=5)

        tk.Label(self.trim_indicator_frame, text="Trim Start:").pack(side="left", padx=5)
        self.trim_start_label = tk.Label(self.trim_indicator_frame, text="00:00.000")
        self.trim_start_label.pack(side="left", padx=5)

        tk.Label(self.trim_indicator_frame, text="Trim End:").pack(side="left", padx=5)
        self.trim_end_label = tk.Label(self.trim_indicator_frame, text="End of video")
        self.trim_end_label.pack(side="left", padx=5)

    def load_video(self, video_path):
        if self.cap:
            self.cap.release()

        self.cap = cv2.VideoCapture(video_path)
        if not self.cap.isOpened():
            messagebox.showerror("Error", "Could not open video file")
            return

        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.duration = self.frame_count / self.fps if self.fps else 0

        self.time_per_frame = 1 / self.fps if self.fps else 0.033

        self.timeline.config(to=self.duration)
        self.timeline_var.set(0)

        self.reset_trim()

        self.duration_label.config(text=f"/{self.format_time(self.duration)}")

        self.update_frame(0)

        self.app.video_duration = self.duration

    def format_time(self, seconds):
        m, s = divmod(int(seconds), 60)
        ms = int((seconds - int(seconds)) * 1000)
        return f"{m:02d}:{s:02d}.{ms:03d}"

    def update_frame(self, position=None):
        if not self.cap:
            return

        if position is not None:
            self.cap.set(cv2.CAP_PROP_POS_MSEC, position * 1000)

        ret, frame = self.cap.read()
        if ret:
            frame = cv2.resize(frame, (self.canvas_width, self.canvas_height))
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            self.photo = ImageTk.PhotoImage(image=Image.fromarray(frame))
            self.canvas.create_image(0, 0, image=self.photo, anchor=tk.NW)

            current_time = self.cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
            self.current_time_label.config(text=self.format_time(current_time))

            if not hasattr(self, 'dragging') or not self.dragging:
                self.timeline_var.set(current_time)

    def play_video(self):
        if not self.cap or not self.playing:
            return

        current_time = self.cap.get(cv2.CAP_PROP_POS_MSEC) / 1000

        if current_time >= self.duration or (self.app.end_time > 0 and current_time >= self.app.end_time):
            self.cap.set(cv2.CAP_PROP_POS_MSEC, self.app.start_time * 1000)

        self.update_frame()

        self.after(self.frame_interval, self.play_video)

    def toggle_play(self):
        if not self.cap:
            return

        self.playing = not self.playing

        if self.playing:
            self.btn_play.config(text="⏸")

            current_time = self.cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
            if self.app.end_time > 0 and current_time >= self.app.end_time:
                self.cap.set(cv2.CAP_PROP_POS_MSEC, self.app.start_time * 1000)

            self.play_video()
        else:
            self.btn_play.config(text="▶")

    def on_timeline_change(self, value):
        if not self.cap:
            return

        self.dragging = True

        position = float(value)

        self.update_frame(position)

        self.after(100, self.clear_dragging_flag)

    def clear_dragging_flag(self):
        self.dragging = False

    def set_start_trim(self):
        if not self.cap:
            return

        current_time = self.cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
        self.app.start_time = current_time
        self.trim_start_label.config(text=self.format_time(current_time))

    def set_end_trim(self):
        if not self.cap:
            return

        current_time = self.cap.get(cv2.CAP_PROP_POS_MSEC) / 1000

        if current_time > self.app.start_time:
            self.app.end_time = current_time
            self.trim_end_label.config(text=self.format_time(current_time))
        else:
            messagebox.showwarning("Invalid Trim", "End time must be after start time")

    def reset_trim(self):
        self.app.start_time = 0
        self.app.end_time = 0
        self.trim_start_label.config(text="00:00.000")
        self.trim_end_label.config(text="End of video")

    def step_forward(self):
        if not self.cap:
            return

        current_time = self.cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
        new_time = current_time + self.time_per_frame

        if new_time >= self.duration:
            new_time = self.duration - self.time_per_frame

        self.update_frame(new_time)

    def step_backward(self):
        if not self.cap:
            return

        current_time = self.cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
        new_time = current_time - self.time_per_frame

        if new_time < 0:
            new_time = 0

        self.update_frame(new_time)

class VideoCompressorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Simple Video Compressor")
        self.root.geometry("800x700")

        self.video_duration = 0
        self.start_time = 0
        self.end_time = 0

        self.main_frame = tk.Frame(root)
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.file_frame = tk.Frame(self.main_frame)
        self.file_frame.pack(fill="x", pady=5)

        input_label = tk.Label(self.file_frame, text="Input File:")
        input_label.grid(row=0, column=0, padx=10, pady=10)
        self.input_entry = tk.Entry(self.file_frame, width=60)
        self.input_entry.grid(row=0, column=1)
        input_button = tk.Button(self.file_frame, text="Browse",
                                 command=lambda: browse_file(self.input_entry, self.output_dir_entry, self))
        input_button.grid(row=0, column=2)

        output_folder_label = tk.Label(self.file_frame, text="Output Folder:")
        output_folder_label.grid(row=1, column=0, padx=10, pady=10)
        self.output_dir_entry = tk.Entry(self.file_frame, width=60)
        self.output_dir_entry.grid(row=1, column=1)
        output_button = tk.Button(self.file_frame, text="Browse",
                                  command=lambda: browse_output_folder(self.output_dir_entry))
        output_button.grid(row=1, column=2)

        self.player_frame = VideoPlayerFrame(self.main_frame, self)
        self.player_frame.pack(fill="x", pady=10)

        self.settings_frame = tk.LabelFrame(self.main_frame, text="Compression Settings")
        self.settings_frame.pack(fill="x", pady=10)

        size_label = tk.Label(self.settings_frame, text="Target Size (MB):")
        size_label.grid(row=0, column=0, padx=10, pady=10)
        self.size_entry = tk.Entry(self.settings_frame)
        self.size_entry.insert(0, str(DEFAULT_SIZE_MB))
        self.size_entry.grid(row=0, column=1)

        resolution_label = tk.Label(self.settings_frame, text="Resolution:")
        resolution_label.grid(row=0, column=2, padx=10, pady=10)
        self.resolution_var = ttk.Combobox(self.settings_frame, values=["480p", "720p", "1080p"],
                                           state="readonly", width=20)
        self.resolution_var.grid(row=0, column=3, padx=10, pady=10)
        self.resolution_var.set(DEFAULT_RESOLUTION)

        self.export_frame = tk.Frame(self.main_frame)
        self.export_frame.pack(fill="x", pady=20)

        self.export_button = tk.Button(self.export_frame, text="Export Video",
                                       command=lambda: start_processing(self),
                                       font=("Arial", 12, "bold"), bg="#4CAF50", fg="white",
                                       padx=20, pady=10)
        self.export_button.pack()

        self.credits_frame = tk.Frame(self.main_frame)
        self.credits_frame.pack(fill="x", pady=10)

        github_button = tk.Button(self.credits_frame, text="GitHub Repo", command=open_github_repo)
        github_button.pack()

    def load_video(self, video_path):
        self.player_frame.load_video(video_path)

if __name__ == "__main__":
    root = tk.Tk()

    try:
        root.iconbitmap(resource_path('icon.ico'))
    except tk.TclError:
        pass

    app = VideoCompressorApp(root)
    root.mainloop()
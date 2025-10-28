import tkinter as tk
from tkinter import ttk, messagebox
import threading
import sys
import keyboard
from rapidfuzz import fuzz, process

from src.auto_paint.auto_painter import AutoPainter


class AutoPainterApp:
    def __init__(self, root, color_map):
        self.root = root
        self.root.title("wplace-auto-painter")
        self.root.geometry("600x400")
        self.root.resizable(True, True)

        self.color_map = color_map
        self.current_color = 'black' if 'black' in color_map else (next(iter(color_map), None))
        self.target_image_path = self.color_map.get(self.current_color)
        self.all_colors = list(self.color_map.keys())

        # 网格布局配置
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        # 运行状态
        self.running = False
        self.thread = None

        # painter 实例
        self.painter = AutoPainter()

        self.create_widgets()
        keyboard.add_hotkey('esc', self.stop_script)

    def create_widgets(self):
        main_frame = tk.Frame(self.root)
        main_frame.grid(row=0, column=0, sticky="nsew")

        main_frame.grid_columnconfigure(0, weight=1)
        for i in range(5):
            main_frame.grid_rowconfigure(i, weight=1)

        tk.Label(main_frame, text="wplace-auto-painter", font=('Arial', 16)).grid(row=0, column=0, pady=10, sticky="n")

        color_frame = tk.Frame(main_frame)
        color_frame.grid(row=1, column=0, pady=10, sticky="n")

        tk.Label(color_frame, text="选择颜色:").pack(side=tk.LEFT, padx=5)

        self.color_var = tk.StringVar(value=self.current_color)
        self.color_dropdown = ttk.Combobox(
            color_frame,
            textvariable=self.color_var,
            values=self.all_colors,
            state="normal",
            width=15
        )
        self.color_dropdown.pack(side=tk.LEFT)

        self.color_dropdown.bind("<KeyRelease>", self.on_color_input)
        self.color_dropdown.bind("<FocusOut>", self.on_focus_out)
        self.color_dropdown.bind("<Return>", lambda e: self.validate_color_selection())
        self.color_dropdown.bind("<<ComboboxSelected>>", lambda e: self.validate_color_selection())
        self.color_dropdown.bind("<Down>", self.on_down_arrow)

        self.start_btn = tk.Button(main_frame, text="start", command=self.start_script, bg="green", fg="white", height=2, width=15)
        self.start_btn.grid(row=2, column=0, pady=20, sticky="n")

        self.status_var = tk.StringVar()
        self.status_var.set("准备就绪")
        tk.Label(main_frame, textvariable=self.status_var).grid(row=3, column=0, sticky="s")

        tk.Label(main_frame, text="ESC键退出绘制，绘制失败时尝试缩放地图至合适大小", font=('Arial', 9), fg='gray').grid(row=4, column=0, pady=(0, 10), sticky="s")

        main_frame.grid_propagate(False)

    def on_down_arrow(self, event):
        if self.color_dropdown["values"]:
            self.color_dropdown.event_generate("<Down>")
        return "break"

    def on_color_input(self, event):
        if event.keysym in ('BackSpace', 'Delete', 'Left', 'Right', 'Up', 'Down'):
            return

        current_text = self.color_var.get().lower()
        if not current_text:
            self.color_dropdown["values"] = self.all_colors
        else:
            matches = process.extractBests(current_text, self.all_colors, scorer=fuzz.partial_ratio, score_cutoff=60)
            self.color_dropdown["values"] = [match[0] for match in matches]

    def on_focus_out(self, event):
        self.validate_color_selection()

    def validate_color_selection(self):
        selected_color = self.color_var.get()
        if selected_color in self.color_map:
            self.confirm_color_selection(selected_color)
        else:
            matches = process.extractOne(selected_color, self.all_colors, scorer=fuzz.partial_ratio)
            if matches and matches[1] > 70:
                self.confirm_color_selection(matches[0])
            else:
                messagebox.showwarning("无效选择", "请从下拉列表中选择有效颜色")
                self.color_var.set(self.current_color)

    def confirm_color_selection(self, color):
        if color in self.color_map:
            self.current_color = color
            self.target_image_path = self.color_map[color]
            self.status_var.set(f"已选择颜色: {color}")
        else:
            self.color_var.set(self.current_color)

    def start_script(self):
        if not self.running:
            self.running = True
            self.status_var.set("运行中...")
            self.start_btn.config(state=tk.DISABLED)
            self.root.iconify()

            # 在新线程中运行 painter.run，并传入 getter
            self.thread = threading.Thread(target=self._run_painter, daemon=True)
            self.thread.start()

    def _run_painter(self):
        # 传入两个 getter：目标路径 getter 和 运行状态 getter
        self.painter.run(lambda: self.target_image_path, lambda: self.running)
        # 运行结束后恢复按钮和窗口
        self.running = False
        try:
            # 在主线程中更新 UI
            self.root.after(0, lambda: self.start_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.root.deiconify())
            self.root.after(0, lambda: self.status_var.set("已停止"))
        except Exception:
            pass

    def stop_script(self):
        if self.running:
            self.running = False
            self.status_var.set("已停止")
            self.start_btn.config(state=tk.NORMAL)
            self.root.deiconify()

    def on_closing(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1)
        self.root.destroy()
        sys.exit()

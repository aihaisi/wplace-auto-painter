import tkinter as tk
from tkinter import ttk, messagebox
import threading
import sys
import keyboard
from rapidfuzz import fuzz, process
import time
from src.auto_paint.auto_painter import AutoPainter
from src.data import load_color_map
from src import color_tackle


class AutoPainterApp:
    def __init__(self, root, color_map=None):
        self.root = root
        self.root.title("wplace-auto-painter")
        self.root.geometry("600x400")
        self.root.resizable(True, True)

        # 如果外部没有传入 color_map，则内部加载
        if color_map is None:
            # 优先使用已存在的数据加载器；若失败或返回空，则回退到 color_tackle 的默认颜色表
            try:
                color_map = load_color_map()
            except Exception:
                color_map = {}
            if not color_map:
                try:
                    color_map = color_tackle.init_color()
                except Exception:
                    color_map = {}

        self.color_map = color_map
        self.current_color = 'black' if 'black' in self.color_map else (next(iter(self.color_map), None))
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
        # 记录当前输入的预测匹配（用于按回车快速选择）
        self.predicted_color = None

        self.create_widgets()
        keyboard.add_hotkey('esc', self.stop_script)

    def create_widgets(self):
        # 主框架（使用grid布局）
        main_frame = tk.Frame(self.root)
        main_frame.grid(row=0, column=0, sticky="nsew")
        
        # 配置主框架的网格
        main_frame.grid_columnconfigure(0, weight=1)
        for i in range(3):  # 3行
            main_frame.grid_rowconfigure(i, weight=1)
        
        # 标题（第0行）
        tk.Label(
            main_frame, 
            text="wplace-auto-painter", 
            font=('Arial', 16)
        ).grid(row=0, column=0, pady=10, sticky="n")
        
        # 颜色选择（带模糊匹配）
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
        
        # 事件绑定（优化版）
        self.color_dropdown.bind("<KeyRelease>", self.on_color_input)
        self.color_dropdown.bind("<FocusOut>", self.on_focus_out)
        self.color_dropdown.bind("<Return>", lambda e: self.validate_color_selection())
        self.color_dropdown.bind("<<ComboboxSelected>>", lambda e: self.validate_color_selection())
        self.color_dropdown.bind("<Down>", self.on_down_arrow)  # 新增下箭头键处理
        
        # 开始按钮（第2行）
        self.start_btn = tk.Button(
            main_frame,
            text="start",
            command=self.start_script,
            bg="green",
            fg="white",
            height=2,
            width=15
        )
        self.start_btn.grid(row=2, column=0, pady=20, sticky="n")
        
        # 状态标签（第3行）
        self.status_var = tk.StringVar()
        self.status_var.set("准备就绪")
        tk.Label(
            main_frame, 
            textvariable=self.status_var
        ).grid(row=3, column=0, sticky="s")
        
        # 新增ESC提示（第4行）
        tk.Label(
            main_frame,
            text="ESC键退出绘制，绘制失败时尝试缩放地图至合适大小\n超出一段时间未匹配到颜色会自动提交并停止",
            font=('Arial', 9),
            fg='gray'
        ).grid(row=4, column=0, pady=(0, 10), sticky="s")
        
        main_frame.grid_propagate(False)

    def on_down_arrow(self, event):
        # 按下下箭头时调用函数
        if self.color_dropdown["values"]:
            self.color_dropdown.event_generate("<Down>")
        return "break"

    def on_color_input(self, event):
        # 输入框输入时更新调用函数
        if event.keysym in ('BackSpace', 'Delete', 'Left', 'Right', 'Up', 'Down'):
            return

        current_text = self.color_var.get().lower()
        if not current_text:
            self.color_dropdown["values"] = self.all_colors
        else:
            # 使用模糊匹配获取候选列表和最佳匹配
            # rapidfuzz 使用 extract 并设置 limit 为所有颜色数
            matches = process.extract(current_text, self.all_colors, scorer=fuzz.partial_ratio, score_cutoff=60, limit=len(self.all_colors))
            # process.extract 返回 (choice, score, index) 元组
            self.color_dropdown["values"] = [match[0] for match in matches]

            best = process.extractOne(current_text, self.all_colors, scorer=fuzz.partial_ratio)
            if best and best[1] >= 60:
                # 保存预测结果，按下回车时将优先确认
                self.predicted_color = best[0]
            else:
                self.predicted_color = None

    def on_focus_out(self, event):
        # 输入框失去焦点时调用函数
        self.validate_color_selection()

    def validate_color_selection(self):
        """
        颜色验证函数\n
        验证当前选择的颜色是否合法，若合法则确认选择，否则恢复上次选择。
        """
        selected_color = self.color_var.get()
        if selected_color in self.color_map:
            self.confirm_color_selection(selected_color)
        else:
            # 优先使用 on_color_input 计算出的预测匹配（当用户在输入后直接按回车）
            if getattr(self, 'predicted_color', None):
                self.confirm_color_selection(self.predicted_color)
                return

            matches = process.extractOne(selected_color, self.all_colors, scorer=fuzz.partial_ratio)
            if matches and matches[1] > 70:
                self.confirm_color_selection(matches[0])
            else:
                messagebox.showwarning("无效选择", "请从下拉列表中选择有效颜色")
                self.color_var.set(self.current_color)
    def confirm_color_selection(self, color):
        """
        确认颜色选择函数\n
        确认当前选择的颜色是否合法，若合法则更新当前颜色和目标图片路径，否则恢复上次选择。
        """
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
        # 停止脚本的执行
        if self.running:
            self.running = False
            self.status_var.set("已停止")
            self.start_btn.config(state=tk.NORMAL)
            time.sleep(0.5)  # 确保线程有时间响应停止信号
            self.root.deiconify()
 
    def on_closing(self):
        # 处理窗口关闭事件
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1)
        self.root.destroy()
        sys.exit()
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import sys
import keyboard
from rapidfuzz import fuzz, process
import time
import pyautogui
import ctypes
from src.auto_paint.auto_painter import AutoPainter
from src.data import load_color_map
from src import color_tackle
from src import generate_color


class AutoPainterApp:
    def __init__(self, root, color_map=None):
        self.root = root
        self.root.title("wplace-auto-painter")
        self.root.geometry("650x550")  # 增加窗口高度以容纳新控件
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

        # painter 实例 - 添加默认阈值
        self.threshold_value = 0.8  # 默认阈值
        self.painter = AutoPainter(threshold=self.threshold_value)
        # 记录当前输入的预测匹配（用于按回车快速选择）
        self.predicted_color = None
        # 颜色吸管是否活动的标志（避免未初始化访问）
        self.color_picker_active = False
        # 存放通过吸管选择的背景颜色 (r, g, b)
        self.background_color = generate_color.BACKGROUND

        self.create_widgets()
        keyboard.add_hotkey('esc', self.stop_script)

    def create_widgets(self):
        # 主框架（使用grid布局）
        main_frame = tk.Frame(self.root)
        main_frame.grid(row=0, column=0, sticky="nsew")
        
        # 配置主框架的网格
        main_frame.grid_columnconfigure(0, weight=1)
        for i in range(8):  # 增加到8行以适应新控件
            main_frame.grid_rowconfigure(i, weight=1)
        
        # 标题（第0行）
        tk.Label(
            main_frame, 
            text="wplace-auto-painter", 
            font=('Arial', 16)
        ).grid(row=0, column=0, pady=10, sticky="n")
        
        # 颜色选择（带模糊匹配）- 现在在第2行
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

    
                # 匹配度改动 - 新增匹配度调节区域（第1行）
        threshold_frame = tk.Frame(main_frame)
        threshold_frame.grid(row=2, column=0, pady=10, sticky="n")
        
        tk.Label(threshold_frame, text="匹配度调整:").pack(side=tk.LEFT, padx=5)
        
        # 滑动条
        self.threshold_var = tk.DoubleVar(value=self.threshold_value)
        self.threshold_scale = tk.Scale(
            threshold_frame,
            variable=self.threshold_var,
            from_=0.5,  # 最小值
            to=0.95,    # 最大值
            resolution=0.01,  # 步长
            orient=tk.HORIZONTAL,
            length=200,
            showvalue=True,
            command=self.on_threshold_change
        )
        self.threshold_scale.pack(side=tk.LEFT, padx=5)
        
        # 数值输入框
        self.threshold_entry = tk.Entry(
            threshold_frame,
            width=5
        )
        self.threshold_entry.insert(0, str(self.threshold_value))
        self.threshold_entry.pack(side=tk.LEFT, padx=5)
        self.threshold_entry.bind("<Return>", self.on_threshold_entry_change)
        
        # 确认按钮
        threshold_confirm_btn = tk.Button(
            threshold_frame,
            text="应用",
            command=self.apply_threshold_change,
            width=4
        )
        threshold_confirm_btn.pack(side=tk.LEFT, padx=5)
        
        # 当前值显示
        self.threshold_display_var = tk.StringVar()
        self.threshold_display_var.set(f"当前: {self.threshold_value}")
        threshold_display_label = tk.Label(
            threshold_frame,
            textvariable=self.threshold_display_var,
            font=('Arial', 9),
            fg='blue'
        )
        threshold_display_label.pack(side=tk.LEFT, padx=5)
        
        
        # 事件绑定（在 combobox 创建后绑定，避免未定义属性访问）
        self.color_dropdown.bind("<KeyRelease>", self.on_color_input)
        self.color_dropdown.bind("<FocusOut>", self.on_focus_out)
        self.color_dropdown.bind("<Return>", lambda e: self.validate_color_selection())
        self.color_dropdown.bind("<<ComboboxSelected>>", lambda e: self.validate_color_selection())
        self.color_dropdown.bind("<Down>", self.on_down_arrow)  # 新增下箭头键处理
        
        # 开始按钮（第3行）
        self.start_btn = tk.Button(
            main_frame,
            text="start",
            command=self.start_script,
            bg="green",
            fg="white",
            height=2,
            width=15
        )
        self.start_btn.grid(row=3, column=0, pady=20, sticky="n")
        
        # 新增颜色吸管区域（第4行）
        color_picker_frame = tk.Frame(main_frame)
        color_picker_frame.grid(row=4, column=0, pady=10, sticky="n")
        
        # 颜色吸管按钮
        self.picker_btn = tk.Button(
            color_picker_frame,
            text="选取背景颜色",
            command=self.toggle_color_picker,
            bg="lightblue",
            height=1,
            width=10
        )
        self.picker_btn.pack(side=tk.LEFT, padx=5)
        
        # 显示RGB值的标签
        self.rgb_var = tk.StringVar()
        self.rgb_var.set(f"RGB: {self.background_color}")
        rgb_label = tk.Label(
            color_picker_frame,
            textvariable=self.rgb_var,
            font=('Arial', 8),
            bg='white',
            relief='sunken',
            width=18
        )
        rgb_label.pack(side=tk.LEFT, padx=5)
        
        # 颜色预览框
        self.color_preview = tk.Label(
            color_picker_frame,
            text="   ",
            font=('Arial', 10),
            bg='#{:02x}{:02x}{:02x}'.format(self.background_color[0], self.background_color[1], self.background_color[2]),
            relief='sunken',
            width=3
        )
        self.color_preview.pack(side=tk.LEFT, padx=5)
        
        # 在第5行添加「生成背景色块」按钮
        self.generate_bg_btn = tk.Button(
            main_frame,
            text="生成颜色模版",
            command=self.on_generate_by_background,
            bg="white",
            height=1,
            width=14
        )
        self.generate_bg_btn.grid(row=5, column=0, pady=6)

        # 状态标签（第6行）
        self.status_var = tk.StringVar()
        self.status_var.set("准备就绪")
        tk.Label(
            main_frame, 
            textvariable=self.status_var
        ).grid(row=6, column=0, sticky="s")
        
        # 新增ESC提示（第7行）
        tk.Label(
            main_frame,
            text="ESC键退出绘制，绘制失败时尝试缩放地图至合适大小\n超出一段时间未匹配到颜色会自动提交并停止",
            font=('Arial', 9),
            fg='gray'
        ).grid(row=7, column=0, pady=(0, 10), sticky="s")
        
        main_frame.grid_propagate(False)

    def on_threshold_change(self, event=None):
        """滑动条改变时的回调函数"""
        # 更新输入框的值
        new_value = self.threshold_var.get()
        self.threshold_entry.delete(0, tk.END)
        self.threshold_entry.insert(0, f"{new_value:.2f}")

    def on_threshold_entry_change(self, event):
        """输入框回车时的回调函数"""
        self.apply_threshold_change()

    def apply_threshold_change(self):
        """应用阈值改变"""
        try:
            # 从输入框获取值
            entry_value = self.threshold_entry.get().strip()
            if not entry_value:
                return
                
            new_threshold = float(entry_value)
            
            # 验证范围
            if new_threshold < 0.5:
                new_threshold = 0.5
            elif new_threshold > 0.95:
                new_threshold = 0.95
                
            # 更新所有控件
            self.threshold_value = new_threshold
            self.threshold_var.set(new_threshold)
            self.threshold_entry.delete(0, tk.END)
            self.threshold_entry.insert(0, f"{new_threshold:.2f}")
            self.threshold_display_var.set(f"当前: {new_threshold:.2f}")
            
            # 更新AutoPainter的阈值
            self.painter.threshold = new_threshold
            
            self.status_var.set(f"匹配度已更新为: {new_threshold:.2f}")
            
        except ValueError:
            messagebox.showerror("错误", "请输入有效的数值（0.5-0.95）")
            # 恢复原来的值
            self.threshold_entry.delete(0, tk.END)
            self.threshold_entry.insert(0, f"{self.threshold_value:.2f}")

    # 以下为原有的其他方法，保持不变
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
            matches = process.extract(current_text, self.all_colors, scorer=fuzz.partial_ratio, score_cutoff=60, limit=len(self.all_colors))
            self.color_dropdown["values"] = [match[0] for match in matches]

            best = process.extractOne(current_text, self.all_colors, scorer=fuzz.partial_ratio)
            if best and best[1] >= 60:
                self.predicted_color = best[0]
            else:
                self.predicted_color = None

    def on_focus_out(self, event):
        self.validate_color_selection()

    def validate_color_selection(self):
        selected_color = self.color_var.get()
        if selected_color in self.color_map:
            self.confirm_color_selection(selected_color)
        else:
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
        if color in self.color_map:
            self.current_color = color
            self.target_image_path = self.color_map[color]
            self.status_var.set(f"已选择颜色: {color}")
        else:
            self.color_var.set(self.current_color)

    def toggle_color_picker(self):
        if not self.color_picker_active:
            self.start_color_picker()
        else:
            self.stop_color_picker()
    
    def start_color_picker(self):
        self.color_picker_active = True
        self.picker_btn.config(text="🛑 停止吸管", bg="red")
        self.status_var.set("颜色吸管已启动 - 移动鼠标查看颜色")
        
        self.color_picker_thread = threading.Thread(target=self.color_picker_loop, daemon=True)
        self.color_picker_thread.start()
    
    def stop_color_picker(self):
        self.color_picker_active = False
        self.picker_btn.config(text="🎨 颜色吸管", bg="lightblue")
        self.status_var.set("颜色吸管已停止")
        self.rgb_var.set("RGB: (---, ---, ---)")
        self.color_preview.config(bg='white')
        self.root.deiconify()
    
    def color_picker_loop(self):
        try:
            while self.color_picker_active and not self.running:
                if keyboard.is_pressed('esc'):
                    self.stop_color_picker()
                    break
                
                x, y = pyautogui.position()
                rgb = pyautogui.pixel(x, y)
                
                try:
                    if ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000:
                        self.background_color = rgb
                        self.root.after(0, lambda: self.on_color_click(rgb, x, y))
                        break
                except Exception:
                    pass

                self.root.after(0, self.update_color_display, rgb, x, y)
                time.sleep(0.05)
                
        except Exception as e:
            print(f"颜色吸管错误: {e}")
            self.stop_color_picker()
    
    def update_color_display(self, rgb, x, y):
        if not self.color_picker_active:
            return
        
        self.rgb_var.set(f"RGB: {rgb}")
        hex_color = '#{:02x}{:02x}{:02x}'.format(rgb[0], rgb[1], rgb[2])
        self.color_preview.config(bg=hex_color)
        self.status_var.set(f"坐标: ({x}, {y}) | RGB: {rgb}")

    def on_color_click(self, rgb, x, y):
        self.background_color = rgb
        self.stop_color_picker()
        try:
            self.root.deiconify()
            try:
                self.root.lift()
            except Exception:
                pass
            try:
                self.root.focus_force()
            except Exception:
                pass
            try:
                self.root.attributes("-topmost", True)
                self.root.after(250, lambda: self.root.attributes("-topmost", False))
            except Exception:
                pass
        except Exception:
            pass
        self.rgb_var.set(f"RGB: {rgb}")
        hex_color = '#{:02x}{:02x}{:02x}'.format(rgb[0], rgb[1], rgb[2])
        self.color_preview.config(bg=hex_color)
        self.status_var.set(f"已设置背景颜色: {rgb} @({x},{y})")

    def on_generate_by_background(self):
        bg = self.background_color
        if not bg:
            messagebox.showwarning("未设置背景色", "请先使用颜色吸管选择一个背景颜色。")
            return

        try:
            generate_color.generate_color_by_background(bg)
            messagebox.showinfo("完成", "颜色模版生成完毕，在src/color文件下")
        except Exception as e:
            messagebox.showerror("错误", f"调用 generate_color_by_background 时出错: {e}")

    def start_script(self):
        if not self.running:
            self.running = True
            self.status_var.set("运行中...")
            self.start_btn.config(state=tk.DISABLED)
            self.root.iconify()

            self.thread = threading.Thread(target=self._run_painter, daemon=True)
            self.thread.start()

    def _run_painter(self):
        self.painter.run(lambda: self.target_image_path, lambda: self.running)
        self.running = False
        try:
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
            time.sleep(0.5)
            self.root.deiconify()
 
    def on_closing(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1)
        self.root.destroy()
        sys.exit()
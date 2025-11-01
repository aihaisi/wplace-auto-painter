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
        self.root.geometry("650x500")
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
        for i in range(3):  # 3行
            main_frame.grid_rowconfigure(i, weight=1)
        
        # 标题（第0行）
        tk.Label(
            main_frame, 
            text="wplace-auto-painter", 
            font=('Arial', 16)
        ).grid(row=0, column=0, pady=10, sticky="n")
        
    # 注意: combobox 在下面创建，事件绑定应在创建之后执行（见下）
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

        # 事件绑定（在 combobox 创建后绑定，避免未定义属性访问）
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
        
        # 新增颜色吸管区域
        color_picker_frame = tk.Frame(main_frame)
        color_picker_frame.grid(row=3, column=0, pady=10, sticky="n")
        
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
        
        # 在第4行添加「生成背景色块」按钮
        self.generate_bg_btn = tk.Button(
            main_frame,
            text="生成颜色模版",
            command=self.on_generate_by_background,
            bg="white",
            height=1,
            width=14
        )
        self.generate_bg_btn.grid(row=4, column=0, pady=6)

        # 状态标签（第5行）
        self.status_var = tk.StringVar()
        self.status_var.set("准备就绪")
        tk.Label(
            main_frame, 
            textvariable=self.status_var
        ).grid(row=5, column=0, sticky="s")
        
        # 新增ESC提示（第6行）
        tk.Label(
            main_frame,
            text="ESC键退出绘制，绘制失败时尝试缩放地图至合适大小\n超出一段时间未匹配到颜色会自动提交并停止",
            font=('Arial', 9),
            fg='gray'
        ).grid(row=6, column=0, pady=(0, 10), sticky="s")
        
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

    def toggle_color_picker(self):
        """切换颜色吸管状态"""
        if not self.color_picker_active:
            self.start_color_picker()
        else:
            self.stop_color_picker()
    
    def start_color_picker(self):
        """启动颜色吸管"""
        self.color_picker_active = True
        self.picker_btn.config(text="🛑 停止吸管", bg="red")
        self.status_var.set("颜色吸管已启动 - 移动鼠标查看颜色")
        
        # 在新线程中运行颜色吸管
        self.color_picker_thread = threading.Thread(target=self.color_picker_loop, daemon=True)
        self.color_picker_thread.start()
    
    def stop_color_picker(self):
        """停止颜色吸管"""
        self.color_picker_active = False
        self.picker_btn.config(text="🎨 颜色吸管", bg="lightblue")
        self.status_var.set("颜色吸管已停止")
        self.rgb_var.set("RGB: (---, ---, ---)")
        self.color_preview.config(bg='white')
        
        self.root.deiconify()
    
    def color_picker_loop(self):
        """颜色吸管主循环"""
        try:
            while self.color_picker_active and not self.running:
                if keyboard.is_pressed('esc'):
                    self.stop_color_picker()
                    break
                
                # 获取鼠标位置和颜色
                x, y = pyautogui.position()
                rgb = pyautogui.pixel(x, y)
                
                # 如果检测到鼠标左键按下，则视为确认选择
                try:
                    # VK_LBUTTON = 0x01, 高位为1表示按下
                    if ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000:
                        # 保存选择并在主线程处理后退出循环
                        self.background_color = rgb
                        self.root.after(0, lambda: self.on_color_click(rgb, x, y))
                        break
                except Exception:
                    # 如果 ctypes 检测出现问题，不影响常规显示
                    pass

                # 更新GUI（需要在主线程中执行）
                self.root.after(0, self.update_color_display, rgb, x, y)
                
                # 控制刷新频率
                time.sleep(0.05)
                
        except Exception as e:
            print(f"颜色吸管错误: {e}")
            self.stop_color_picker()
    
    def update_color_display(self, rgb, x, y):
        """更新颜色显示（在主线程中执行）"""
        if not self.color_picker_active:
            return
        
        # 更新RGB值显示
        self.rgb_var.set(f"RGB: {rgb}")
        
        # 更新颜色预览框
        hex_color = '#{:02x}{:02x}{:02x}'.format(rgb[0], rgb[1], rgb[2])
        self.color_preview.config(bg=hex_color)
        
        # 可选：在状态栏显示坐标
        self.status_var.set(f"坐标: ({x}, {y}) | RGB: {rgb}")


    def on_color_click(self, rgb, x, y):
        """处理鼠标左键点击选择：保存颜色、停止吸管并更新 UI"""
        # 确保保存值（loop 已设置过一次，但再次设置以防万一）
        self.background_color = rgb
        # 停止吸管（会更新按钮与状态），然后恢复所选颜色显示
        self.stop_color_picker()
        # 如果窗口被最小化（例如 start_script 时调用了 iconify），确保恢复显示
        try:
            self.root.deiconify()
            # 提升窗口并短暂置顶，确保它被显示在最前
            try:
                self.root.lift()
            except Exception:
                pass
            try:
                self.root.focus_force()
            except Exception:
                pass
            try:
                # 临时设置 topmost，使窗口显现在最前；随后恢复为非 topmost
                self.root.attributes("-topmost", True)
                self.root.after(250, lambda: self.root.attributes("-topmost", False))
            except Exception:
                pass
        except Exception:
            pass
        # 更新显示为所选颜色
        self.rgb_var.set(f"RGB: {rgb}")
        hex_color = '#{:02x}{:02x}{:02x}'.format(rgb[0], rgb[1], rgb[2])
        self.color_preview.config(bg=hex_color)
        self.status_var.set(f"已设置背景颜色: {rgb} @({x},{y})")
        


    def on_generate_by_background(self):
        """将当前选择的背景颜色传给 generate_color.generate_color_by_background。
        如果函数尚未实现，则弹窗提示。
        """
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
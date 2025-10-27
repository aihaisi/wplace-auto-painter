import tkinter as tk
from tkinter import ttk, messagebox
import threading
import pyautogui
import cv2
import numpy as np
import keyboard  # 全局监听
import time
import sys
from fuzzywuzzy import fuzz, process


class AutoPainterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("wplace-auto-painter")
        self.root.geometry("600x400")
        self.root.resizable(True, True)
        
        self.color_map = init_color()
        self.current_color = 'black'  # 默认颜色
        self.target_image_path = self.color_map[self.current_color]
        self.all_colors = list(self.color_map.keys())
        
        # 网格布局配置
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=1)
        
        # 运行状态
        self.running = False
        self.thread = None
        
        # 未匹配次数
        self.unmatched_count = 0
        
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
        """按下箭头键时手动弹出下拉框"""
        if self.color_dropdown["values"]:
            self.color_dropdown.event_generate("<Down>")
        return "break"  # 阻止默认行为
    
    def on_color_input(self, event):
        """处理颜色输入（不自动弹出下拉框）"""
        # 忽略导航键
        if event.keysym in ('BackSpace', 'Delete', 'Left', 'Right', 'Up', 'Down'):
            return
        
        current_text = self.color_var.get().lower()
        
        # 更新下拉列表但不弹出
        if not current_text:
            self.color_dropdown["values"] = self.all_colors
        else:
            matches = process.extractBests(
                current_text,
                self.all_colors,
                scorer=fuzz.partial_ratio,
                score_cutoff=60
            )
            self.color_dropdown["values"] = [match[0] for match in matches]
    
    def on_focus_out(self, event):
        """失去焦点时的处理"""
        self.validate_color_selection()
    
    def validate_color_selection(self):
        """验证颜色选择"""
        selected_color = self.color_var.get()
        
        if selected_color in self.color_map:
            self.confirm_color_selection(selected_color)
        else:
            # 尝试模糊匹配
            matches = process.extractOne(
                selected_color,
                self.all_colors,
                scorer=fuzz.partial_ratio
            )
            if matches and matches[1] > 70:
                self.confirm_color_selection(matches[0])
            else:
                messagebox.showwarning("无效选择", "请从下拉列表中选择有效颜色")
                self.color_var.set(self.current_color)
    
    def confirm_color_selection(self, color):
        """确认颜色选择"""
        if color in self.color_map:
            self.current_color = color
            self.target_image_path = self.color_map[color]
            self.status_var.set(f"已选择颜色: {color}")
        else:
            self.color_var.set(self.current_color)
    
    def start_script(self):
        """开始运行脚本"""
        if not self.running:
            self.running = True
            self.status_var.set("运行中...")
            self.start_btn.config(state=tk.DISABLED)
            
            # 最小化窗口
            self.root.iconify()
            
            # 在新线程中运行脚本
            self.thread = threading.Thread(target=self.start_paint, daemon=True)
            self.thread.start()
    
    def stop_script(self):
        """停止脚本运行"""
        if self.running:
            self.running = False
            self.status_var.set("已停止")
            self.start_btn.config(state=tk.NORMAL)
            
            # 恢复窗口
            self.root.deiconify()
    
    def start_paint(self):
        click_offset_x = 0
        click_offset_y = 0
        
        try:
            target_image = cv2.imread(self.target_image_path)
            if target_image is None:
                messagebox.showerror("错误", f"无法加载目标图像: {self.target_image_path}")
                self.stop_script()
                return
                
            target_height, target_width = target_image.shape[:2]
            
            while self.running:
                # 检查ESC键是否被按下
                if keyboard.is_pressed('esc'):
                    self.stop_script()
                    break
                
                # 截取屏幕截图
                screenshot = pyautogui.screenshot()
                screenshot = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
                
                # 使用模板匹配
                result = cv2.matchTemplate(screenshot, target_image, cv2.TM_CCOEFF_NORMED)
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
                
                threshold = 0.8
                if max_val >= threshold:
                    top_left = max_loc
                    center_x = top_left[0] + target_width // 2 + click_offset_x
                    center_y = top_left[1] + target_height // 2 + click_offset_y
                    
                    pyautogui.moveTo(center_x, center_y)
                    pyautogui.click()
                    self.unmatched_count = 0  # 重置未匹配计数
                    print(f"点击位置: ({center_x}, {center_y})")
                    
                else:
                    self.unmatched_count += 1
                    if self.unmatched_count > 50:
                        self.click_submit()
                        messagebox.showwarning("提示", "多次未匹配到目标图像，已尝试提交并停止点击")
                        self.stop_script()
                
        except Exception as e:
            messagebox.showerror("错误", f"运行出错: {str(e)}")
            self.stop_script()
    
    def on_closing(self):
        """窗口关闭事件处理"""
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1)
        self.root.destroy()
        sys.exit()
        
    def click_submit(self):
        """点击提交按钮"""
        self.submit_btn_url = "src/icon/submit.png"
        self.submit_btn_image = cv2.imread(self.submit_btn_url)
        target_height, target_width = self.submit_btn_image.shape[:2]

        screenshot = pyautogui.screenshot()
        screenshot = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
        
        result = cv2.matchTemplate(screenshot, self.submit_btn_image, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        
        threshold = 0.8
        if max_val >= threshold:
            top_left = max_loc
            center_x = top_left[0] + target_width // 2
            center_y = top_left[1] + target_height // 2
            pyautogui.moveTo(center_x, center_y)
            pyautogui.click()


def init_color():
    color_list = [
        "black", "darkgray", "gray", "mediumgray", "lightgray", "white",
        "deepred", "darkred", "red", "lightred", "darkorange", "orange",
        "gold", "yellow", "lightyellow", "darkgoldenrod", "goldenrod",
        "lightgoldenrod", "darkolive", "olive", "lightolive", "darkgreen",
        "green", "lightgreen", "darkteal", "teal", "lightteal", "darkcyan",
        "cyan", "lightcyan", "darkblue", "blue", "lightblue", "darkindigo",
        "indigo", "lightindigo", "darkslateblue", "slateblue", "lightslateblue",
        "darkpurple", "purple", "lightpurple", "darkpink", "pink", "lightpink",
        "darkpeach", "peach", "lightpeach", "darkbrown", "brown", "lightbrown",
        "darktan", "tan", "lighttan", "darkbeige", "beige", "lightbeige",
        "darkstone", "stone", "lightstone", "darkslate", "slate", "lightslate"
    ]
    
    color_map = {}
    for color in color_list:
        color_map[color] = f'src/color/{color}.png'
    return color_map


if __name__ == "__main__":
    root = tk.Tk()
    app = AutoPainterApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
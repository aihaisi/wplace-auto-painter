import time
import os
import cv2
import numpy as np
import pyautogui
import keyboard
from tkinter import messagebox


class AutoPainter:
    """负责执行模板匹配并完成点击的逻辑。

    run 方法接受两个可调用对象：
    - target_path_getter(): 返回当前要寻找的目标图片路径（字符串）
    - running_getter(): 返回布尔值，表示是否继续运行
    """

    def __init__(self, click_offset_x=0, click_offset_y=0, threshold=0.8):
        self.click_offset_x = click_offset_x
        self.click_offset_y = click_offset_y
        self.threshold = threshold

    def run(self, target_path_getter, running_getter):
        current_path = None
        target_image = None

        try:
            while running_getter():
                # 检查 ESC（优先）
                if keyboard.is_pressed('esc'):
                    break

                # 如果目标路径发生变化或未加载目标图像，则尝试加载
                path = target_path_getter()
                if not path:
                    time.sleep(0.1)
                    continue

                if path != current_path:
                    current_path = path
                    if not os.path.exists(current_path):
                        messagebox.showerror("错误", f"无法找到目标图像: {current_path}")
                        return
                    target_image = cv2.imread(current_path)
                    if target_image is None:
                        messagebox.showerror("错误", f"无法加载目标图像: {current_path}")
                        return
                    target_height, target_width = target_image.shape[:2]

                # 截图并匹配
                screenshot = pyautogui.screenshot()
                screenshot = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

                result = cv2.matchTemplate(screenshot, target_image, cv2.TM_CCOEFF_NORMED)
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

                if max_val >= self.threshold:
                    top_left = max_loc
                    center_x = top_left[0] + target_width // 2 + self.click_offset_x
                    center_y = top_left[1] + target_height // 2 + self.click_offset_y
                    pyautogui.moveTo(center_x, center_y)
                    pyautogui.click()
                    print(f"点击位置: ({center_x}, {center_y})")

                # 小延迟以避免 CPU 飙升
                time.sleep(0.01)

        except Exception as e:
            # 在 GUI 环境下显示错误
            try:
                messagebox.showerror("错误", f"运行出错: {str(e)}")
            except Exception:
                print("运行出错:", e)

import time
import os
import cv2
import numpy as np
import pyautogui
import keyboard
from tkinter import messagebox
import color_tackle


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
        # 记录上一次找到的目标图像的 top-left 坐标 (x, y)
        # 下一次检测将从该位置开始按行优先（先向右再向下）选择下一个匹配
        self.last_found = None
        # 未匹配计数与阈值（用于自动提交）
        self.unmatched_count = 0
        self.unmatched_threshold = 50

    def run(self, target_path_getter, running_getter):
        current_path = None
        target_image = None

        try:
            while running_getter():
                # 优先响应 ESC
                if keyboard.is_pressed('esc'):
                    break

                # 获取目标路径并在必要时加载图像
                path = target_path_getter()
                if not path:
                    time.sleep(0.1)
                    continue

                if path != current_path:
                    current_path = path
                    target_image = self._load_target_image(current_path)
                    if target_image is None:
                        return
                    # 目标图片变了，重置上次位置
                    self.last_found = None

                # 截图
                screenshot = self._screenshot()

                # 查找匹配项
                matches = self._get_matches(screenshot, target_image)

                if matches:
                    # 选择下一个匹配并点击
                    next_match = self._select_next_match(matches)
                    top_left = (next_match[0], next_match[1])
                    # 点击；如果中途停止则退出 run
                    self._click(top_left, target_image)
                    # 找到匹配则重置未匹配计数
                    self.unmatched_count = 0
                else:
                    # 没有匹配，重置上次位置以便下次从头开始
                    self.last_found = None
                    # 未匹配计数递增，超出阈值则尝试点击提交按钮并停止
                    self.unmatched_count += 1
                    if self.unmatched_count > self.unmatched_threshold:
                        try:
                            color_tackle.click_submit()
                        except Exception:
                            # 如果外部模块不可用或执行失败，仍然优雅地停止
                            pass
                        try:
                            messagebox.showwarning("提示", "多次未匹配到目标图像，已尝试提交并停止点击")
                        except Exception:
                            print("多次未匹配到目标图像，已尝试提交并停止点击")
                        return

                # 小延迟以避免 CPU 飙升
                time.sleep(0.01)

        except Exception as e:
            # 在 GUI 环境下显示错误
            try:
                messagebox.showerror("错误", f"运行出错: {str(e)}")
            except Exception:
                print("运行出错:", e)

    def _load_target_image(self, path):
        """加载目标图像并做基本校验，失败时在 GUI 报错并返回 None。"""
        if not os.path.exists(path):
            messagebox.showerror("错误", f"无法找到目标图像: {path}")
            return None
        target_image = cv2.imread(path)
        if target_image is None:
            messagebox.showerror("错误", f"无法加载目标图像: {path}")
            return None
        return target_image

    def _screenshot(self):
        shot = pyautogui.screenshot()
        return cv2.cvtColor(np.array(shot), cv2.COLOR_RGB2BGR)

    def _get_matches(self, screenshot, target_image):
        """返回匹配列表 [(x,y,score), ...]，未排序。"""
        result = cv2.matchTemplate(screenshot, target_image, cv2.TM_CCOEFF_NORMED)
        ys, xs = np.where(result >= self.threshold)
        matches = []
        for x, y in zip(xs, ys):
            matches.append((int(x), int(y), float(result[y, x])))
        return matches

    def _select_next_match(self, matches):
        """按行优先从 matches 中选择下一个要点击的项，并更新 self.last_found。

        matches: list of (x,y,score)，未排序。
        返回选中的 (x,y,score)
        """
        # 按行优先排序（先 y 再 x）
        matches.sort(key=lambda t: (t[1], t[0]))
        next_match = None
        if self.last_found is None:
            next_match = matches[0]
        else:
            lx, ly = self.last_found
            same_row = [m for m in matches if m[1] == ly and m[0] > lx]
            if same_row:
                next_match = min(same_row, key=lambda t: t[0])
            else:
                below = [m for m in matches if m[1] > ly]
                if below:
                    min_y = min(m[1] for m in below)
                    row = [m for m in below if m[1] == min_y]
                    next_match = min(row, key=lambda t: t[0])
                else:
                    next_match = matches[0]

        # 更新 last_found 为所选项的 top-left
        self.last_found = (next_match[0], next_match[1])
        return next_match

    def _click(self, top_left, target_image):
        """在 top_left 所在位置执行一次点击。"""
        target_height, target_width = target_image.shape[:2]
        center_x = top_left[0] + target_width // 2 + self.click_offset_x
        center_y = top_left[1] + target_height // 2 + self.click_offset_y
        pyautogui.moveTo(center_x, center_y)
        pyautogui.click()
        print(f"点击位置: ({center_x}, {center_y})")


"""入口脚本（launcher）。

现在 GUI 和 自动绘制逻辑已拆分到包中：
- src.data.load_color_map()
- src.gui.AutoPainterApp
"""
import tkinter as tk
from src.data import load_color_map
from src.gui import AutoPainterApp


def main():
    color_map = load_color_map()
    root = tk.Tk()
    app = AutoPainterApp(root, color_map)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()
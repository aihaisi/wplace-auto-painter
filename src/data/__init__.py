import json
import os

__all__ = ["load_color_map"]


def load_color_map():
    """加载 colors.json 并返回一个映射 color_name -> src/color/<color>.png"""
    here = os.path.dirname(__file__)
    path = os.path.join(here, "colors.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            colors = json.load(f)
    except Exception:
        colors = []

    color_map = {}
    for c in colors:
        color_map[c] = os.path.join("src", "color", f"{c}.png")
    return color_map

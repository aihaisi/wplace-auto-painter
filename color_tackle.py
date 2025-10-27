import pyautogui
import keyboard
import cv2
import numpy as np

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

def run_script(target_image_path):
    
    running = True
    
    click_offset_x = 0
    click_offset_y = 0
    
    unmatched_times = 0
    
    try:
        target_image = cv2.imread(target_image_path) 
        target_height, target_width = target_image.shape[:2]
        
        while running:

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
                unmatched_times = 0  # 重置未匹配计数
                print(f"点击位置: ({center_x}, {center_y})")
            else:
                unmatched_times += 1
                if unmatched_times > 50: 
                    click_submit()
                    print("多次未匹配到目标图像，已尝试提交并停止点击。")
                    running = False

    except Exception as e:
        print(f"Error: {str(e)}")


def click_submit():
    """点击提交按钮"""
    submit_btn_url = "src/icon/submit.png"
    submit_btn_image = cv2.imread(submit_btn_url)
    target_height, target_width = submit_btn_image.shape[:2]

    screenshot = pyautogui.screenshot()
    screenshot = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
    
    result = cv2.matchTemplate(screenshot, submit_btn_image, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

    
    threshold = 0.8
    if max_val >= threshold:
        top_left = max_loc
        center_x = top_left[0] + target_width // 2
        center_y = top_left[1] + target_height // 2
        pyautogui.moveTo(center_x, center_y)
        pyautogui.click()
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

import pyautogui

from services.config_manager import get_config


def _clamp_region(region: tuple) -> Optional[Tuple[int, int, int, int]]:
    try:
        left, top, width, height = region
    except Exception:
        return None

    if width <= 0 or height <= 0:
        return None

    screen_w, screen_h = pyautogui.size()
    right = min(screen_w, left + width)
    bottom = min(screen_h, top + height)
    left = max(0, left)
    top = max(0, top)

    new_w = right - left
    new_h = bottom - top
    if new_w <= 0 or new_h <= 0:
        return None

    return (left, top, new_w, new_h)


def _save_region(region: tuple, label: str) -> Optional[Path]:
    region = _clamp_region(region)
    if not region:
        return None

    debug_dir = Path(get_config("ui_location.dots_debug_dir", "./data/debug"))
    debug_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"{label}_{ts}_{region[0]}_{region[1]}_{region[2]}_{region[3]}.png"
    path = debug_dir / filename
    img = pyautogui.screenshot(region=region)
    img.save(path)
    return path


def main() -> None:
    x = get_config("display.sns_window.x", 0)
    y = get_config("display.sns_window.y", 0)
    w = get_config("display.sns_window.width", 0)
    h = get_config("display.sns_window.height", 0)
    if not w or not h:
        print("display.sns_window not configured.")
        return

    rect = (x, y, w, h)

    box_w = get_config("ui_location.dots_image_bottom_box_width", 260)
    box_h = get_config("ui_location.dots_image_bottom_box_height", 220)
    box_right_pad = get_config("ui_location.dots_image_bottom_box_right_pad", 40)
    box_bottom_pad = get_config("ui_location.dots_image_bottom_box_bottom_pad", 120)
    bottom_box = (
        rect[0] + rect[2] - int(box_right_pad) - int(box_w),
        rect[1] + rect[3] - int(box_bottom_pad) - int(box_h),
        int(box_w),
        int(box_h),
    )

    right_strip = get_config("ui_location.dots_image_search_width", 140)
    top_pad = get_config("ui_location.dots_image_search_top_pad", 120)
    bottom_pad = get_config("ui_location.dots_image_search_bottom_pad", 160)
    right_strip_region = (
        rect[0] + rect[2] - int(right_strip),
        rect[1] + int(top_pad),
        int(right_strip),
        max(10, rect[3] - int(top_pad) - int(bottom_pad)),
    )

    saved = []
    for label, region in (("dots_bottom_box", bottom_box), ("dots_right_strip", right_strip_region)):
        path = _save_region(region, label)
        if path:
            saved.append(path)

    if saved:
        print("Saved:")
        for p in saved:
            print(f"  {p}")
    else:
        print("No regions saved (invalid region or config).")


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
import io
import re
import logging
import datetime
from datetime import datetime
from typing import Literal, Iterable, List, Optional, Tuple
import streamlit as st

from KiroshiApp.models import ScreenshotAsset, InMemoryUploadedFile
from KiroshiApp.utils import sanitize_filename, _utc_now_z

# GUI Dependencies with fallbacks
try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except Exception:
    pyautogui = None
    PYAUTOGUI_AVAILABLE = False

try:
    import tkinter as tk
    TK_AVAILABLE = True
except Exception:
    tk = None
    TK_AVAILABLE = False

try:
    from PIL import ImageGrab
    IMAGEGRAB_AVAILABLE = True
except Exception:
    ImageGrab = None
    IMAGEGRAB_AVAILABLE = False

try:
    import mss
    MSS_AVAILABLE = True
except Exception:
    mss = None
    MSS_AVAILABLE = False

class ScreenshotService:
    """State-aware manager that owns screenshot capture and hydration logic."""

    def __init__(self, *, state_key: str = "screenshots") -> None:
        self.state_key = state_key

    @staticmethod
    def _queue_screenshot_upload(asset: ScreenshotAsset) -> None:
        """Create an upload entry for ``asset`` so evidence queues stay in sync."""
        uploads = st.session_state.get("uploads")
        if isinstance(uploads, list):
            target = uploads
        else:
            target = []
            st.session_state["uploads"] = target

        staged = InMemoryUploadedFile(asset.name, asset.getvalue())
        target.append(staged)

    def _coerce(self, items: Iterable[object]) -> List[ScreenshotAsset]:
        normalised: List[ScreenshotAsset] = []
        for item in items:
            asset = _ensure_screenshot_asset(item)
            if asset is not None:
                normalised.append(asset)
        return normalised

    def replace(self, items: Iterable[object]) -> List[ScreenshotAsset]:
        normalised = self._coerce(items)
        st.session_state[self.state_key] = normalised
        return normalised

    def assets(self) -> List[ScreenshotAsset]:
        existing = st.session_state.get(self.state_key, [])
        if isinstance(existing, list):
            return self.replace(existing)
        return self.replace([])

    def append(self, asset: ScreenshotAsset) -> List[ScreenshotAsset]:
        assets = list(self.assets())
        assets.append(asset)
        st.session_state[self.state_key] = assets
        return assets

    def clear(self) -> None:
        st.session_state[self.state_key] = []

    def capture_from_ui(
        self,
        mode: Literal["full", "region"],
        *,
        label: str,
        auto_stamp: bool,
        label_state_key: str,
        reset_flag_key: str | None = None,
    ) -> None:
        existing = self.assets()
        safe_stem, display_label = _generate_screenshot_basename(
            label, auto_stamp=auto_stamp, existing=existing
        )
        capture_fn = self.capture_full if mode == "full" else self.capture_region
        shot, error = capture_fn(safe_stem, label=display_label)
        if shot:
            shot.capture_mode = mode
            shot.origin = "capture"
            self.append(shot)
            self._queue_screenshot_upload(shot)
            st.success(f"Captured {mode} screenshot: {shot.label}")
            if reset_flag_key:
                st.session_state[reset_flag_key] = True
            return

        if not error:
            st.warning("Screenshot capture is unavailable in this environment.")
            return

        message = error.strip()
        if "cancel" in message.lower():
            st.info("Screenshot capture cancelled.")
        elif "environment" in message.lower():
            st.warning(message)
        else:
            st.error(message)

    def capture_region(
        self,
        safe_name: str,
        *,
        label: str | None = None,
    ) -> Tuple[Optional[ScreenshotAsset], Optional[str]]:
        if tk is None or not TK_AVAILABLE:
            return None, (
                "Advanced screenshot selection requires a local display with Tkinter support in this environment."
            )

        if not (PYAUTOGUI_AVAILABLE or IMAGEGRAB_AVAILABLE or MSS_AVAILABLE):
            return None, "Screenshot capture is unavailable in this environment."

        coords, error = select_screen_region()
        if not coords:
            return None, error

        left, top, width, height = coords
        if width <= 0 or height <= 0:
            return None, "No region was selected."

        img = None
        if PYAUTOGUI_AVAILABLE and pyautogui is not None:
            try:
                img = pyautogui.screenshot(
                    region=(left, top, width, height)
                )
            except Exception as exc:
                logging.warning("pyautogui region capture failed: %s", exc)

        if img is None and IMAGEGRAB_AVAILABLE and ImageGrab is not None:
            try:
                img = ImageGrab.grab(bbox=(left, top, left + width, top + height))
            except Exception as exc:
                logging.error("ImageGrab region capture failed: %s", exc)
                return None, "Unable to capture the selected region."

        if img is None and MSS_AVAILABLE and mss is not None:
            try:
                with mss.mss() as sct:
                    monitor = sct.monitors[0]
                    raw = sct.grab(monitor)
                from PIL import Image as PILImage

                img = PILImage.frombytes("RGB", raw.size, raw.rgb)
                crop_box = (
                    left - monitor.get("left", 0),
                    top - monitor.get("top", 0),
                    left - monitor.get("left", 0) + width,
                    top - monitor.get("top", 0) + height,
                )
                img = img.crop(crop_box)
            except Exception as exc:
                logging.error("mss region capture failed: %s", exc)
                return None, "Unable to capture the selected region."

        if img is None:
            return None, "Unable to capture the selected region."

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return (
            ScreenshotAsset(
                name=f"{safe_name}.png",
                data=buf.getvalue(),
                label=label or safe_name,
                capture_mode="region",
            ),
            None,
        )

    def capture_full(
        self,
        safe_name: str,
        *,
        label: str | None = None,
    ) -> Tuple[Optional[ScreenshotAsset], Optional[str]]:
        img = None
        if PYAUTOGUI_AVAILABLE and pyautogui is not None:
            try:
                img = pyautogui.screenshot()
            except Exception as exc:
                logging.warning("pyautogui full capture failed: %s", exc)

        if img is None and IMAGEGRAB_AVAILABLE and ImageGrab is not None:
            try:
                img = ImageGrab.grab()
            except Exception as exc:
                logging.warning("ImageGrab full capture failed: %s", exc)

        if img is None and MSS_AVAILABLE and mss is not None:
            try:
                with mss.mss() as sct:
                    monitor = sct.monitors[0]
                    raw = sct.grab(monitor)
                from PIL import Image as PILImage

                img = PILImage.frombytes("RGB", raw.size, raw.rgb)
            except Exception as exc:
                logging.error("mss full capture failed: %s", exc)

        if img is None:
            return None, (
                "Screenshot capture is unavailable in this environment. "
                "For Windows deployments, ensure the exe includes Pillow, pyautogui, or mss."
            )

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return (
            ScreenshotAsset(
                name=f"{safe_name}.png",
                data=buf.getvalue(),
                label=label or safe_name,
                capture_mode="full",
            ),
            None,
        )

def _ensure_screenshot_asset(item: object) -> Optional[ScreenshotAsset]:
    """Coerce legacy screenshot payloads into :class:`ScreenshotAsset`."""
    if isinstance(item, ScreenshotAsset):
        return item
    if isinstance(item, InMemoryUploadedFile):
        label = getattr(item, "label", "") or getattr(item, "name", "")
        return ScreenshotAsset(
            name=getattr(item, "name", "screenshot"),
            data=getattr(item, "data", b""),
            label=str(label),
            capture_mode=getattr(item, "capture_mode", "imported"),
            origin=getattr(item, "origin", "legacy"),
        )
    return None

def _generate_screenshot_basename(
    label: str,
    *,
    auto_stamp: bool,
    existing: Iterable[ScreenshotAsset],
) -> Tuple[str, str]:
    """Return a sanitized filename stem and display label for the next capture."""
    raw_label = label.strip()
    display_label = raw_label or f"Capture {len(list(existing)) + 1}"
    safe_stem = re.sub(r"[^A-Za-z0-9_-]+", "_", raw_label).strip("_").lower()
    if not safe_stem:
        safe_stem = re.sub(r"[^A-Za-z0-9_-]+", "_", display_label).strip("_").lower()
    if not safe_stem:
        safe_stem = "capture"
    if auto_stamp:
        safe_stem = f"{safe_stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    # Simple uniqueness check could be added here if needed
    return safe_stem, display_label

def select_screen_region() -> Tuple[Optional[Tuple[int, int, int, int]], Optional[str]]:
    """Launch a temporary overlay that lets the user select a screen region."""
    if not TK_AVAILABLE or tk is None:
        return None, "Region selection requires a graphical environment."

    try:
        root = tk.Tk()
    except Exception as exc:
        logging.warning("Unable to initialize Tkinter for region capture: %s", exc)
        return None, "Region selection is unavailable in this environment."

    selection = {"start": None, "coords": None, "cancelled": False}

    try:
        root.attributes("-topmost", True)
    except Exception:
        pass
    try:
        root.attributes("-fullscreen", True)
    except Exception:
        width = root.winfo_screenwidth()
        height = root.winfo_screenheight()
        root.geometry(f"{width}x{height}+0+0")
    try:
        root.attributes("-alpha", 0.2)
    except Exception:
        root.configure(bg="#000000")
    try:
        root.overrideredirect(True)
    except Exception:
        pass

    canvas = tk.Canvas(root, bg="#000000", highlightthickness=0, cursor="crosshair")
    canvas.pack(fill=tk.BOTH, expand=True)

    root.update_idletasks()
    canvas.create_text(
        root.winfo_screenwidth() // 2,
        40,
        text="Click and drag to select the area to capture. Press Esc to cancel.",
        fill="white",
        font=("Helvetica", 14),
    )

    rect_id = None

    def canvas_coords(x_root, y_root):
        return x_root - root.winfo_rootx(), y_root - root.winfo_rooty()

    def on_button_press(event):
        nonlocal rect_id
        selection["start"] = (event.x_root, event.y_root)
        if rect_id is not None:
            canvas.delete(rect_id)
        cx, cy = canvas_coords(event.x_root, event.y_root)
        rect_id = canvas.create_rectangle(cx, cy, cx, cy, outline="red", width=2)

    def on_mouse_move(event):
        if selection["start"] is None or rect_id is None:
            return
        start_x, start_y = selection["start"]
        cx0, cy0 = canvas_coords(start_x, start_y)
        cx1, cy1 = canvas_coords(event.x_root, event.y_root)
        canvas.coords(rect_id, cx0, cy0, cx1, cy1)

    def on_button_release(event):
        start = selection["start"]
        if not isinstance(start, tuple):
            return
        end = (event.x_root, event.y_root)
        left = min(start[0], end[0])
        top = min(start[1], end[1])
        width = abs(end[0] - start[0])
        height = abs(end[1] - start[1])
        if width > 1 and height > 1:
            selection["coords"] = (int(left), int(top), int(width), int(height))
        else:
            selection["coords"] = None
        root.quit()

    def on_cancel(event=None):
        selection["cancelled"] = True
        root.quit()

    canvas.bind("<ButtonPress-1>", on_button_press)
    canvas.bind("<B1-Motion>", on_mouse_move)
    canvas.bind("<ButtonRelease-1>", on_button_release)
    root.bind("<Escape>", on_cancel)
    root.protocol("WM_DELETE_WINDOW", on_cancel)

    try:
        root.mainloop()
    finally:
        try:
            root.destroy()
        except Exception:
            pass

    if selection.get("cancelled"):
        return None, "Region selection cancelled."

    coords = selection.get("coords")
    if not isinstance(coords, tuple):
        return None, "No region was selected."
    return coords, None

_screenshot_service = ScreenshotService()

def capture_region_screenshot(safe_name: str, label: str | None = None) -> Tuple[Optional[ScreenshotAsset], Optional[str]]:
    return _screenshot_service.capture_region(safe_name, label=label)

def capture_full_screenshot(safe_name: str, label: str | None = None) -> Tuple[Optional[ScreenshotAsset], Optional[str]]:
    return _screenshot_service.capture_full(safe_name, label=label)

def get_active_screenshots() -> List[ScreenshotAsset]:
    return _screenshot_service.assets()

def set_active_screenshots(items: Iterable[object]) -> List[ScreenshotAsset]:
    return _screenshot_service.replace(items)

def clear_active_screenshots() -> None:
    _screenshot_service.clear()

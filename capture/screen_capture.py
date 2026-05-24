"""
Screen Capture System
=====================
Ultra-fast screen capture using MSS library.
Captures the game screen and provides numpy arrays for YOLO detection.
Runs in its own thread with a shared frame buffer.
"""

import time
import threading
import numpy as np
import cv2
import mss
from utils.logger import get_logger

logger = get_logger("capture")


class ScreenCapture:
    """
    Fast screen capture system using MSS.

    Captures the game screen at high FPS and stores the latest frame
    in a thread-safe buffer for other systems to consume.
    """

    def __init__(self, config: dict):
        """
        Initialize the screen capture system.

        Args:
            config: Capture configuration dict with keys:
                - monitor (int): Monitor index (1-based)
                - region (dict|None): Custom region {left, top, width, height}
                - fps (int): Target capture FPS
        """
        self.monitor_index = config.get("monitor", 1)
        self.region = config.get("region", None)
        self.target_fps = config.get("fps", 60)
        self.frame_interval = 1.0 / self.target_fps
        self.capture_method = config.get("method", "pil")  # Default to PIL for dual-GPU/hybrid stability

        # Thread-safe frame buffer
        self._frame = None
        self._frame_lock = threading.Lock()
        self._frame_count = 0
        self._fps = 0.0
        self._fps_timer = time.time()
        self._fps_count = 0

        # Thread control
        self._running = False
        self._thread = None

        logger.info(f"ScreenCapture initialized | Method: {self.capture_method.upper()} | Monitor: {self.monitor_index} | Target FPS: {self.target_fps}")

    @property
    def frame(self) -> np.ndarray:
        """Get the latest captured frame (thread-safe)."""
        with self._frame_lock:
            return self._frame.copy() if self._frame is not None else None

    @property
    def fps(self) -> float:
        """Get current capture FPS."""
        return self._fps

    @property
    def frame_count(self) -> int:
        """Get total captured frame count."""
        return self._frame_count

    def _get_monitor_region(self, sct: mss.mss) -> dict:
        """
        Get the monitor region to capture.

        Args:
            sct: MSS instance

        Returns:
            Monitor region dict
        """
        if self.region:
            return self.region

        # Use specified monitor
        monitors = sct.monitors
        if self.monitor_index < len(monitors):
            return monitors[self.monitor_index]
        else:
            logger.warning(f"Monitor {self.monitor_index} not found, using primary monitor")
            return monitors[1] if len(monitors) > 1 else monitors[0]

    def _capture_loop(self):
        """Main capture loop — runs in a separate thread."""
        logger.info("Capture thread started")

        with mss.mss() as sct:
            monitor = self._get_monitor_region(sct)
            logger.info(f"Capturing region: {monitor}")

            while self._running:
                loop_start = time.time()

                try:
                    # Capture screenshot
                    screenshot = sct.grab(monitor)

                    # Convert to numpy array (BGRA -> BGR)
                    frame = np.array(screenshot)
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

                    # Store frame thread-safely
                    with self._frame_lock:
                        self._frame = frame
                        self._frame_count += 1

                    # Calculate FPS
                    self._fps_count += 1
                    elapsed = time.time() - self._fps_timer
                    if elapsed >= 1.0:
                        self._fps = self._fps_count / elapsed
                        self._fps_count = 0
                        self._fps_timer = time.time()

                except Exception as e:
                    logger.error(f"Capture error: {e}")
                    time.sleep(0.1)

                # Frame rate limiting
                elapsed = time.time() - loop_start
                sleep_time = self.frame_interval - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)

        logger.info("Capture thread stopped")

    def start(self):
        """Start the capture thread."""
        if self._running:
            logger.warning("Capture already running")
            return

        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True, name="CaptureThread")
        self._thread.start()
        logger.info("Capture system started")

    def stop(self):
        """Stop the capture thread."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        self._thread = None
        logger.info("Capture system stopped")

    def get_frame_for_detection(self) -> np.ndarray:
        """
        Get the current frame optimized for YOLO detection.
        Returns a copy of the latest frame, or None if no frame available.
        """
        return self.frame

    def save_screenshot(self, path: str = "screenshot.png") -> bool:
        """
        Save the current frame as an image file.

        Args:
            path: Output file path

        Returns:
            True if saved successfully
        """
        frame = self.frame
        if frame is not None:
            cv2.imwrite(path, frame)
            logger.info(f"Screenshot saved: {path}")
            return True
        logger.warning("No frame available to save")
        return False

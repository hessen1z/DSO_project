"""
Humanizer System
================
Makes bot actions look human-like with:
- Bézier curve mouse movements
- Random delays between actions
- Slight position offsets on clicks
- Variable typing speeds
"""

import time
import random
import math
import pyautogui
from utils.logger import get_logger

logger = get_logger("humanizer")

# Disable pyautogui's built-in pause and failsafe for speed
pyautogui.PAUSE = 0
pyautogui.FAILSAFE = True  # Keep failsafe (move mouse to corner to abort)


class Humanizer:
    """
    Makes bot inputs look natural and human-like.
    All mouse and keyboard actions should go through this class.
    """

    def __init__(self, config: dict):
        """
        Initialize the humanizer.

        Args:
            config: Humanizer configuration dict with keys:
                - enabled (bool): Enable/disable humanization
                - min_delay (float): Minimum delay between actions
                - max_delay (float): Maximum delay between actions
                - mouse_curve (bool): Use Bézier curves for mouse movement
                - mouse_speed (float): Base mouse movement speed (seconds)
                - click_offset (int): Max random pixel offset on clicks
                - typing_min_delay (float): Min delay between key presses
                - typing_max_delay (float): Max delay between key presses
        """
        self.enabled = config.get("enabled", True)
        self.min_delay = config.get("min_delay", 0.05)
        self.max_delay = config.get("max_delay", 0.2)
        self.mouse_curve = config.get("mouse_curve", True)
        self.mouse_speed = config.get("mouse_speed", 0.3)
        self.click_offset = config.get("click_offset", 3)
        self.typing_min_delay = config.get("typing_min_delay", 0.02)
        self.typing_max_delay = config.get("typing_max_delay", 0.08)

        logger.info(f"Humanizer initialized | Enabled: {self.enabled} | Curves: {self.mouse_curve}")

    def _random_delay(self, min_d: float = None, max_d: float = None):
        """Add a random delay between actions."""
        if not self.enabled:
            return
        min_d = min_d or self.min_delay
        max_d = max_d or self.max_delay
        delay = random.uniform(min_d, max_d)
        time.sleep(delay)

    def _add_offset(self, x: int, y: int) -> tuple:
        """Add slight random offset to coordinates."""
        if not self.enabled or self.click_offset <= 0:
            return x, y
        ox = random.randint(-self.click_offset, self.click_offset)
        oy = random.randint(-self.click_offset, self.click_offset)
        return x + ox, y + oy

    def _bezier_point(self, t: float, p0: tuple, p1: tuple, p2: tuple, p3: tuple) -> tuple:
        """Calculate a point on a cubic Bézier curve."""
        u = 1 - t
        return (
            int(u**3 * p0[0] + 3 * u**2 * t * p1[0] + 3 * u * t**2 * p2[0] + t**3 * p3[0]),
            int(u**3 * p0[1] + 3 * u**2 * t * p1[1] + 3 * u * t**2 * p2[1] + t**3 * p3[1])
        )

    def _generate_curve_points(self, start: tuple, end: tuple, num_points: int = 20) -> list:
        """
        Generate points along a Bézier curve from start to end.

        Args:
            start: Starting (x, y) position
            end: Ending (x, y) position
            num_points: Number of intermediate points

        Returns:
            List of (x, y) points along the curve
        """
        # Calculate distance for control point spread
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        dist = math.sqrt(dx**2 + dy**2)
        spread = max(50, dist * 0.3)

        # Random control points for natural curve
        cp1 = (
            start[0] + dx * 0.25 + random.uniform(-spread, spread) * 0.3,
            start[1] + dy * 0.25 + random.uniform(-spread, spread) * 0.3
        )
        cp2 = (
            start[0] + dx * 0.75 + random.uniform(-spread, spread) * 0.3,
            start[1] + dy * 0.75 + random.uniform(-spread, spread) * 0.3
        )

        points = []
        for i in range(num_points + 1):
            t = i / num_points
            point = self._bezier_point(t, start, cp1, cp2, end)
            points.append(point)

        return points

    def move_mouse(self, x: int, y: int, speed: float = None):
        """
        Move mouse to position with optional Bézier curve.

        Args:
            x: Target X position
            y: Target Y position
            speed: Movement speed in seconds (None = use default)
        """
        speed = speed or self.mouse_speed

        if self.enabled and self.mouse_curve:
            # Get current position
            current = pyautogui.position()
            start = (current.x, current.y)
            end = (x, y)

            # Calculate distance for adaptive speed
            dx = end[0] - start[0]
            dy = end[1] - start[1]
            dist = math.sqrt(dx**2 + dy**2)

            # Skip curve for very short distances
            if dist < 10:
                pyautogui.moveTo(x, y)
                return

            # Adaptive number of points based on distance
            num_points = max(10, min(40, int(dist / 15)))

            # Generate curve
            points = self._generate_curve_points(start, end, num_points)

            # Move along curve
            step_delay = speed / num_points
            for px, py in points:
                pyautogui.moveTo(px, py)
                time.sleep(step_delay * random.uniform(0.5, 1.5))
        else:
            pyautogui.moveTo(x, y, duration=speed if self.enabled else 0)

    def click(self, x: int = None, y: int = None, button: str = "left", clicks: int = 1):
        """
        Click at position with humanized behavior.

        Args:
            x: X position (None = current position)
            y: Y position (None = current position)
            button: Mouse button ('left', 'right', 'middle')
            clicks: Number of clicks
        """
        if x is not None and y is not None:
            # Add offset for human-like targeting
            tx, ty = self._add_offset(x, y)
            self.move_mouse(tx, ty)
            self._random_delay(0.02, 0.08)

        pyautogui.click(button=button, clicks=clicks)

        # Small delay after click
        self._random_delay(0.02, 0.05)

    def right_click(self, x: int = None, y: int = None):
        """Right-click at position."""
        self.click(x, y, button="right")

    def press_key(self, key: str):
        """
        Press a key with humanized timing.

        Args:
            key: Key to press (e.g., '1', 'f1', 'space')
        """
        self._random_delay(0.01, 0.04)
        pyautogui.press(key)
        self._random_delay(0.02, 0.06)

    def hold_key(self, key: str, duration: float = 0.5):
        """
        Hold a key for a duration.

        Args:
            key: Key to hold
            duration: Hold duration in seconds
        """
        if self.enabled:
            duration += random.uniform(-0.05, 0.1)
            duration = max(0.1, duration)

        pyautogui.keyDown(key)
        time.sleep(duration)
        pyautogui.keyUp(key)
        self._random_delay()

    def type_text(self, text: str):
        """
        Type text with human-like delays between characters.

        Args:
            text: Text to type
        """
        for char in text:
            pyautogui.press(char)
            if self.enabled:
                delay = random.uniform(self.typing_min_delay, self.typing_max_delay)
                time.sleep(delay)

    def random_movement(self, center_x: int, center_y: int, radius: int = 100):
        """
        Make a random movement near a position (for anti-stuck).

        Args:
            center_x: Center X position
            center_y: Center Y position
            radius: Maximum radius of random movement
        """
        angle = random.uniform(0, 2 * math.pi)
        dist = random.uniform(20, radius)
        target_x = int(center_x + dist * math.cos(angle))
        target_y = int(center_y + dist * math.sin(angle))

        self.click(target_x, target_y)
        logger.debug(f"Random movement to ({target_x}, {target_y})")

    def delay(self, min_d: float = None, max_d: float = None):
        """Public delay method for external use."""
        self._random_delay(min_d, max_d)

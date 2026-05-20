"""
YOLO Detection System
=====================
YOLOv8-based object detection for game elements.
Detects enemies, loot, portals, NPCs, HP bars, death screens, etc.
Runs in its own thread at a lower FPS than capture.
"""

import time
import threading
import os
import numpy as np
from utils.logger import get_logger

logger = get_logger("detection")


class Detection:
    """Represents a single detection result."""

    def __init__(self, class_name: str, confidence: float, bbox: tuple, class_id: int = -1):
        """
        Args:
            class_name: Detected class name (e.g., 'enemy', 'loot')
            confidence: Detection confidence (0-1)
            bbox: Bounding box (x1, y1, x2, y2)
            class_id: Class ID from the model
        """
        self.class_name = class_name
        self.confidence = confidence
        self.bbox = bbox  # (x1, y1, x2, y2)
        self.class_id = class_id

        # Calculate center point
        self.center_x = int((bbox[0] + bbox[2]) / 2)
        self.center_y = int((bbox[1] + bbox[3]) / 2)

        # Calculate dimensions
        self.width = int(bbox[2] - bbox[0])
        self.height = int(bbox[3] - bbox[1])

    @property
    def area(self) -> int:
        """Get bounding box area."""
        return self.width * self.height

    def distance_to(self, x: int, y: int) -> float:
        """Calculate distance from center to a point."""
        import math
        return math.sqrt((self.center_x - x) ** 2 + (self.center_y - y) ** 2)

    def __repr__(self):
        return (f"Detection({self.class_name}, conf={self.confidence:.2f}, "
                f"center=({self.center_x},{self.center_y}), "
                f"size={self.width}x{self.height})")


class YOLODetector:
    """
    YOLOv8 detection wrapper for game element detection.

    Supports custom-trained models for game-specific classes.
    Falls back to pre-trained model if custom model not found.
    """

    # Default class mapping for custom trained model
    DEFAULT_CLASSES = [
        "enemy", "elite", "boss", "loot", "portal",
        "npc", "dead_screen", "hp_bar", "inventory_full"
    ]

    def __init__(self, config: dict):
        """
        Initialize the YOLO detector.

        Args:
            config: Detection configuration dict with keys:
                - model_path (str): Path to custom YOLO model
                - fallback_model (str): Fallback model name
                - confidence (float): Minimum confidence threshold
                - detection_fps (int): Target detection FPS
                - classes (list): Class names
        """
        self.model_path = config.get("model_path", "detection/models/best.pt")
        self.fallback_model = config.get("fallback_model", "yolov8n.pt")
        self.confidence = config.get("confidence", 0.5)
        self.target_fps = config.get("detection_fps", 10)
        self.frame_interval = 1.0 / self.target_fps
        self.class_names = config.get("classes", self.DEFAULT_CLASSES)

        # Model reference
        self.model = None
        self.model_loaded = False
        self.using_custom = False

        # Thread-safe detection results
        self._detections = []
        self._detections_lock = threading.Lock()
        self._detection_count = 0
        self._fps = 0.0
        self._fps_timer = time.time()
        self._fps_count = 0

        # Thread control
        self._running = False
        self._thread = None
        self._frame_source = None  # Callback to get frames

        # Load model
        self._load_model()

    def _load_model(self):
        """Load the YOLO model."""
        try:
            from ultralytics import YOLO

            # Try custom model first
            if os.path.exists(self.model_path):
                logger.info(f"Loading custom model: {self.model_path}")
                self.model = YOLO(self.model_path)
                self.using_custom = True
            else:
                logger.warning(f"Custom model not found: {self.model_path}")
                logger.info(f"Loading fallback model: {self.fallback_model}")
                self.model = YOLO(self.fallback_model)
                self.using_custom = False

            self.model_loaded = True
            logger.info(f"YOLO model loaded | Custom: {self.using_custom} | "
                        f"Confidence: {self.confidence} | Target FPS: {self.target_fps}")

        except ImportError:
            logger.error("ultralytics not installed! Run: pip install ultralytics")
            self.model_loaded = False
        except Exception as e:
            logger.error(f"Failed to load YOLO model: {e}")
            self.model_loaded = False

    @property
    def detections(self) -> list:
        """Get the latest detection results (thread-safe)."""
        with self._detections_lock:
            return self._detections.copy()

    @property
    def fps(self) -> float:
        """Get current detection FPS."""
        return self._fps

    def detect(self, frame: np.ndarray) -> list:
        """
        Run detection on a single frame.

        Args:
            frame: BGR numpy array from screen capture

        Returns:
            List of Detection objects
        """
        if not self.model_loaded or frame is None:
            return []

        try:
            # Run inference
            results = self.model(frame, conf=self.confidence, verbose=False)

            detections = []
            for result in results:
                if result.boxes is None:
                    continue

                for box in result.boxes:
                    # Get bounding box
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    confidence = float(box.conf[0].cpu().numpy())
                    class_id = int(box.cls[0].cpu().numpy())

                    # Get class name
                    if self.using_custom and class_id < len(self.class_names):
                        class_name = self.class_names[class_id]
                    else:
                        class_name = self.model.names.get(class_id, f"class_{class_id}")

                    detection = Detection(
                        class_name=class_name,
                        confidence=confidence,
                        bbox=(int(x1), int(y1), int(x2), int(y2)),
                        class_id=class_id
                    )
                    detections.append(detection)

            return detections

        except Exception as e:
            logger.error(f"Detection error: {e}")
            return []

    def _detection_loop(self):
        """Main detection loop — runs in a separate thread."""
        logger.info("Detection thread started")

        while self._running:
            loop_start = time.time()

            try:
                # Get frame from source
                frame = self._frame_source() if self._frame_source else None

                if frame is not None:
                    # Run detection
                    detections = self.detect(frame)

                    # Store results thread-safely
                    with self._detections_lock:
                        self._detections = detections
                        self._detection_count += 1

                    # Calculate FPS
                    self._fps_count += 1
                    elapsed = time.time() - self._fps_timer
                    if elapsed >= 1.0:
                        self._fps = self._fps_count / elapsed
                        self._fps_count = 0
                        self._fps_timer = time.time()

            except Exception as e:
                logger.error(f"Detection loop error: {e}")
                time.sleep(0.1)

            # Frame rate limiting
            elapsed = time.time() - loop_start
            sleep_time = self.frame_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

        logger.info("Detection thread stopped")

    def start(self, frame_source_callback):
        """
        Start the detection thread.

        Args:
            frame_source_callback: Callable that returns the latest frame (numpy array)
        """
        if not self.model_loaded:
            logger.error("Cannot start detection — model not loaded")
            return

        if self._running:
            logger.warning("Detection already running")
            return

        self._frame_source = frame_source_callback
        self._running = True
        self._thread = threading.Thread(target=self._detection_loop, daemon=True, name="DetectionThread")
        self._thread.start()
        logger.info("Detection system started")

    def stop(self):
        """Stop the detection thread."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        self._thread = None
        logger.info("Detection system stopped")

    def get_by_class(self, class_name: str) -> list:
        """
        Get all detections of a specific class.

        Args:
            class_name: Class name to filter

        Returns:
            List of Detection objects matching the class
        """
        return [d for d in self.detections if d.class_name == class_name]

    def get_nearest(self, class_name: str, ref_x: int = None, ref_y: int = None) -> Detection:
        """
        Get the nearest detection of a specific class.

        Args:
            class_name: Class name to search for
            ref_x: Reference X position (default: screen center)
            ref_y: Reference Y position (default: screen center)

        Returns:
            Nearest Detection object, or None
        """
        candidates = self.get_by_class(class_name)
        if not candidates:
            return None

        # Default to screen center
        if ref_x is None:
            ref_x = 960  # Assuming 1920x1080
        if ref_y is None:
            ref_y = 540

        return min(candidates, key=lambda d: d.distance_to(ref_x, ref_y))

    def has_detection(self, class_name: str) -> bool:
        """Check if any detection of a class exists."""
        return any(d.class_name == class_name for d in self.detections)

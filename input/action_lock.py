"""
Action Lock System
==================
Global mutex that prevents multiple bot systems (combat, navigation, loot, potion)
from sending conflicting keyboard/mouse inputs simultaneously.

Usage:
    lock = ActionLock()

    # In CombatSystem.execute():
    with lock.acquire("combat"):
        humanizer.press_key("1")
        humanizer.click(x, y)

    # If another system tries to acquire while combat holds it:
    with lock.acquire("navigation"):
        # This will wait until combat releases the lock
        humanizer.right_click(x, y)

The lock is reentrant within the same owner name, so a single system
can call nested actions without deadlocking.
"""

import time
import threading
from contextlib import contextmanager
from utils.logger import get_logger

logger = get_logger("action_lock")


class ActionLock:
    """
    Thread-safe global action lock to serialize bot input actions.

    Only one system (combat, navigation, loot, potion, etc.) can hold
    the lock at a time. Other systems block until it's released.

    Features:
        - Named ownership for debugging (who holds the lock)
        - Timeout to prevent infinite hangs
        - Reentrant for same-owner calls
        - Status query for overlay/logging
    """

    def __init__(self, enabled: bool = True, timeout: float = 3.0):
        """
        Args:
            enabled: If False, locking is skipped (pass-through mode)
            timeout: Max seconds to wait for lock acquisition
        """
        self._enabled = enabled
        self._timeout = timeout
        self._lock = threading.Lock()
        self._owner = None
        self._owner_lock = threading.Lock()
        self._acquire_time = 0
        self._depth = 0  # Reentrant depth counter

        logger.info(f"ActionLock initialized | enabled={enabled} | timeout={timeout}s")

    @contextmanager
    def acquire(self, owner: str = "unknown"):
        """
        Context manager to acquire the global action lock.

        Args:
            owner: Name of the system acquiring the lock (for logging)

        Yields:
            True if lock was acquired, False if timed out

        Example:
            with action_lock.acquire("combat"):
                humanizer.press_key("1")
        """
        if not self._enabled:
            yield True
            return

        # Reentrant: if same owner already holds, increment depth
        with self._owner_lock:
            if self._owner == owner:
                self._depth += 1
                logger.debug(f"ActionLock reentrant acquire by '{owner}' (depth={self._depth})")
                try:
                    yield True
                finally:
                    with self._owner_lock:
                        self._depth -= 1
                return

        # Try to acquire the lock with timeout
        acquired = self._lock.acquire(timeout=self._timeout)

        if acquired:
            with self._owner_lock:
                self._owner = owner
                self._acquire_time = time.time()
                self._depth = 1
            logger.debug(f"ActionLock acquired by '{owner}'")
            try:
                yield True
            finally:
                with self._owner_lock:
                    self._depth -= 1
                    if self._depth <= 0:
                        self._owner = None
                        self._depth = 0
                self._lock.release()
                logger.debug(f"ActionLock released by '{owner}'")
        else:
            logger.warning(
                f"ActionLock TIMEOUT — '{owner}' waited {self._timeout}s, "
                f"held by '{self._owner}'"
            )
            yield False

    @property
    def is_locked(self) -> bool:
        """Check if lock is currently held."""
        return self._lock.locked()

    @property
    def current_owner(self) -> str:
        """Get the name of the system currently holding the lock."""
        with self._owner_lock:
            return self._owner

    @property
    def hold_duration(self) -> float:
        """How long the current owner has held the lock (seconds)."""
        with self._owner_lock:
            if self._owner and self._acquire_time:
                return time.time() - self._acquire_time
        return 0.0

    def get_status(self) -> dict:
        """Get lock status for overlay/logging."""
        with self._owner_lock:
            return {
                "enabled": self._enabled,
                "locked": self._lock.locked(),
                "owner": self._owner or "none",
                "hold_time": round(self.hold_duration, 2),
                "depth": self._depth,
            }

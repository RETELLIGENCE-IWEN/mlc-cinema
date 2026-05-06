"""Application-wide configuration constants for mlc-cinema."""

from __future__ import annotations

APP_NAME: str = "mlc-cinema"
APP_DISPLAY_NAME: str = "MLC Cinema"
APP_VERSION: str = "0.0.1"

# Playback timer tick rate (Hz). The timer fires this often regardless
# of speed; the playback controller advances timeline time by
# ``dt_real * speed`` per tick and snaps to the nearest frame.
PLAYBACK_TICK_HZ: float = 60.0

# Speed multiplier bounds. ``1.0`` means wall-clock time matches the
# recorded timeline duration.
MIN_PLAYBACK_SPEED: float = 0.001
MAX_PLAYBACK_SPEED: float = 1000.0
DEFAULT_PLAYBACK_SPEED: float = 1.0

# Default trail length in frames (used by the placeholder viewport).
DEFAULT_TRAIL_LENGTH: int = 200

# Logger name root for the application.
LOG_NAMESPACE: str = "mlc_cinema"

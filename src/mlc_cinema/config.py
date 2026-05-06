"""Application-wide configuration constants for mlc-cinema."""

from __future__ import annotations

APP_NAME: str = "mlc-cinema"
APP_DISPLAY_NAME: str = "MLC Cinema"
APP_VERSION: str = "0.0.1"

# Default playback frame rate (frames per second).
DEFAULT_PLAYBACK_FPS: float = 10.0

# Default trail length in frames (used by the placeholder viewport).
DEFAULT_TRAIL_LENGTH: int = 200

# Logger name root for the application.
LOG_NAMESPACE: str = "mlc_cinema"

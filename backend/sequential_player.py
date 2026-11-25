"""
PRIME-Factory v1.0 — Sequential Player
Source: Software Constitution v1.0, Section 13 — Sequential Player

Plays simulation data point-by-point with configurable speed.
Supports callbacks for UI updates.
"""

import time
from typing import List, Dict, Callable, Optional


class SequentialPlayer:
    """
    Plays simulation data point-by-point with configurable speed.
    Supports callbacks for UI updates.
    """

    def __init__(self, speed_multiplier: float = 1.0):
        self.speed_multiplier = speed_multiplier
        self.current_data: List[Dict] = []
        self.current_index: int = 0
        self.is_playing: bool = False
        self.on_update: Optional[Callable] = None
        self.on_complete: Optional[Callable] = None

    def load_data(self, data: List[Dict]):
        """Load time-series data."""
        self.current_data = data
        self.current_index = 0

    def set_callbacks(self, on_update: Callable, on_complete: Callable):
        """Set update and completion callbacks."""
        self.on_update = on_update
        self.on_complete = on_complete

    def play(self):
        """Play data point-by-point."""
        self.is_playing = True
        self.current_index = 0

        for i, point in enumerate(self.current_data):
            if not self.is_playing:
                break

            self.current_index = i

            if self.on_update:
                self.on_update(point, i, len(self.current_data))

            # Wait based on speed multiplier
            time.sleep(1.0 / self.speed_multiplier)

        self.is_playing = False

        if self.on_complete:
            self.on_complete()

    def stop(self):
        """Stop playback."""
        self.is_playing = False

    def get_current_point(self) -> Optional[Dict]:
        """Get current data point."""
        if 0 <= self.current_index < len(self.current_data):
            return self.current_data[self.current_index]
        return None

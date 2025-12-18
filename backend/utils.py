from __future__ import annotations

import time


class StageTimer:
    def __init__(self, stage: str) -> None:
        self.stage = stage
        self._start = 0.0

    def __enter__(self) -> "StageTimer":
        self._start = time.perf_counter()
        print(f"[process_model] {self.stage} start")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        duration = time.perf_counter() - self._start
        print(f"[process_model] {self.stage} took {duration:.3f}s")

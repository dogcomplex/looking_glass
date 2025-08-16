from dataclasses import dataclass
import numpy as np

@dataclass
class ClockParams:
    window_ns: float = 10.0
    jitter_ps_rms: float = 10.0

class Clock:
    def __init__(self, params: ClockParams, rng=None):
        self.p = params
        self.rng = np.random.default_rng() if rng is None else rng

    def sample_window(self) -> float:
        jitter_ns = self.rng.normal(0.0, self.p.jitter_ps_rms*1e-3)
        return max(0.1, self.p.window_ns + jitter_ns)

from dataclasses import dataclass
import numpy as np


@dataclass
class ThermalParams:
    drift_scale: float = 0.0   # unitless scale of slow drift
    corner_hz: float = 0.01    # approximate corner frequency of the slow process


class Thermal:
    def __init__(self, params: ThermalParams, rng=None):
        self.p = params
        self.rng = np.random.default_rng() if rng is None else rng
        self._state = 0.0

    def step(self, frame_period_s: float = 0.1) -> dict:
        """Advance drift state and return per-module drift terms.

        frame_period_s is an approximate time per frame; this is a crude model.
        """
        if self.p.drift_scale <= 0.0:
            return {"comp_vth_mV_delta": 0.0, "opt_trans_scale": 1.0}
        # Simple AR(1) with pole set by corner frequency
        fc = max(self.p.corner_hz, 1e-6)
        alpha = float(np.exp(-2.0 * np.pi * fc * frame_period_s))
        noise = float(self.rng.normal(0.0, 1.0))
        self._state = alpha * self._state + (1.0 - alpha) * noise
        s = self._state * self.p.drift_scale
        comp_delta_mV = 1.0 * s
        opt_scale = 1.0 + 0.01 * s
        return {"comp_vth_mV_delta": comp_delta_mV, "opt_trans_scale": opt_scale}


from dataclasses import dataclass
import numpy as np

@dataclass
class TIAParams:
    tia_transimpedance_kohm: float = 10.0
    bw_mhz: float = 100.0
    in_noise_pA_rthz: float = 5.0
    peaking_q: float = 0.7

class TIA:
    def __init__(self, params: TIAParams, rng=None):
        self.p = params
        self.rng = np.random.default_rng() if rng is None else rng
        self._last = None

    def simulate(self, I: np.ndarray, dt_ns: float):
        I = np.array(I)
        R = self.p.tia_transimpedance_kohm * 1e3
        V = I * R
        # First-order LPF
        bw = self.p.bw_mhz * 1e6
        alpha = 1.0 - np.exp(-2.0*np.pi*bw*dt_ns*1e-9)
        if self._last is None:
            self._last = np.zeros_like(V)
        V_f = self._last + alpha*(V - self._last)
        self._last = V_f
        # Input-referred noise to output
        in_noise_A = self.p.in_noise_pA_rthz*1e-12*np.sqrt(1.0/(dt_ns*1e-9 + 1e-18))
        noise = self.rng.normal(0.0, in_noise_A*R, size=V.shape)
        return V_f + noise

from dataclasses import dataclass
import numpy as np

q = 1.602176634e-19

@dataclass
class PDParams:
    responsivity_A_per_W: float = 0.55
    dark_current_nA: float = 2.0
    cap_pF: float = 1.0

class Photodiode:
    def __init__(self, params: PDParams, rng=None):
        self.p = params
        self.rng = np.random.default_rng() if rng is None else rng

    def simulate(self, optical_mw, dt_ns: float):
        W = np.clip(np.array(optical_mw)*1e-3, 0.0, None)
        I_sig = self.p.responsivity_A_per_W * W
        I_dark = self.p.dark_current_nA * 1e-9
        B = 1.0/(dt_ns*1e-9 + 1e-18)
        I_total = I_sig + I_dark
        sigma = np.sqrt(2*q*np.clip(I_total,0,None)*B + 1e-24)
        noise = self.rng.normal(0.0, sigma, size=I_total.shape)
        return I_total + noise

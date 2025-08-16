from dataclasses import dataclass
import numpy as np

@dataclass
class ComparatorParams:
    vth_mV: float = 5.0
    hysteresis_mV: float = 1.0
    input_noise_mV_rms: float = 0.8
    drift_mV_per_C: float = 0.05
    prop_delay_ns: float = 2.0
    saturate_levels: bool = True

class Comparator:
    def __init__(self, params: ComparatorParams, rng=None):
        self.p = params
        self.rng = np.random.default_rng() if rng is None else rng
        self._last_out = None

    def reset(self) -> None:
        self._last_out = None

    def simulate(self, Vp: np.ndarray, Vm: np.ndarray, temp_C: float):
        dv = (np.array(Vp) - np.array(Vm))*1e3  # mV
        vth = self.p.vth_mV + (temp_C-25.0)*self.p.drift_mV_per_C
        hyst = self.p.hysteresis_mV
        noise = self.rng.normal(0.0, self.p.input_noise_mV_rms, size=dv.shape)
        eff = dv + noise
        if self._last_out is None:
            self._last_out = np.zeros_like(eff)
        up_th = vth + 0.5*hyst
        dn_th = vth - 0.5*hyst
        out = np.where(eff > up_th, 1, np.where(eff < -up_th, -1, self._last_out))
        out = np.where((eff < dn_th) & (eff > -dn_th), 0, out)
        if self.p.saturate_levels:
            out = np.clip(out, -1, 1)
        self._last_out = out
        return out.astype(int)

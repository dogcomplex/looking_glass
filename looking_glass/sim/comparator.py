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
    vth_sigma_mV: float = 0.0

class Comparator:
    def __init__(self, params: ComparatorParams, rng=None):
        self.p = params
        self.rng = np.random.default_rng() if rng is None else rng
        self._last_out = None
        self._vth_offset = None
        self._vth_per_ch = None

    def reset(self) -> None:
        self._last_out = None
        self._vth_offset = None
        self._vth_per_ch = None

    def set_vth_per_channel(self, vth_mV_vec):
        import numpy as _np
        arr = _np.asarray(vth_mV_vec, dtype=float)
        self._vth_per_ch = arr

    def simulate(self, Vp: np.ndarray, Vm: np.ndarray, temp_C: float):
        import numpy as _np
        dv = (_np.array(Vp) - _np.array(Vm))*1e3  # mV
        if self._vth_offset is None and self.p.vth_sigma_mV > 0.0:
            self._vth_offset = float(self.rng.normal(0.0, self.p.vth_sigma_mV))
        else:
            self._vth_offset = self._vth_offset or 0.0
        if self._vth_per_ch is not None and self._vth_per_ch.shape[0] == dv.shape[0]:
            # Treat provided per-channel thresholds as absolute vth (mV)
            vth_vec = self._vth_per_ch
        else:
            base_vth = self.p.vth_mV + (temp_C-25.0)*self.p.drift_mV_per_C + self._vth_offset
            vth_vec = _np.full_like(dv, base_vth, dtype=float)
        hyst = self.p.hysteresis_mV
        noise = self.rng.normal(0.0, self.p.input_noise_mV_rms, size=dv.shape)
        eff = dv + noise
        if self._last_out is None:
            self._last_out = _np.zeros_like(eff)
        up_th = vth_vec + 0.5*hyst
        dn_th = vth_vec - 0.5*hyst
        # Symmetric ternary thresholding; prefer zero near the origin
        out = _np.where(eff > up_th, 1, _np.where(eff < -up_th, -1, 0))
        if self.p.saturate_levels:
            out = _np.clip(out, -1, 1)
        self._last_out = out
        return out.astype(int)

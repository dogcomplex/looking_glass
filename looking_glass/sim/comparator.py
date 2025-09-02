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
    # Metastability near zero dv (sim-only stress hook)
    metastable_on: bool = False
    metastable_width_mV: float = 0.2  # half-width of dv band where metastability risk exists
    metastable_flip_prob: float = 0.05  # probability to flip decision within band

class Comparator:
    def __init__(self, params: ComparatorParams, rng=None):
        self.p = params
        self.rng = np.random.default_rng() if rng is None else rng
        self._last_out = None
        self._vth_offset = None
        self._vth_per_ch = None

    def reset(self) -> None:
        self._last_out = None
        # Preserve comparator offset and per-channel calibration across frames so
        # calibrations applied once remain effective during multi-trial runs.
        # self._vth_offset and self._vth_per_ch are intentionally NOT cleared.

    def set_vth_per_channel(self, vth_mV_vec):
        arr = np.asarray(vth_mV_vec, dtype=float)
        self._vth_per_ch = arr

    def simulate(self, Vp: np.ndarray, Vm: np.ndarray, temp_C: float):
        dv = (np.array(Vp) - np.array(Vm))*1e3  # mV
        if self._vth_offset is None and self.p.vth_sigma_mV > 0.0:
            self._vth_offset = float(self.rng.normal(0.0, self.p.vth_sigma_mV))
        else:
            self._vth_offset = self._vth_offset or 0.0
        if self._vth_per_ch is not None and self._vth_per_ch.shape[0] == dv.shape[0]:
            # Treat provided per-channel thresholds as absolute vth (mV)
            vth_vec = self._vth_per_ch
        else:
            base_vth = self.p.vth_mV + (temp_C-25.0)*self.p.drift_mV_per_C + self._vth_offset
            vth_vec = np.full_like(dv, base_vth, dtype=float)
        hyst = self.p.hysteresis_mV
        noise = self.rng.normal(0.0, self.p.input_noise_mV_rms, size=dv.shape)
        eff = dv + noise
        if self._last_out is None:
            self._last_out = np.zeros_like(eff)
        up_th = vth_vec + 0.5*hyst
        # Symmetric ternary thresholding; prefer zero near the origin
        out = np.where(eff > up_th, 1, np.where(eff < -up_th, -1, 0))
        if self.p.saturate_levels:
            out = np.clip(out, -1, 1)
        # Optional metastability: within a narrow band around zero dv, randomly flip with small prob
        if bool(self.p.metastable_on) and float(self.p.metastable_flip_prob) > 0.0:
            band = float(self.p.metastable_width_mV)
            if band > 0.0:
                mask = np.abs(eff) < band
                flips = self.rng.random(size=eff.shape) < float(self.p.metastable_flip_prob)
                # Flip sign; zero stays zero (can also toggle zero randomly if desired)
                flip_mask = mask & flips
                out = np.where(flip_mask, -np.sign(out), out)
        self._last_out = out
        return out.astype(int)

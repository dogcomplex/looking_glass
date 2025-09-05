from dataclasses import dataclass
import numpy as np

@dataclass
class TIAParams:
    tia_transimpedance_kohm: float = 10.0
    bw_mhz: float = 100.0
    bw2_mhz: float = 0.0
    in_noise_pA_rthz: float = 5.0
    peaking_q: float = 0.7
    slew_v_per_us: float = 500.0
    adc_bits: int = 10
    adc_fullscale_v: float = 1.0
    adc_read_noise_mV_rms: float = 0.0
    gain_sigma_pct: float = 0.0

class TIA:
    def __init__(self, params: TIAParams, rng=None):
        self.p = params
        self.rng = np.random.default_rng() if rng is None else rng
        self._last = None
        self._last_out = None
        # Channel gain mismatch can be represented as per-sample multiplier for simplicity
        self._gain_scale = None

    def reset(self) -> None:
        self._last = None
        self._last_out = None

    def simulate(self, I: np.ndarray, dt_ns: float):
        I = np.array(I)
        R = self.p.tia_transimpedance_kohm * 1e3
        if self._gain_scale is None and self.p.gain_sigma_pct > 0.0:
            sigma = self.p.gain_sigma_pct/100.0
            self._gain_scale = self.rng.normal(1.0, sigma, size=I.shape)
        if self._gain_scale is not None:
            R = R * self._gain_scale
        V = I * R
        # Two-pole LPF with optional peaking approximation
        bw = self.p.bw_mhz * 1e6
        bw2 = max(0.0, self.p.bw2_mhz) * 1e6
        alpha = 1.0 - np.exp(-2.0*np.pi*bw*dt_ns*1e-9)
        if self._last is None:
            self._last = np.zeros_like(V)
        V_f = self._last + alpha*(V - self._last)
        self._last = V_f
        if bw2 > 0.0:
            a2 = 1.0 - np.exp(-2.0*np.pi*bw2*dt_ns*1e-9)
            V_f2 = self._last + a2*(V_f - self._last)
            self._last = V_f2
            V_f = V_f2
        # Input-referred noise to output
        in_noise_A = self.p.in_noise_pA_rthz*1e-12*np.sqrt(1.0/(dt_ns*1e-9 + 1e-18))
        noise = self.rng.normal(0.0, in_noise_A*R, size=V.shape)
        Vn = V_f + noise
        # Slew limit
        if self._last_out is None:
            self._last_out = np.zeros_like(Vn)
        max_delta = self.p.slew_v_per_us * (dt_ns * 1e-3)
        delta = Vn - self._last_out
        delta = np.clip(delta, -max_delta, max_delta)
        out = self._last_out + delta
        self._last_out = out
        # ADC quantization and read noise
        if self.p.adc_bits > 0:
            fs = max(self.p.adc_fullscale_v, 1e-6)
            levels = 2**self.p.adc_bits
            step = fs / levels
            out = np.clip(out, -fs, fs)
            out = (np.round(out/step) * step)
        if self.p.adc_read_noise_mV_rms > 0.0:
            out = out + self.rng.normal(0.0, self.p.adc_read_noise_mV_rms*1e-3, size=out.shape)
        return out

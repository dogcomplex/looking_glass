from dataclasses import dataclass
import numpy as np

@dataclass
class EmitterParams:
    wavelength_nm: float = 850.0
    channels: int = 16
    power_mw_per_ch: float = 1.0
    extinction_db: float = 20.0
    rin_dbhz: float = -150.0
    rise_fall_ns_10_90: float = 1.0
    temp_coeff_pct_per_C: float = 0.2
    power_sigma_pct: float = 0.0
    modulation_mode: str = "extinction"  # "extinction" or "pushpull"
    pushpull_alpha: float = 0.8  # 0..1, fraction of differential modulation depth

class EmitterArray:
    def __init__(self, params: EmitterParams, rng=None):
        self.p = params
        self.rng = np.random.default_rng() if rng is None else rng
        # Fixed per-channel power scale (mismatch)
        sigma = max(self.p.power_sigma_pct, 0.0) / 100.0
        if self.p.channels > 0 and sigma > 0:
            self._ch_scale = self.rng.normal(1.0, sigma, size=self.p.channels)
        else:
            self._ch_scale = None

    def simulate(self, ternary: np.ndarray, dt_ns: float, temp_C: float) -> tuple[np.ndarray, np.ndarray]:
        ternary = np.asarray(ternary)
        assert len(ternary) == self.p.channels
        # Map ternary to two rails (W+ and W-)
        base = self.p.power_mw_per_ch
        if self._ch_scale is not None:
            base_vec = np.full_like(ternary, base, dtype=float) * self._ch_scale
        else:
            base_vec = np.full_like(ternary, base, dtype=float)
        temp_scale = 1.0 + (temp_C-25.0)*self.p.temp_coeff_pct_per_C/100.0
        if self.p.modulation_mode == "pushpull":
            # Constant total per channel; differential encodes sign
            alpha = float(np.clip(self.p.pushpull_alpha, 0.0, 1.0))
            total = base_vec * temp_scale
            half = 0.5 * total
            add = 0.5 * alpha * total
            Pp = np.where(ternary>0, half+add, np.where(ternary<0, half-add, half))
            Pm = np.where(ternary>0, half-add, np.where(ternary<0, half+add, half))
        else:
            # Extinction-based on/off per rail
            ext = 10**(-self.p.extinction_db/10.0)
            Pp = np.where(ternary>0, base_vec, base_vec*ext) * temp_scale
            Pm = np.where(ternary<0, base_vec, base_vec*ext) * temp_scale
        Pp = Pp * temp_scale
        Pm = Pm * temp_scale
        # Add RIN with a common-mode component per channel (correlated across rails)
        bw_hz = 1.0/(dt_ns*1e-9 + 1e-18)
        rin_lin = max(0.0, 10**(self.p.rin_dbhz/10.0))
        sigma_rel = np.sqrt(max(bw_hz, 1.0) * rin_lin)
        # Common-mode multiplicative fluctuation per channel
        g = self.rng.normal(0.0, sigma_rel, size=Pp.shape)
        Pp = Pp * (1.0 + g)
        Pm = Pm * (1.0 + g)
        # Residual uncorrelated component (e.g., rail-specific speckle)
        resid = 0.3 * sigma_rel
        if resid > 0:
            Pp = Pp + self.rng.normal(0.0, resid * np.maximum(Pp, 0.0))
            Pm = Pm + self.rng.normal(0.0, resid * np.maximum(Pm, 0.0))
        Pp = np.clip(Pp, 0.0, None)
        Pm = np.clip(Pm, 0.0, None)
        return Pp, Pm

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

class EmitterArray:
    def __init__(self, params: EmitterParams, rng=None):
        self.p = params
        self.rng = np.random.default_rng() if rng is None else rng

    def simulate(self, ternary: np.ndarray, dt_ns: float, temp_C: float) -> tuple[np.ndarray, np.ndarray]:
        ternary = np.asarray(ternary)
        assert len(ternary) == self.p.channels
        # Map ternary to two rails (W+ and W-)
        base = self.p.power_mw_per_ch
        ext = 10**(-self.p.extinction_db/10.0)
        temp_scale = 1.0 + (temp_C-25.0)*self.p.temp_coeff_pct_per_C/100.0
        Pp = np.where(ternary>0, base, base*ext)
        Pm = np.where(ternary<0, base, base*ext)
        Pp = Pp * temp_scale
        Pm = Pm * temp_scale
        # Add RIN: power noise ~ sqrt(BW)
        bw_hz = 1.0/(dt_ns*1e-9 + 1e-18)
        rin_lin = 10**(self.p.rin_dbhz/10.0)
        sigma = np.sqrt(max(bw_hz,1.0))*rin_lin*base
        Pp = Pp + self.rng.normal(0.0, sigma, size=Pp.shape)
        Pm = Pm + self.rng.normal(0.0, sigma, size=Pm.shape)
        return Pp, Pm

from dataclasses import dataclass
import numpy as np

q = 1.602176634e-19
h = 6.62607015e-34
c = 299792458.0


@dataclass
class CameraParams:
    qe: float = 0.6                    # quantum efficiency (0..1)
    wavelength_nm: float = 850.0       # nm, used to convert W to photons
    full_well_e: float = 20000.0       # electrons
    read_noise_e_rms: float = 2.0      # electrons rms
    dark_current_e_per_s: float = 50.0 # electrons per second
    prnu_pct: float = 0.5              # pixel response non-uniformity (% std)
    adc_bits: int = 12
    adc_fullscale_e: float = 20000.0


class Camera:
    def __init__(self, params: CameraParams, rng=None):
        self.p = params
        self.rng = np.random.default_rng() if rng is None else rng
        self._prnu = None

    def _ensure_prnu(self, N: int):
        if self._prnu is None:
            sigma = max(self.p.prnu_pct, 0.0) / 100.0
            self._prnu = 1.0 + self.rng.normal(0.0, sigma, size=N)

    def simulate(self, optical_mw, dt_ns: float):
        P = np.clip(np.array(optical_mw, dtype=float) * 1e-3, 0.0, None)  # W
        N = P.size
        self._ensure_prnu(N)
        lam = self.p.wavelength_nm * 1e-9
        photons_per_J = 1.0 / (h * c / lam)
        t_s = dt_ns * 1e-9
        # Electrons from signal
        e_sig = P * t_s * photons_per_J * self.p.qe
        # Dark current contribution
        e_dark = np.full(N, self.p.dark_current_e_per_s * t_s)
        # Shot noise (Poisson) and read noise
        e_mean = e_sig * self._prnu + e_dark
        e_poiss = self.rng.poisson(np.clip(e_mean, 0.0, None))
        e_read = self.rng.normal(0.0, self.p.read_noise_e_rms, size=N)
        e_total = e_poiss + e_read
        # Saturation and ADC quantization (electrons domain)
        e_total = np.clip(e_total, 0.0, self.p.full_well_e)
        if self.p.adc_bits > 0 and self.p.adc_fullscale_e > 0:
            step = self.p.adc_fullscale_e / (2 ** self.p.adc_bits)
            e_total = np.clip(e_total, 0.0, self.p.adc_fullscale_e)
            e_total = np.round(e_total / step) * step
        # Convert to equivalent current over the integration interval
        I_equiv = (e_total * q) / np.clip(t_s, 1e-12, None)
        return I_equiv


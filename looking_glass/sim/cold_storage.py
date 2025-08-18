from dataclasses import dataclass
import numpy as np


@dataclass
class ColdParams:
    # Readout physics (rough order-of-magnitude, adjustable by packs later)
    read_laser_mw: float = 5.0            # read laser optical power at media (mW)
    diffraction_efficiency: float = 0.12  # fraction of power diffracted into "on" spot
    extinction_db: float = 25.0           # on/off extinction of stored grating (dB)
    speckle_sigma_pct: float = 5.0        # multiplicative speckle contrast per channel (%)
    global_ct_db: float = -35.0           # global crosstalk pedestal (dB)
    mtf_blur_w: float = 2.0               # effective blur width parameter (arbitrary units)
    access_latency_ms: float = 2.0        # average seek/access/settle latency (ms)
    channels: int = 16


class ColdReader:
    """Simple holographic/phased-glass readout model that emulates an emitter.

    Emits two rails (plus/minus) as optical power vectors for compatibility with the pipeline.
    """

    def __init__(self, params: ColdParams, rng=None):
        self.p = params
        self.rng = np.random.default_rng() if rng is None else rng

    def simulate(self, ternary: np.ndarray, dt_ns: float, temp_C: float):
        ternary = np.asarray(ternary)
        assert ternary.size == self.p.channels

        base = float(self.p.read_laser_mw) * float(self.p.diffraction_efficiency)
        ext = 10 ** (-float(self.p.extinction_db) / 10.0)
        # Ideal rails before imperfections
        Pp = np.where(ternary > 0, base, base * ext)
        Pm = np.where(ternary < 0, base, base * ext)

        # Global crosstalk pedestal
        ct = 10 ** (float(self.p.global_ct_db) / 10.0)
        if Pp.size:
            leak_p = Pp.mean() * ct
            leak_m = Pm.mean() * ct
            Pp = Pp + leak_p
            Pm = Pm + leak_m

        # Speckle multiplicative noise (per-channel log-normal approx)
        sig = float(self.p.speckle_sigma_pct) / 100.0
        if sig > 0.0:
            mul_p = self.rng.normal(1.0, sig, size=Pp.shape)
            mul_m = self.rng.normal(1.0, sig, size=Pm.shape)
            Pp = Pp * mul_p
            Pm = Pm * mul_m

        # Simple MTF blur effect: reduce rail contrast a bit
        k = 1.0 / (1.0 + (float(self.p.mtf_blur_w)) ** 2)
        Pp = Pp * (1.0 - 0.5 * k) + 0.5 * k * Pp.mean()
        Pm = Pm * (1.0 - 0.5 * k) + 0.5 * k * Pm.mean()

        Pp = np.clip(Pp, 0.0, None)
        Pm = np.clip(Pm, 0.0, None)
        return Pp, Pm



from dataclasses import dataclass
import numpy as np

@dataclass
class OpticsParams:
    transmittance: float = 0.7
    w_plus_contrast: float = 0.85
    w_minus_contrast: float = 0.84
    crosstalk_db: float = -28.0
    ct_model: str = "global"  # "global" or "neighbor"
    ct_neighbor_db: float = -30.0
    stray_floor_db: float = -38.0
    psf_kernel: str = "lorentzian:w=2.5"
    signal_scale: float = 1.0
    amp_on: bool = False
    amp_gain_db: float = 10.0
    sat_abs_on: bool = False
    sat_I_sat: float = 1.0
    sat_alpha: float = 0.6

def _lorentz_kernel(size=51, w=2.5):
    x = np.linspace(-size//2, size//2, size)
    k = 1.0/(1.0 + (x/w)**2)
    k /= k.sum()
    return k

def _parse_psf(psf: str):
    if psf.startswith("lorentzian"):
        parts = psf.split(":")
        w = 2.5
        if len(parts) > 1:
            for kv in parts[1].split(","):
                if kv.startswith("w="):
                    try:
                        w = float(kv.split("=")[1])
                    except ValueError:
                        w = 2.5
        return ("lorentzian", w)
    return ("lorentzian", 2.5)

class Optics:
    def __init__(self, params: OpticsParams, rng=None):
        self.p = params
        self.rng = np.random.default_rng() if rng is None else rng
        self.grid = (64, 64)
        self._build_psf()
        self._last_blocks = None

    def _build_psf(self):
        kind, w = _parse_psf(self.p.psf_kernel)
        if kind == "lorentzian":
            self.k1d = _lorentz_kernel(51, w)
        else:
            self.k1d = _lorentz_kernel(51, 2.5)

    def simulate(self, power_vec_plus, power_vec_minus):
        H, W = self.grid
        chans = len(power_vec_plus)
        blocks = int(np.sqrt(chans))
        blocks = max(1, blocks)
        by = max(1, H // blocks)
        bx = max(1, W // blocks)
        img = np.zeros((H, W), dtype=np.float64)

        idx = 0
        for by_i in range(blocks):
            for bx_i in range(blocks):
                if idx >= chans:
                    break
                y0, x0 = by_i*by, bx_i*bx
                y1, x1 = min(H, y0+by), min(W, x0+bx)
                if y1<=y0 or x1<=x0:
                    continue
                midx = (x0+x1)//2
                img[y0:y1, x0:midx] += power_vec_plus[idx]*self.p.w_plus_contrast
                img[y0:y1, midx:x1] += power_vec_minus[idx]*self.p.w_minus_contrast
                idx += 1

        # PSF blur separable
        k = self.k1d
        img = np.apply_along_axis(lambda m: np.convolve(m, k, mode="same"), axis=1, arr=img)
        img = np.apply_along_axis(lambda m: np.convolve(m, k, mode="same"), axis=0, arr=img)

        # Stray pedestal
        stray_lin = 10**(self.p.stray_floor_db/10.0)
        ped = stray_lin * (img.max() + 1e-12)
        img = img + ped

        # Optional amplifier
        if self.p.amp_on:
            gain = 10**(self.p.amp_gain_db/10.0)
            img = img*gain + self.rng.normal(0.0, 0.01*img.mean() + 1e-12, size=img.shape)

        # Optional saturable absorber
        if self.p.sat_abs_on:
            I = img
            I_sat = self.p.sat_I_sat
            alpha = self.p.sat_alpha
            img = I / (1.0 + alpha*(I/(I_sat+1e-12)))

        # Project back to per-channel averages
        out_plus = []
        out_minus = []
        idx = 0
        for by_i in range(blocks):
            for bx_i in range(blocks):
                if idx >= chans:
                    break
                y0, x0 = by_i*by, bx_i*bx
                y1, x1 = min(H, y0+by), min(W, x0+bx)
                if y1<=y0 or x1<=x0:
                    continue
                midx = (x0+x1)//2
                roi_plus = img[y0:y1, x0:midx]
                roi_minus = img[y0:y1, midx:x1]
                out_plus.append(roi_plus.mean()*self.p.transmittance*self.p.signal_scale)
                out_minus.append(roi_minus.mean()*self.p.transmittance*self.p.signal_scale)
                idx += 1

        out_plus = np.array(out_plus)
        out_minus = np.array(out_minus)
        per_tile_plus = None
        per_tile_minus = None
        if chans == blocks * blocks:
            per_tile_plus = out_plus.reshape((blocks, blocks))
            per_tile_minus = out_minus.reshape((blocks, blocks))
            self._last_blocks = blocks
        else:
            self._last_blocks = None
        # Crosstalk
        if self.p.ct_model == "neighbor" and blocks > 1:
            # build grid arrays with zeros for unused cells
            size = blocks * blocks
            pad_p = np.zeros(size)
            pad_m = np.zeros(size)
            pad_p[:len(out_plus)] = out_plus
            pad_m[:len(out_minus)] = out_minus
            grid_p = pad_p.reshape((blocks, blocks))
            grid_m = pad_m.reshape((blocks, blocks))
            # 4-neighbor kernel (no center)
            nn = 10**(self.p.ct_neighbor_db/10.0)
            def neighbor_leak(g):
                up = np.vstack([np.zeros((1, g.shape[1])), g[:-1, :]])
                dn = np.vstack([g[1:, :], np.zeros((1, g.shape[1]))])
                lf = np.hstack([np.zeros((g.shape[0], 1)), g[:, :-1]])
                rt = np.hstack([g[:, 1:], np.zeros((g.shape[0], 1))])
                return g + nn * (up + dn + lf + rt)
            grid_p = neighbor_leak(grid_p)
            grid_m = neighbor_leak(grid_m)
            out_plus = grid_p.reshape(-1)[:len(out_plus)]
            out_minus = grid_m.reshape(-1)[:len(out_minus)]
        else:
            ct = 10**(self.p.crosstalk_db/10.0)
            leak_p = out_plus.mean()*ct if out_plus.size else 0.0
            leak_m = out_minus.mean()*ct if out_minus.size else 0.0
            out_plus = out_plus + leak_p
            out_minus = out_minus + leak_m
        return out_plus, out_minus, per_tile_plus, per_tile_minus

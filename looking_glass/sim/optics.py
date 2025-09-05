from dataclasses import dataclass
import numpy as np
import math

@dataclass
class OpticsParams:
    transmittance: float = 0.7
    w_plus_contrast: float = 0.85
    w_minus_contrast: float = 0.84
    crosstalk_db: float = -35.0
    ct_model: str = "global"  # "global" or "neighbor"
    ct_neighbor_db: float = -30.0
    ct_diag_db: float = -35.0
    stray_floor_db: float = -38.0
    psf_kernel: str = "lorentzian:w=2.5"
    signal_scale: float = 1.0
    amp_on: bool = False
    amp_gain_db: float = 10.0
    amp_ase_sigma: float = 0.01  # scales additive ASE-like noise ~ sigma * sqrt(gain) * mean
    sat_abs_on: bool = False
    sat_I_sat: float = 1.0
    sat_alpha: float = 0.6
    # Speckle/fringe multiplicative spatial noise (sim-only stress hook)
    speckle_on: bool = False
    speckle_sigma: float = 0.0  # multiplicative std of speckle field
    speckle_corr_px: int = 7    # correlation length in pixels (odd recommended)
    # Projector tiling helpers
    tile_border_px: int = 0           # empty border inside each tile to reduce inter-tile bleed
    tile_gain_sigma_pct: float = 0.0  # per-tile multiplicative gain sigma (PRNU/illumination)
    tile_isolation: bool = False      # if true, blur is applied per-tile (no cross-tile mixing)
    grid_px: int = 64                 # base grid resolution (square)
    # Fiber/loop realism hooks
    ins_loss_db_mean: float = 0.0     # extra insertion loss mean per pass (dB)
    ins_loss_db_sigma: float = 0.0    # extra insertion loss sigma per pass (dB)
    pdl_db: float = 0.0               # polarization-dependent loss magnitude (dB)
    pdl_step_rad: float = 0.0         # random-walk step per frame (radians)
    memory_tau_frames: float = 0.0    # simple SOA-like memory (frames), 0 disables
    reflection_event_db: float = 0.0  # back-reflection event strength (dB), 0 disables
    reflection_prob: float = 0.0      # probability per frame of a reflection spike
    # Slow temporal speckle fading (multiplicative, low-frequency)
    speckle_time_on: bool = False
    speckle_time_sigma: float = 0.0
    speckle_time_tau_frames: int = 0
    # Nonlinear multi-λ proxies (stress only)
    xgm_on: bool = False
    xgm_coeff: float = 0.0           # compresses intensity vs total power (0..1 small)
    xpm_on: bool = False
    xpm_coeff: float = 0.0           # adds intensity-coupled neighbor mixing
    fwm_on: bool = False
    fwm_coeff: float = 0.0           # adds ghost terms from quadratic mixing
    # Polarization scrambler (seconds-scale): randomize PDL projection periodically
    pol_scrambler_on: bool = False
    pol_scramble_every_frames: int = 0

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
        gp = max(16, int(getattr(self.p, 'grid_px', 64)))
        self.grid = (gp, gp)
        self._build_psf()
        self._last_blocks = None
        self._pdl_phase = 0.0
        self._mem_state = None
        self._speckle_time = None
        self._frame_idx = 0

    def _build_psf(self):
        kind, w = _parse_psf(self.p.psf_kernel)
        if kind == "lorentzian":
            self.k1d = _lorentz_kernel(51, w)
        else:
            self.k1d = _lorentz_kernel(51, 2.5)

    def simulate(self, power_vec_plus, power_vec_minus):
        H, W = self.grid
        chans = len(power_vec_plus)
        # Use ceil so we allocate enough tiles to cover all channels
        blocks = int(math.ceil(chans ** 0.5))
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
                # Apply optional inner border to leave empty margins per tile
                b = max(0, int(self.p.tile_border_px))
                y0b, x0b = y0 + b, x0 + b
                y1b, x1b = max(y0b, y1 - b), max(x0b, x1 - b)
                if y1b<=y0b or x1b<=x0b:
                    idx += 1
                    continue
                midx = (x0b+x1b)//2
                img[y0b:y1b, x0b:midx] += power_vec_plus[idx]*self.p.w_plus_contrast
                img[y0b:y1b, midx:x1b] += power_vec_minus[idx]*self.p.w_minus_contrast
                idx += 1

        # PSF blur separable (globally or per-tile isolated)
        k = self.k1d
        if bool(self.p.tile_isolation) and blocks > 0:
            out_img = np.zeros_like(img)
            for by_i in range(blocks):
                for bx_i in range(blocks):
                    y0, x0 = by_i*by, bx_i*bx
                    y1, x1 = min(H, y0+by), min(W, x0+bx)
                    if y1<=y0 or x1<=x0:
                        continue
                    sub = img[y0:y1, x0:x1]
                    sub = np.apply_along_axis(lambda m: np.convolve(m, k, mode="same"), axis=1, arr=sub)
                    sub = np.apply_along_axis(lambda m: np.convolve(m, k, mode="same"), axis=0, arr=sub)
                    out_img[y0:y1, x0:x1] = sub
            img = out_img
        else:
            img = np.apply_along_axis(lambda m: np.convolve(m, k, mode="same"), axis=1, arr=img)
            img = np.apply_along_axis(lambda m: np.convolve(m, k, mode="same"), axis=0, arr=img)

        # Optional speckle/fringe multiplicative spatial noise (zero-mean, correlated)
        if bool(self.p.speckle_on) and float(self.p.speckle_sigma) > 0.0:
            corr = max(1, int(self.p.speckle_corr_px))
            # Build a simple separable smoothing kernel for correlation
            kk = _lorentz_kernel(max(3, 2*(corr//2)+1), max(1.0, corr/2.0))
            noise = self.rng.normal(0.0, 1.0, size=img.shape)
            noise = np.apply_along_axis(lambda m: np.convolve(m, kk, mode="same"), axis=1, arr=noise)
            noise = np.apply_along_axis(lambda m: np.convolve(m, kk, mode="same"), axis=0, arr=noise)
            std = noise.std() + 1e-12
            noise = noise / std
            img = img * (1.0 + float(self.p.speckle_sigma) * noise)
            img = np.clip(img, 0.0, None)

        # Slow temporal speckle fading (multiplicative field with long correlation)
        if bool(getattr(self.p, 'speckle_time_on', False)) and float(getattr(self.p, 'speckle_time_sigma', 0.0)) > 0.0:
            tau = max(1, int(getattr(self.p, 'speckle_time_tau_frames', 0) or 0))
            beta = 1.0 / float(tau)
            # drive noise ~ N(0,1) filtered spatially a bit to avoid pixel snow
            drive = self.rng.normal(0.0, 1.0, size=img.shape)
            kk = _lorentz_kernel(9, 2.0)
            drive = np.apply_along_axis(lambda m: np.convolve(m, kk, mode="same"), axis=1, arr=drive)
            drive = np.apply_along_axis(lambda m: np.convolve(m, kk, mode="same"), axis=0, arr=drive)
            drive /= (drive.std() + 1e-12)
            if self._speckle_time is None:
                self._speckle_time = drive
            else:
                self._speckle_time = (1.0 - beta) * self._speckle_time + beta * drive
            img = img * (1.0 + float(self.p.speckle_time_sigma) * self._speckle_time)
            img = np.clip(img, 0.0, None)

        # Stray pedestal
        stray_lin = 10**(self.p.stray_floor_db/10.0)
        ped = stray_lin * (img.max() + 1e-12)
        img = img + ped

        # Optional amplifier
        if self.p.amp_on:
            gain = 10**(self.p.amp_gain_db/10.0)
            ase_sigma = float(self.p.amp_ase_sigma)
            img = img * gain + self.rng.normal(0.0, ase_sigma * (gain**0.5) * (img.mean() + 1e-12), size=img.shape)
            img = np.clip(img, 0.0, None)

        # Optional saturable absorber
        if self.p.sat_abs_on:
            I = img
            I_sat = self.p.sat_I_sat
            alpha = self.p.sat_alpha
            img = I / (1.0 + alpha*(I/(I_sat+1e-12)))

        # XGM proxy: compress intensity as total power rises (deterministic crosstalk via shared gain)
        if bool(getattr(self.p, 'xgm_on', False)) and float(getattr(self.p, 'xgm_coeff', 0.0)) > 0.0:
            total = img.mean() + 1e-12
            k = np.clip(float(self.p.xgm_coeff) * total / (total + 1.0), 0.0, 0.5)
            img = img * (1.0 - k)
            img = np.clip(img, 0.0, None)

        # XPM proxy: add small neighbor-mixed copy scaled by local intensity
        if bool(getattr(self.p, 'xpm_on', False)) and float(getattr(self.p, 'xpm_coeff', 0.0)) > 0.0:
            kx = _lorentz_kernel(7, 1.5)
            blurred = np.apply_along_axis(lambda m: np.convolve(m, kx, mode="same"), axis=1, arr=img)
            blurred = np.apply_along_axis(lambda m: np.convolve(m, kx, mode="same"), axis=0, arr=blurred)
            img = img + float(self.p.xpm_coeff) * (blurred - img) * (img / (img.mean() + 1e-12))
            img = np.clip(img, 0.0, None)

        # FWM proxy: quadratic ghost leaked back after slight blur
        if bool(getattr(self.p, 'fwm_on', False)) and float(getattr(self.p, 'fwm_coeff', 0.0)) > 0.0:
            quad = img * img
            kq = _lorentz_kernel(5, 1.0)
            quad = np.apply_along_axis(lambda m: np.convolve(m, kq, mode="same"), axis=1, arr=quad)
            quad = np.apply_along_axis(lambda m: np.convolve(m, kq, mode="same"), axis=0, arr=quad)
            img = img + float(self.p.fwm_coeff) * quad / (quad.mean() + 1e-12)
            img = np.clip(img, 0.0, None)

        # Simple SOA-like memory: reduce gain if last intensity was high (pattern dependence)
        tau = float(self.p.memory_tau_frames)
        if tau and tau > 0.0:
            avg = img.mean()
            if self._mem_state is None:
                self._mem_state = avg
            else:
                beta = 1.0 / max(1.0, tau)
                self._mem_state = (1.0 - beta) * self._mem_state + beta * avg
            # Apply a mild compression proportional to stored state
            comp = 1.0 / (1.0 + 0.5 * self._mem_state / (img.mean() + 1e-12))
            img = img * np.clip(comp, 0.7, 1.0)

        # Extra insertion loss variation per pass (in dB)
        if (self.p.ins_loss_db_mean or self.p.ins_loss_db_sigma):
            mu = float(self.p.ins_loss_db_mean)
            sg = float(self.p.ins_loss_db_sigma)
            loss_db = self.rng.normal(mu, sg)
            img = img * 10**(-loss_db/10.0)

        # Polarization-dependent loss with slow random walk
        if float(self.p.pdl_db) > 0.0 and float(self.p.pdl_step_rad) >= 0.0:
            self._pdl_phase += self.rng.normal(0.0, float(self.p.pdl_step_rad))
            pdl_lin = 10**(-float(self.p.pdl_db)/10.0)
            # Effective scale between [pdl_lin, 1] depending on projection
            scale = pdl_lin + (1.0 - pdl_lin) * (0.5 + 0.5 * np.cos(self._pdl_phase))
            img = img * scale
            # Optional polarization scrambler: periodic re-randomization of projection
            if bool(getattr(self.p, 'pol_scrambler_on', False)):
                every = max(0, int(getattr(self.p, 'pol_scramble_every_frames', 0) or 0))
                if every > 0 and (self._frame_idx % every) == 0:
                    self._pdl_phase = float(self.rng.uniform(0.0, 2.0 * math.pi))

        # Reflection spike event: add a scaled self-interference term with small random phase proxy
        if float(self.p.reflection_event_db) > 0.0 and float(self.p.reflection_prob) > 0.0:
            if self.rng.random() < float(self.p.reflection_prob):
                refl = 10**(-float(self.p.reflection_event_db)/10.0)
                # approximate interference as additive scaled copy plus small random fluctuation
                jitter = self.rng.normal(0.0, 0.05, size=img.shape)
                img = img + refl * img * (1.0 + jitter)

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
                b = max(0, int(self.p.tile_border_px))
                y0b, x0b = y0 + b, x0 + b
                y1b, x1b = max(y0b, y1 - b), max(x0b, x1 - b)
                if y1b<=y0b or x1b<=x0b:
                    idx += 1
                    continue
                midx = (x0b+x1b)//2
                roi_plus = img[y0b:y1b, x0b:midx]
                roi_minus = img[y0b:y1b, midx:x1b]
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
        # Apply per-tile gain variation (PRNU/illumination non-uniformity)
        if float(self.p.tile_gain_sigma_pct) > 0.0 and len(out_plus) > 0:
            sigma = float(self.p.tile_gain_sigma_pct) / 100.0
            gain = self.rng.normal(1.0, sigma, size=len(out_plus))
            out_plus = out_plus * gain
            out_minus = out_minus * gain

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
            nd = 10**(self.p.ct_diag_db/10.0)
            def neighbor_leak(g):
                up = np.vstack([np.zeros((1, g.shape[1])), g[:-1, :]])
                dn = np.vstack([g[1:, :], np.zeros((1, g.shape[1]))])
                lf = np.hstack([np.zeros((g.shape[0], 1)), g[:, :-1]])
                rt = np.hstack([g[:, 1:], np.zeros((g.shape[0], 1))])
                # diagonals
                ul = np.vstack([np.zeros((1, g.shape[1])), g[:-1, :]])
                ul = np.hstack([np.zeros((g.shape[0], 1)), ul[:, :-1]])
                ur = np.vstack([np.zeros((1, g.shape[1])), g[:-1, :]])
                ur = np.hstack([ur[:, 1:], np.zeros((g.shape[0], 1))])
                dl = np.vstack([g[1:, :], np.zeros((1, g.shape[1]))])
                dl = np.hstack([np.zeros((g.shape[0], 1)), dl[:, :-1]])
                dr = np.vstack([g[1:, :], np.zeros((1, g.shape[1]))])
                dr = np.hstack([dr[:, 1:], np.zeros((g.shape[0], 1))])
                return g + nn * (up + dn + lf + rt) + nd * (ul + ur + dl + dr)
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

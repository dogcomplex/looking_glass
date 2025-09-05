from dataclasses import dataclass
import numpy as np
from .sim.emitter import EmitterArray, EmitterParams
from .sim.optics import Optics, OpticsParams
from .sim.sensor import Photodiode, PDParams
from .sim.tia import TIA, TIAParams
from .sim.comparator import Comparator, ComparatorParams
from .sim.clock import Clock, ClockParams
from .sim.thermal import Thermal, ThermalParams
from .sim.camera import Camera, CameraParams

@dataclass
class SystemParams:
    channels: int = 16
    window_ns: float = 10.0
    temp_C: float = 25.0
    temp_ramp_C_per_hr: float = 0.0
    seed: int = 42
    reset_analog_state_each_frame: bool = True
    normalize_dv: bool = False
    normalize_eps_v: float = 1e-6
    lane_skew_ps_rms: float = 0.0
    pmd_ps_rms: float = 0.0
    correlated_jitter_ps_rms: float = 0.0

class Orchestrator:
    def __init__(self,
                 sys: SystemParams,
                 emitter_p: EmitterParams,
                 optics_p: OpticsParams,
                 pd_p: PDParams,
                 tia_p: TIAParams,
                 comp_p: ComparatorParams,
                 clk_p: ClockParams,
                 cam_p: CameraParams | None = None,
                 thermal_p: ThermalParams | None = None,
                 emitter_override=None):
        self.rng = np.random.default_rng(sys.seed)
        self.sys = sys
        self.emit = emitter_override if emitter_override is not None else EmitterArray(emitter_p, rng=self.rng)
        self.optx = Optics(optics_p, rng=self.rng)
        self.pd = Photodiode(pd_p, rng=self.rng)
        self.cam = Camera(cam_p, rng=self.rng) if cam_p is not None else None
        self.tia = TIA(tia_p, rng=self.rng)
        self.comp = Comparator(comp_p, rng=self.rng)
        self.clk = Clock(clk_p, rng=self.rng)
        self.therm = Thermal(thermal_p, rng=self.rng) if thermal_p is not None else None

    def step(self, force_ternary: np.ndarray | None = None):
        N = self.sys.channels
        dt_raw = self.clk.sample_window()
        # Apply comparator propagation delay as lost effective integration time
        dt = max(0.1, float(dt_raw) - float(self.comp.p.prop_delay_ns))
        # Apply temperature ramp to system temperature (affects emitter wavelength drift via simulate)
        if float(getattr(self.sys, 'temp_ramp_C_per_hr', 0.0)) != 0.0:
            self.sys.temp_C = float(self.sys.temp_C) + (dt * 1e-9) * (float(self.sys.temp_ramp_C_per_hr) / 3600.0)
        if self.sys.reset_analog_state_each_frame:
            # Reset analog state to avoid inter-frame memory when desired
            self.tia.reset()
            self.comp.reset()
        # Slow drift
        if self.therm is not None:
            drift = self.therm.step(frame_period_s=dt*1e-9)
            # Apply comparator threshold drift and optics transmittance scale
            self.comp.p.vth_mV = self.comp.p.vth_mV + drift["comp_vth_mV_delta"]
            self.optx.p.transmittance = self.optx.p.transmittance * drift["opt_trans_scale"]
        # ternary input vector
        if force_ternary is None:
            tern = self.rng.integers(-1, 2, size=N)
        else:
            tern = np.asarray(force_ternary, dtype=int)
            assert tern.shape[0] == N
        Pp, Pm = self.emit.simulate(tern, dt, self.sys.temp_C)
        # DWDM passband walk-off due to wavelength drift: adjust optics transmittance temporarily
        trans_save = self.optx.p.transmittance
        try:
            slope = float(getattr(self.optx.p, 'dwdm_slope_db_per_nm', 0.0))
            dlam = float(getattr(self.emit, '_delta_lambda_nm', 0.0))
            if slope != 0.0 and dlam != 0.0:
                loss_db = abs(dlam) * slope
                self.optx.p.transmittance = trans_save * 10**(-loss_db/10.0)
        except Exception:
            pass
        Pp2, Pm2, per_tile_p, per_tile_m = self.optx.simulate(Pp, Pm)
        # restore transmittance
        self.optx.p.transmittance = trans_save
        if self.cam is not None:
            # Camera converts optical power to equivalent current with shot/read noise and quantization
            Ip = self.cam.simulate(Pp2, dt)
            Im = self.cam.simulate(Pm2, dt)
        else:
            # Direct PD path
            Ip = self.pd.simulate(Pp2, dt)
            Im = self.pd.simulate(Pm2, dt)
        Vp = self.tia.simulate(Ip, dt)
        Vm = self.tia.simulate(Im, dt)
        # Lane skew: small per-channel timing mismatch -> dv perturbation proxy
        if float(getattr(self.sys, 'lane_skew_ps_rms', 0.0)) > 0.0:
            sk = float(self.sys.lane_skew_ps_rms) * 1e-3  # ps->ns scaling proxy
            dv_noise = self.rng.normal(0.0, sk, size=N)
            Vp = Vp + dv_noise
            Vm = Vm - dv_noise
        # PMD and AWG group-delay ripple: additional timing-induced dv noise
        gdr = float(getattr(self.optx.p, 'gdr_ps_pkpk', 0.0))
        pmd = float(getattr(self.sys, 'pmd_ps_rms', 0.0))
        sigma_ns = (gdr * 0.29e-3) + (pmd * 1e-3)  # coarse proxy to voltage jitter scale
        if sigma_ns > 0.0:
            jit = self.rng.normal(0.0, sigma_ns, size=N)
            Vp = Vp + jit
            Vm = Vm - jit
        # Correlated jitter across lanes (common-mode sampling error)
        cj_ps = float(getattr(self.sys, 'correlated_jitter_ps_rms', 0.0))
        if cj_ps > 0.0:
            cj_ns = self.rng.normal(0.0, cj_ps * 1e-3)
            Vp = Vp + cj_ns
            Vm = Vm - cj_ns
        if getattr(self.sys, "normalize_dv", False):
            # Per-channel normalization to suppress multiplicative noise (AGC-like)
            denom = np.clip(np.abs(Vp) + np.abs(Vm), self.sys.normalize_eps_v, None)
            Vp = Vp / denom
            Vm = Vm / denom
        t_out = self.comp.simulate(Vp, Vm, self.sys.temp_C)
        # Align lengths defensively (square grid backends may not match arbitrary channel counts)
        truth = tern
        try:
            M = int(min(len(t_out), len(truth)))
            if len(t_out) != len(truth):
                t_out = np.asarray(t_out)[:M]
                truth = np.asarray(truth)[:M]
                Vp = np.asarray(Vp)[:M]
                Vm = np.asarray(Vm)[:M]
        except Exception:
            M = len(truth)
        # crude "true" comparing to sign with 0 threshold
        ber = np.mean(t_out != truth)
        energy_pj = float((Pp2.sum()+Pm2.sum())*1e-3*dt*1e-9*1e12)  # mW * s -> J, to pJ
        # Simple per-module SNR proxies (avoid zero-divide)
        eps = 1e-18
        snr_emit = float((np.mean(Pp+Pm)+eps)/(np.std(Pp-Pm)+eps))
        snr_pd = float((np.mean(Ip+Im)+eps)/(np.std(Ip-Im)+eps))
        snr_tia = float((np.mean(Vp+Vm)+eps)/(np.std(Vp-Vm)+eps))
        return {
            "ber": float(ber),
            "energy_pj": energy_pj,
            "window_ns": float(dt),
            "snr_emit": snr_emit,
            "snr_pd": snr_pd,
            "snr_tia": snr_tia,
            "t_out": np.asarray(t_out).tolist(),
            "truth": np.asarray(truth).tolist(),
            "blocks": int(np.sqrt(N)) if int(np.sqrt(N))**2 == N else None,
            "per_tile": {
                "plus": per_tile_p.tolist() if per_tile_p is not None else None,
                "minus": per_tile_m.tolist() if per_tile_m is not None else None,
            },
            "dv_mV": (np.asarray(Vp) - np.asarray(Vm)).tolist(),
            "vsum_mV": (np.abs(np.asarray(Vp)) + np.abs(np.asarray(Vm))).tolist(),
            "effective_channels": int(M),
        }

    def run(self, trials=100):
        outs = [self.step() for _ in range(trials)]
        ber = np.median([o["ber"] for o in outs])
        en = np.median([o["energy_pj"] for o in outs])
        dt = np.median([o["window_ns"] for o in outs])
        snr_emit = np.median([o["snr_emit"] for o in outs])
        snr_pd = np.median([o["snr_pd"] for o in outs])
        snr_tia = np.median([o["snr_tia"] for o in outs])
        tokens_per_s = float(self.sys.channels) / max(1e-12, (dt * 1e-9))
        return {
            "p50_ber": float(ber),
            "p50_energy_pj": float(en),
            "window_ns": float(dt),
            "p50_tokens_per_s": float(tokens_per_s),
            "p50_snr_emit": float(snr_emit),
            "p50_snr_pd": float(snr_pd),
            "p50_snr_tia": float(snr_tia),
        }

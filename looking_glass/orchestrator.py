from dataclasses import dataclass
import numpy as np
from .sim.emitter import EmitterArray, EmitterParams
from .sim.optics import Optics, OpticsParams
from .sim.sensor import Photodiode, PDParams
from .sim.tia import TIA, TIAParams
from .sim.comparator import Comparator, ComparatorParams
from .sim.clock import Clock, ClockParams
from .sim.thermal import Thermal, ThermalParams

@dataclass
class SystemParams:
    channels: int = 16
    window_ns: float = 10.0
    temp_C: float = 25.0
    seed: int = 42
    reset_analog_state_each_frame: bool = True

class Orchestrator:
    def __init__(self,
                 sys: SystemParams,
                 emitter_p: EmitterParams,
                 optics_p: OpticsParams,
                 pd_p: PDParams,
                 tia_p: TIAParams,
                 comp_p: ComparatorParams,
                 clk_p: ClockParams,
                 thermal_p: ThermalParams | None = None):
        self.rng = np.random.default_rng(sys.seed)
        self.sys = sys
        self.emit = EmitterArray(emitter_p, rng=self.rng)
        self.optx = Optics(optics_p, rng=self.rng)
        self.pd = Photodiode(pd_p, rng=self.rng)
        self.tia = TIA(tia_p, rng=self.rng)
        self.comp = Comparator(comp_p, rng=self.rng)
        self.clk = Clock(clk_p, rng=self.rng)
        self.therm = Thermal(thermal_p, rng=self.rng) if thermal_p is not None else None

    def step(self):
        N = self.sys.channels
        dt_raw = self.clk.sample_window()
        # Apply comparator propagation delay as lost effective integration time
        dt = max(0.1, float(dt_raw) - float(self.comp.p.prop_delay_ns))
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
        # random ternary vector
        tern = self.rng.integers(-1, 2, size=N)
        Pp, Pm = self.emit.simulate(tern, dt, self.sys.temp_C)
        Pp2, Pm2, per_tile_p, per_tile_m = self.optx.simulate(Pp, Pm)
        Ip = self.pd.simulate(Pp2, dt)
        Im = self.pd.simulate(Pm2, dt)
        Vp = self.tia.simulate(Ip, dt)
        Vm = self.tia.simulate(Im, dt)
        t_out = self.comp.simulate(Vp, Vm, self.sys.temp_C)
        # crude "true" comparing to sign with 0 threshold
        truth = tern
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
            "per_tile": {
                "plus": per_tile_p.tolist() if per_tile_p is not None else None,
                "minus": per_tile_m.tolist() if per_tile_m is not None else None,
            },
        }

    def run(self, trials=100):
        outs = [self.step() for _ in range(trials)]
        ber = np.median([o["ber"] for o in outs])
        en = np.median([o["energy_pj"] for o in outs])
        dt = np.median([o["window_ns"] for o in outs])
        snr_emit = np.median([o["snr_emit"] for o in outs])
        snr_pd = np.median([o["snr_pd"] for o in outs])
        snr_tia = np.median([o["snr_tia"] for o in outs])
        return {
            "p50_ber": float(ber),
            "p50_energy_pj": float(en),
            "window_ns": float(dt),
            "p50_snr_emit": float(snr_emit),
            "p50_snr_pd": float(snr_pd),
            "p50_snr_tia": float(snr_tia),
        }

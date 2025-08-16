from dataclasses import dataclass
import numpy as np
from .sim.emitter import EmitterArray, EmitterParams
from .sim.optics import Optics, OpticsParams
from .sim.sensor import Photodiode, PDParams
from .sim.tia import TIA, TIAParams
from .sim.comparator import Comparator, ComparatorParams
from .sim.clock import Clock, ClockParams

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
                 clk_p: ClockParams):
        self.rng = np.random.default_rng(sys.seed)
        self.sys = sys
        self.emit = EmitterArray(emitter_p, rng=self.rng)
        self.optx = Optics(optics_p, rng=self.rng)
        self.pd = Photodiode(pd_p, rng=self.rng)
        self.tia = TIA(tia_p, rng=self.rng)
        self.comp = Comparator(comp_p, rng=self.rng)
        self.clk = Clock(clk_p, rng=self.rng)

    def step(self):
        N = self.sys.channels
        dt_raw = self.clk.sample_window()
        # Apply comparator propagation delay as lost effective integration time
        dt = max(0.1, float(dt_raw) - float(self.comp.p.prop_delay_ns))
        if self.sys.reset_analog_state_each_frame:
            # Reset analog state to avoid inter-frame memory when desired
            self.tia.reset()
            self.comp.reset()
        # random ternary vector
        tern = self.rng.integers(-1, 2, size=N)
        Pp, Pm = self.emit.simulate(tern, dt, self.sys.temp_C)
        Pp2, Pm2 = self.optx.simulate(Pp, Pm)
        Ip = self.pd.simulate(Pp2, dt)
        Im = self.pd.simulate(Pm2, dt)
        Vp = self.tia.simulate(Ip, dt)
        Vm = self.tia.simulate(Im, dt)
        t_out = self.comp.simulate(Vp, Vm, self.sys.temp_C)
        # crude "true" comparing to sign with 0 threshold
        truth = tern
        ber = np.mean(t_out != truth)
        energy_pj = float((Pp2.sum()+Pm2.sum())*1e-3*dt*1e-9*1e12)  # mW * s -> J, to pJ
        return {"ber": float(ber), "energy_pj": energy_pj, "window_ns": float(dt)}

    def run(self, trials=100):
        outs = [self.step() for _ in range(trials)]
        ber = np.median([o["ber"] for o in outs])
        en = np.median([o["energy_pj"] for o in outs])
        dt = np.median([o["window_ns"] for o in outs])
        return {"p50_ber": float(ber), "p50_energy_pj": float(en), "window_ns": float(dt)}

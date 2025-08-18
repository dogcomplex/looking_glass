from __future__ import annotations

from dataclasses import replace
import math
import random
from typing import Dict, Any, Tuple

from .orchestrator import Orchestrator, SystemParams
from .sim.emitter import EmitterParams
from .sim.optics import OpticsParams
from .sim.sensor import PDParams
from .sim.tia import TIAParams
from .sim.comparator import ComparatorParams
from .sim.clock import ClockParams


class TuneSpace:
    def __init__(self):
        # Reasonable, hardware-realistic bounds
        self.bounds = {
            ("clock", "window_ns"): (8.0, 30.0),
            ("emitter", "power_mw_per_ch"): (0.3, 2.0),
            ("emitter", "extinction_db"): (15.0, 35.0),
            ("tia", "tia_transimpedance_kohm"): (2.0, 20.0),
            ("tia", "bw_mhz"): (20.0, 120.0),
            ("tia", "in_noise_pA_rthz"): (2.0, 8.0),
            ("comparator", "hysteresis_mV"): (0.5, 2.0),
            ("comparator", "input_noise_mV_rms"): (0.2, 1.0),
            ("optics", "crosstalk_db"): (-38.0, -20.0),
            ("optics", "ct_neighbor_db"): (-40.0, -25.0),
            ("optics", "ct_diag_db"): (-45.0, -30.0),
            ("optics", "w_plus_contrast"): (0.75, 0.95),
            ("optics", "w_minus_contrast"): (0.75, 0.95),
            ("optics", "stray_floor_db"): (-48.0, -30.0),
        }

    def clip(self, key: Tuple[str, str], val: float) -> float:
        lo, hi = self.bounds[key]
        return max(lo, min(hi, val))


def evaluate(system: SystemParams,
             emit: EmitterParams,
             optx: OpticsParams,
             pd: PDParams,
             tia: TIAParams,
             comp: ComparatorParams,
             clk: ClockParams,
             trials: int,
             use_calibration: bool = True) -> Dict[str, Any]:
    orch = Orchestrator(system, emit, optx, pd, tia, comp, clk)
    base = orch.run(trials=trials)
    result = {"ber": float(base.get("p50_ber", 1.0)), "summary": base}
    if not use_calibration:
        return result
    # Small calibration pass (per-channel threshold)
    try:
        import numpy as np
        pos_sum = np.zeros(system.channels)
        pos_cnt = np.zeros(system.channels)
        neg_sum = np.zeros(system.channels)
        neg_cnt = np.zeros(system.channels)
        for _ in range(min(200, max(60, trials))):
            tern = orch.rng.integers(-1, 2, size=system.channels)
            r = orch.step(force_ternary=tern)
            dv = np.array(r.get("dv_mV", [0]*system.channels))
            pos = tern > 0
            neg = tern < 0
            pos_sum[pos] += dv[pos]; pos_cnt[pos] += 1
            neg_sum[neg] += dv[neg]; neg_cnt[neg] += 1
        pos_mean = np.divide(pos_sum, np.clip(pos_cnt, 1.0, None))
        neg_mean = np.divide(neg_sum, np.clip(neg_cnt, 1.0, None))
        vth_vec = 0.5*(pos_mean + neg_mean)
        orch.comp.set_vth_per_channel(vth_vec)
        after = orch.run(trials=trials)
        result["ber_calibrated"] = float(after.get("p50_ber", result["ber"]))
        result["summary_calibrated"] = after
    except Exception:
        pass
    return result


def auto_tune(system: SystemParams,
              emit: EmitterParams,
              optx: OpticsParams,
              pd: PDParams,
              tia: TIAParams,
              comp: ComparatorParams,
              clk: ClockParams,
              trials: int = 150,
              budget: int = 80,
              seed: int = 42,
              use_calibration: bool = True) -> Dict[str, Any]:
    rnd = random.Random(seed)
    space = TuneSpace()
    # Start from current
    best_cfg = (system, emit, optx, pd, tia, comp, clk)
    best = evaluate(*best_cfg, trials=trials, use_calibration=use_calibration)
    best_cost = best.get("ber_calibrated", best["ber"]) 
    temp = 0.5
    cooling = 0.97
    for i in range(budget):
        sys2, em2, ox2, pd2, ti2, co2, cl2 = best_cfg
        # Propose slight perturbations in realistic bounds
        def jitter(val, scale):
            return val + rnd.uniform(-scale, scale)
        cl2 = replace(cl2, window_ns=space.clip(("clock","window_ns"), jitter(cl2.window_ns, 2.0)))
        em2 = replace(em2,
                      power_mw_per_ch=space.clip(("emitter","power_mw_per_ch"), jitter(em2.power_mw_per_ch, 0.2)),
                      extinction_db=space.clip(("emitter","extinction_db"), jitter(em2.extinction_db, 2.0)))
        ti2 = replace(ti2,
                      tia_transimpedance_kohm=space.clip(("tia","tia_transimpedance_kohm"), jitter(ti2.tia_transimpedance_kohm, 2.0)),
                      bw_mhz=space.clip(("tia","bw_mhz"), jitter(ti2.bw_mhz, 10.0)),
                      in_noise_pA_rthz=space.clip(("tia","in_noise_pA_rthz"), jitter(ti2.in_noise_pA_rthz, 0.8)))
        co2 = replace(co2,
                      hysteresis_mV=space.clip(("comparator","hysteresis_mV"), jitter(co2.hysteresis_mV, 0.2)),
                      input_noise_mV_rms=space.clip(("comparator","input_noise_mV_rms"), jitter(co2.input_noise_mV_rms, 0.1)))
        ox2 = replace(ox2,
                      crosstalk_db=space.clip(("optics","crosstalk_db"), jitter(ox2.crosstalk_db, 2.0)),
                      ct_neighbor_db=space.clip(("optics","ct_neighbor_db"), jitter(ox2.ct_neighbor_db, 2.0)),
                      ct_diag_db=space.clip(("optics","ct_diag_db"), jitter(ox2.ct_diag_db, 2.0)),
                      w_plus_contrast=space.clip(("optics","w_plus_contrast"), jitter(ox2.w_plus_contrast, 0.03)),
                      w_minus_contrast=space.clip(("optics","w_minus_contrast"), jitter(ox2.w_minus_contrast, 0.03)),
                      stray_floor_db=space.clip(("optics","stray_floor_db"), jitter(ox2.stray_floor_db, 2.0)))
        cand_cfg = (sys2, em2, ox2, pd2, ti2, co2, cl2)
        cand = evaluate(*cand_cfg, trials=trials, use_calibration=use_calibration)
        cost = cand.get("ber_calibrated", cand["ber"]) 
        if cost < best_cost or rnd.random() < math.exp((best_cost - cost)/max(1e-6,temp)):
            best_cfg = cand_cfg
            best = cand
            best_cost = cost
        temp *= cooling
    sys2, em2, ox2, pd2, ti2, co2, cl2 = best_cfg
    return {
        "best_ber": best.get("ber_calibrated", best.get("ber")),
        "best_summary": best.get("summary_calibrated", best.get("summary")),
        "params": {
            "system": sys2.__dict__,
            "emitter": em2.__dict__,
            "optics": ox2.__dict__,
            "pd": pd2.__dict__,
            "tia": ti2.__dict__,
            "comparator": co2.__dict__,
            "clock": cl2.__dict__,
        }
    }


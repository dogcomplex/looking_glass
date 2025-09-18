from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from looking_glass.sim.emitter import EmitterArray, EmitterParams


def test_pushpull_temperature_scaling_once():
    params = EmitterParams(
        channels=1,
        power_mw_per_ch=2.0,
        temp_coeff_pct_per_C=5.0,
        modulation_mode="pushpull",
        pushpull_alpha=0.6,
        rin_dbhz=float("-inf"),
    )
    emitter = EmitterArray(params, rng=np.random.default_rng(42))
    temp_C = 45.0
    ternary = np.array([1], dtype=int)

    Pp, Pm = emitter.simulate(ternary, dt_ns=1.0, temp_C=temp_C)

    temp_scale = 1.0 + (temp_C - 25.0) * params.temp_coeff_pct_per_C / 100.0
    total = params.power_mw_per_ch * temp_scale
    half = 0.5 * total
    add = 0.5 * params.pushpull_alpha * total

    np.testing.assert_allclose(Pp, half + add)
    np.testing.assert_allclose(Pm, half - add)


def test_extinction_temperature_scaling_once():
    params = EmitterParams(
        channels=3,
        power_mw_per_ch=1.5,
        temp_coeff_pct_per_C=7.5,
        modulation_mode="extinction",
        extinction_db=25.0,
        rin_dbhz=float("-inf"),
    )
    emitter = EmitterArray(params, rng=np.random.default_rng(123))
    temp_C = 35.0
    ternary = np.array([1, 0, -1], dtype=int)

    Pp, Pm = emitter.simulate(ternary, dt_ns=1.0, temp_C=temp_C)

    temp_scale = 1.0 + (temp_C - 25.0) * params.temp_coeff_pct_per_C / 100.0
    on = params.power_mw_per_ch * temp_scale
    off = on * 10 ** (-params.extinction_db / 10.0)

    np.testing.assert_allclose(Pp, [on, off, off])
    np.testing.assert_allclose(Pm, [off, off, on])

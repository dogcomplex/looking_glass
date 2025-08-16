import os, sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import math
from statistics import median

from looking_glass.orchestrator import Orchestrator, SystemParams
from looking_glass.sim.emitter import EmitterParams, EmitterArray
from looking_glass.sim.sensor import PDParams, Photodiode
from looking_glass.sim.tia import TIAParams
from looking_glass.sim.comparator import ComparatorParams
from looking_glass.sim.clock import ClockParams


def check_emitter_rin_scaling():
    p = EmitterParams(channels=1, rin_dbhz=-150.0, power_mw_per_ch=1.0)
    em = EmitterArray(p)
    # Two window lengths (ns) -> different BW; noise should increase with sqrt(BW)
    dt1, dt2 = 5.0, 20.0
    s1 = []
    s2 = []
    for _ in range(2000):
        Pp1, _ = em.simulate([1], dt1, 25.0)
        Pp2, _ = em.simulate([1], dt2, 25.0)
        s1.append(Pp1[0])
        s2.append(Pp2[0])
    sigma1 = (median(sorted(s1)[len(s1)//2:]) - median(sorted(s1)[:len(s1)//2]))/1.349 if s1 else 0.0
    sigma2 = (median(sorted(s2)[len(s2)//2:]) - median(sorted(s2)[:len(s2)//2]))/1.349 if s2 else 0.0
    # Expect sigma ~ sqrt(BW) ~ 1/sqrt(dt); so sigma1/sigma2 ~ sqrt(dt2/dt1)
    ratio = sigma1 / (sigma2 + 1e-12)
    expected = math.sqrt(dt2/dt1)
    return abs(ratio/expected - 1.0) < 0.5  # loose tolerance for small-sample robust-estimate


def check_sensor_shot_noise_scaling():
    p = PDParams(responsivity_A_per_W=0.5, dark_current_nA=0.0)
    pd = Photodiode(p)
    dt = 10.0
    currents = []
    for _ in range(2000):
        I = pd.simulate([1.0], dt)
        currents.append(I[0])
    # Roughly mean should be ~ R*P + dark (0)
    mean_I = sum(currents)/len(currents)
    # With 1 mW optical and 0.5 A/W responsivity => 0.0005 A
    return 4e-4 < mean_I < 6e-4


def check_end_to_end_improves_with_longer_window():
    sys_p = SystemParams(channels=16, window_ns=10.0, temp_C=25.0, seed=123)
    emit = EmitterParams(channels=16)
    optx = looking_optx_params()
    pd = PDParams()
    tia = TIAParams()
    comp = ComparatorParams()
    clk = ClockParams(window_ns=10.0, jitter_ps_rms=10.0)

    orch = Orchestrator(sys_p, emit, optx, pd, tia, comp, clk)
    # Short window (effective shorter after comparator delay)
    orch.clk.p.window_ns = 5.0
    ber_short = median([orch.step()["ber"] for _ in range(200)])
    # Long window (better SNR)
    orch.clk.p.window_ns = 20.0
    ber_long = median([orch.step()["ber"] for _ in range(200)])
    return ber_long <= ber_short


def check_tia_rc_settling_monotonic():
    from looking_glass.sim.tia import TIA
    p = TIAParams(tia_transimpedance_kohm=10.0, bw_mhz=10.0, in_noise_pA_rthz=0.0, slew_v_per_us=10.0)
    tia = TIA(p)
    dt = 10.0  # ns
    I = 100e-6  # 100 uA step
    outs = []
    for _ in range(50):
        outs.append(float(tia.simulate([I], dt)[0]))
    # Monotonic rise and below steady-state (R*I)
    steady = p.tia_transimpedance_kohm*1e3*I
    return all(outs[i] <= outs[i+1] + 1e-9 for i in range(len(outs)-1)) and outs[-1] <= steady + 1e-6


def check_comparator_hysteresis_window():
    from looking_glass.sim.comparator import Comparator
    p = ComparatorParams(vth_mV=5.0, hysteresis_mV=2.0, input_noise_mV_rms=0.0, drift_mV_per_C=0.0)
    cmpx = Comparator(p)
    cmpx.reset()
    # Sweep differential input around thresholds
    def out_for_dv(dv_mV):
        return int(cmpx.simulate([dv_mV/1e3], [0.0], 25.0)[0])
    # Rising: below -up_th => -1, above up_th => +1; central window near 0
    ups = [out_for_dv(x) for x in range(-10, 11, 1)]
    # Expect zero somewhere near 0 due to hysteresis region, and both -1 and +1 present at extremes
    return (-1 in ups) and (1 in ups) and (0 in ups)


def looking_optx_params():
    from looking_glass.sim.optics import OpticsParams
    return OpticsParams()


def main():
    tests = [
        ("Emitter RIN ~ sqrt(BW) scaling", check_emitter_rin_scaling),
        ("Sensor mean current sane", check_sensor_shot_noise_scaling),
        ("End-to-end BER improves with longer window", check_end_to_end_improves_with_longer_window),
        ("TIA RC settling monotonic and bounded", check_tia_rc_settling_monotonic),
        ("Comparator hysteresis exhibits 0-region", check_comparator_hysteresis_window),
    ]
    results = []
    for name, fn in tests:
        ok = False
        try:
            ok = bool(fn())
        except (AssertionError, ValueError, RuntimeError):
            ok = False
        results.append((name, ok))
    for name, ok in results:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    # Non-zero exit code if any fail
    if not all(ok for _, ok in results):
        sys.exit(1)


if __name__ == "__main__":
    main()


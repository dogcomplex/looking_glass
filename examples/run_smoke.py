import os, sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from looking_glass.orchestrator import Orchestrator, SystemParams
from looking_glass.sim.emitter import EmitterParams
from looking_glass.sim.optics import OpticsParams
from looking_glass.sim.sensor import PDParams
from looking_glass.sim.tia import TIAParams
from looking_glass.sim.comparator import ComparatorParams
from looking_glass.sim.clock import ClockParams

def main():
    sys_p = SystemParams(channels=16, window_ns=10.0, temp_C=25.0, seed=1)
    emit = EmitterParams(channels=16)
    optx = OpticsParams()
    pd = PDParams()
    tia = TIAParams()
    comp = ComparatorParams()
    clk = ClockParams(window_ns=10.0, jitter_ps_rms=10.0)
    orch = Orchestrator(sys_p, emit, optx, pd, tia, comp, clk)
    print(orch.run(trials=200))

if __name__ == "__main__":
    main()

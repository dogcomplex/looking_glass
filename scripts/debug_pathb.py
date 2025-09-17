import os
import sys
import numpy as np
import yaml

ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from looking_glass.orchestrator import Orchestrator, SystemParams
from looking_glass.sim.emitter import EmitterParams
from looking_glass.sim.optics import OpticsParams
from looking_glass.sim.sensor import PDParams
from looking_glass.sim.tia import TIAParams
from looking_glass.sim.comparator import ComparatorParams
from looking_glass.sim.clock import ClockParams


def load_yaml(path, cls, channels=None):
    base = cls()
    if channels is not None and hasattr(base, "channels"):
        base.channels = channels
    with open(os.path.join(ROOT, path), 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
    for k, v in data.items():
        if hasattr(base, k):
            setattr(base, k, v)
    if channels is not None and hasattr(base, "channels"):
        base.channels = channels
    return base


def confusion(optics_pack):
    channels = 8
    sys_p = SystemParams(channels=channels, window_ns=9.0, seed=321, reset_analog_state_each_frame=False)
    emit = load_yaml('configs/packs/overlays/emitter_pathb_premium.yaml', EmitterParams, channels)
    optx = load_yaml(optics_pack, OpticsParams)
    pd = PDParams()
    tia = load_yaml('configs/packs/overlays/tia_pathb_premium.yaml', TIAParams)
    comp = load_yaml('configs/packs/overlays/comparator_pathb_premium.yaml', ComparatorParams)
    clk = ClockParams(window_ns=9.0, jitter_ps_rms=45.0)
    orch = Orchestrator(sys_p, emit, optx, pd, tia, comp, clk)
    rng = np.random.default_rng(777)
    counts = {(t, o): 0 for t in (-1, 0, 1) for o in (-1, 0, 1)}
    errs = []
    for _ in range(400):
        tern = rng.integers(-1, 2, size=channels)
        res = orch.step(force_ternary=tern)
        out = np.array(res['t_out'], dtype=int)
        errs.append(np.mean(out != tern))
        for t, o in zip(tern, out):
            counts[(int(t), int(o))] += 1
    print('pack:', optics_pack)
    for t in (-1, 0, 1):
        row = [counts[(t, o)] for o in (-1, 0, 1)]
        print(f'  t={t}: {row}')
    print('  median BER:', float(np.median(errs)))


if __name__ == '__main__':
    confusion('configs/packs/overlays/optics_pathb_soa_mzi.yaml')
    confusion('configs/packs/overlays/optics_pathb_soa_mzi_clamp.yaml')
    confusion('configs/packs/overlays/optics_pathb_soa_mzi_clean.yaml')

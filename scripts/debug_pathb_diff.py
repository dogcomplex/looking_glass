import os
import sys
import numpy as np
import yaml

ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from looking_glass.sim.optics import OpticsParams
from looking_glass.sim.emitter import EmitterParams


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


def debug_diff(optics_pack):
    from looking_glass.sim.optics import Optics
    params = load_yaml(optics_pack, OpticsParams)
    optx = Optics(params)
    emit = load_yaml('configs/packs/overlays/emitter_pathb_premium.yaml', EmitterParams, channels=8)
    rng = np.random.default_rng(0)
    diff_emit = []
    diff_after = []
    for _ in range(400):
        tern = rng.integers(-1, 2, size=8)
        Pp, Pm = optx.rng.normal(0,0,0), optx.rng.normal(0,0,0)  # placeholder

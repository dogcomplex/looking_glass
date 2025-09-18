import json
import numpy as np
from pathlib import Path
from examples.test import _run_pathb_stage_pass
from looking_glass.orchestrator import Orchestrator, SystemParams
from looking_glass.sim.emitter import EmitterParams
from looking_glass.sim.optics import OpticsParams
from looking_glass.sim.sensor import PDParams
from looking_glass.sim.tia import TIAParams
from looking_glass.sim.comparator import ComparatorParams
from looking_glass.sim.clock import ClockParams

with Path('configs/packs/tmp_lowcost_emitter_boost.yaml').open() as f:
    emit = EmitterParams(**(json.loads(json.dumps({})) or {}))

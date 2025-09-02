from __future__ import annotations
import json
import time
from pathlib import Path


def main() -> None:
    queue = Path('queue/probes.jsonl')
    queue.parent.mkdir(parents=True, exist_ok=True)

    base = [
        '--trials','320','--no-sweeps','--no-drift','--light-output',
        '--apply-calibration','--no-adaptive-input','--no-cold-input',
        '--no-path-b','--path-b-depth','0','--no-path-b-analog',
        '--base-window-ns','19.0','--classifier','chop','--avg-frames','3',
        '--mask-bad-frac','0.09375','--gate-thresh-mV','0.6','--gate-extra-frames','1',
    ]

    optics_A = 'configs/packs/overlays/optics_stage_a_hygiene.yaml'
    optics_E = 'configs/packs/overlays/optics_stage_e_power_mod.yaml'
    optics_E2 = 'configs/packs/overlays/optics_stage_e2_power_mod.yaml'
    comp_T = 'configs/packs/overlays/tuned_comparator.yaml'
    comp_C = 'configs/packs/overlays/comparator_stage_c_trims.yaml'
    comp_C2 = 'configs/packs/overlays/comparator_stage_c2_trims.yaml'
    tia_T = 'configs/packs/overlays/tuned_tia.yaml'
    tia_B = 'configs/packs/overlays/tia_stage_b_low_noise.yaml'
    tia_B2 = 'configs/packs/overlays/tia_stage_b2_low_noise.yaml'

    def J(label: str, seed: int, optics: str, comp: str, tia: str) -> dict:
        cmd = list(base) + ['--seed', str(seed)]
        return {
            'version': 'overlayfix2',
            'nonce': str(int(time.time())),
            'cmd': cmd,
            'optics_overlay': optics,
            'comparator_overlay': comp,
            'tia_overlay': tia,
            'json_out': f"out/{label}.json",
            'label': label,
        }

    jobs = [
        J('ofix_stageA', 8450, optics_A, comp_T, tia_T),
        J('ofix_stageB', 8451, optics_A, comp_T, tia_B),
        J('ofix_stageC', 8452, optics_A, comp_C, tia_T),
        J('ofix_stageE', 8453, optics_E, comp_T, tia_B),
        J('ofix_stageBCE', 8454, optics_E, comp_C, tia_B),
        J('ofix_comboStrong', 8455, optics_E2, comp_C2, tia_B2),
    ]

    with queue.open('a', encoding='utf-8') as f:
        for job in jobs:
            f.write(json.dumps(job, separators=(',', ':')) + '\n')
    print(f'appended {len(jobs)} overlay-fix validation jobs to {queue}')


if __name__ == '__main__':
    main()



from __future__ import annotations
import json
from pathlib import Path


def main() -> None:
    queue = Path('queue/probes.jsonl')
    queue.parent.mkdir(parents=True, exist_ok=True)

    base = [
        '--trials','320','--no-sweeps','--light-output',
        '--apply-calibration','--no-adaptive-input','--no-cold-input',
        '--no-path-b','--path-b-depth','0','--no-path-b-analog',
        '--classifier','chop','--base-window-ns','19.0','--avg-frames','3', '--mask-bad-frac','0.09375',
        '--gate-thresh-mV','0.6','--gate-extra-frames','1',
    ]

    optics_E2 = 'configs/packs/overlays/optics_stage_e2_power_mod.yaml'
    comp_C2 = 'configs/packs/overlays/comparator_stage_c2_trims.yaml'
    tia_B2 = 'configs/packs/overlays/tia_stage_b2_low_noise.yaml'

    jobs: list[dict] = []

    # Drift knobs: simulate slow vth bias drift, increased comp noise, and window jitter
    drifts = [
        ('vth+0p2', ['--vth-bias-mV','0.2']),
        ('vth+0p5', ['--vth-bias-mV','0.5']),
        ('noise+0p05', ['--comp-input-noise-mV','0.35']),  # from 0.30→0.35
        ('noise+0p10', ['--comp-input-noise-mV','0.40']),  # to 0.40
        ('jit+0p05', ['--base-window-ns','19.05']),
        ('jit-0p05', ['--base-window-ns','18.95']),
    ]
    seed = 9600
    for tag, extra in drifts:
        cmd = list(base) + ['--seed', str(seed)] + extra
        label = f"drift_{tag}_avg3_m0.09375_s{seed}"
        jobs.append({'cmd': cmd,'optics_overlay': optics_E2,'comparator_overlay': comp_C2,'tia_overlay': tia_B2,'json_out': f"out/{label}.json",'label': label})
        seed += 1

    with queue.open('a', encoding='utf-8') as f:
        for j in jobs:
            f.write(json.dumps(j, separators=(',', ':')) + '\n')
    print(f"appended {len(jobs)} drift stress-test jobs to {queue}")


if __name__ == '__main__':
    main()



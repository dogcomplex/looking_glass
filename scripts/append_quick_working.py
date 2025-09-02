from __future__ import annotations
import json
from pathlib import Path


def main() -> None:
    queue = Path('queue/probes.jsonl')
    queue.parent.mkdir(parents=True, exist_ok=True)

    base = [
        '--trials','320','--no-sweeps','--no-drift','--light-output',
        '--apply-calibration','--no-adaptive-input','--no-cold-input',
        '--no-path-b','--path-b-depth','0','--no-path-b-analog',
        '--classifier','chop','--base-window-ns','19.0', '--mask-bad-frac','0.09375',
    ]

    optics_E2 = 'configs/packs/overlays/optics_stage_e2_power_mod.yaml'
    comp_C2 = 'configs/packs/overlays/comparator_stage_c2_trims.yaml'
    tia_B2 = 'configs/packs/overlays/tia_stage_b2_low_noise.yaml'

    jobs: list[dict] = []

    # Best config, avg2 + lite gating (new seeds)
    for s in [9700, 9701]:
        cmd = list(base) + ['--avg-frames','2','--gate-thresh-mV','0.6','--gate-extra-frames','1','--seed',str(s)]
        label = f"quick_E2C2B2_w19p0_avg2_m0.09375_s{s}_g0p6e1"
        jobs.append({'cmd': cmd,'optics_overlay': optics_E2,'comparator_overlay': comp_C2,'tia_overlay': tia_B2,'json_out': f"out/{label}.json",'label': label})

    # Robust variant, avg3 + lite gating
    for s in [9700, 9701]:
        cmd = list(base) + ['--avg-frames','3','--gate-thresh-mV','0.6','--gate-extra-frames','1','--seed',str(s)]
        label = f"quick_E2C2B2_w19p0_avg3_m0.09375_s{s}_g0p6e1"
        jobs.append({'cmd': cmd,'optics_overlay': optics_E2,'comparator_overlay': comp_C2,'tia_overlay': tia_B2,'json_out': f"out/{label}.json",'label': label})

    # Safe drift variants with supported flags
    drift_cases = [
        ('vth+0p2', ['--vth-bias-mV','0.2'], 9710),
        ('noise+0p05', ['--comp-input-noise-mV','0.35'], 9711),
        ('jit+0p05', ['--base-window-ns','19.05'], 9712),
    ]
    for tag, extra, s in drift_cases:
        cmd = list(base) + ['--avg-frames','3','--gate-thresh-mV','0.6','--gate-extra-frames','1','--seed',str(s)] + extra
        label = f"quick_drift_{tag}_avg3_m0.09375_s{s}"
        jobs.append({'cmd': cmd,'optics_overlay': optics_E2,'comparator_overlay': comp_C2,'tia_overlay': tia_B2,'json_out': f"out/{label}.json",'label': label})

    with queue.open('a', encoding='utf-8') as f:
        for j in jobs:
            f.write(json.dumps(j, separators=(',', ':')) + '\n')
    print(f"appended {len(jobs)} quick working jobs to {queue}")


if __name__ == '__main__':
    main()



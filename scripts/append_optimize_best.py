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
        '--classifier','chop', '--base-window-ns','19.0', '--avg-frames','2', '--mask-bad-frac','0.09375',
        '--gate-thresh-mV','0.6','--gate-extra-frames','1',
    ]

    optics_E2 = 'configs/packs/overlays/optics_stage_e2_power_mod.yaml'
    comp_C2 = 'configs/packs/overlays/comparator_stage_c2_trims.yaml'
    tia_B2 = 'configs/packs/overlays/tia_stage_b2_low_noise.yaml'

    jobs: list[dict] = []
    for s in [9301, 9302]:
        # vth optimizer (small)
        cmd = list(base) + ['--seed', str(s), '--optimize-vth', '--opt-vth-iters','2', '--opt-vth-step-mV','0.2', '--opt-vth-use-mask']
        label = f"optbest_E2C2B2_w19p0_avg2_m0.09375_s{s}_vthopt_g0p6e1"
        jobs.append({'cmd': cmd,'optics_overlay': optics_E2,'comparator_overlay': comp_C2,'tia_overlay': tia_B2,'json_out': f"out/{label}.json",'label': label})
        # linear optimizer (small)
        cmd = list(base) + ['--seed', str(s), '--optimize-linear', '--opt-lin-iters','2', '--opt-lin-step-mV','0.2', '--opt-lin-use-mask']
        label = f"optbest_E2C2B2_w19p0_avg2_m0.09375_s{s}_linopt_g0p6e1"
        jobs.append({'cmd': cmd,'optics_overlay': optics_E2,'comparator_overlay': comp_C2,'tia_overlay': tia_B2,'json_out': f"out/{label}.json",'label': label})

    with queue.open('a', encoding='utf-8') as f:
        for j in jobs:
            f.write(json.dumps(j, separators=(',', ':')) + '\n')
    print(f"appended {len(jobs)} optimize-best jobs to {queue}")


if __name__ == '__main__':
    main()



from __future__ import annotations
import json
from pathlib import Path


def main() -> None:
    queue = Path('queue/probes.jsonl')
    queue.parent.mkdir(parents=True, exist_ok=True)

    base = [
        '--trials','320','--no-sweeps','--light-output',
        '--apply-calibration','--no-adaptive-input',
        '--no-cold-input',  # focus on path B loop, final camera readout
        '--classifier','chop','--mask-bad-frac','0.09375',
    ]

    # Use best-known packs; Path B recursion is controlled via flags
    optics = 'configs/packs/overlays/optics_stage_e2_power_mod.yaml'
    comp = 'configs/packs/overlays/comparator_stage_c2_trims.yaml'
    tia = 'configs/packs/overlays/tia_stage_b2_low_noise.yaml'

    jobs: list[dict] = []

    seeds = [8800, 8801]
    depths = ['1','2','3']
    windows = ['18.95','19.0','19.05']
    for s in seeds:
        for d in depths:
            for w in windows:
                # avg2 and avg3 variants, lite gating on avg3
                cmd = list(base) + ['--seed', str(s), '--base-window-ns', w, '--avg-frames','2', '--path-b-depth', d]
                label = f"pathb_w{w.replace('.','p')}_avg2_m0.09375_s{s}_d{d}"
                jobs.append({'cmd': cmd,'optics_overlay': optics,'comparator_overlay': comp,'tia_overlay': tia,'json_out': f"out/{label}.json",'label': label})
                cmd = list(base) + ['--seed', str(s), '--base-window-ns', w, '--avg-frames','3', '--path-b-depth', d, '--gate-thresh-mV','0.6','--gate-extra-frames','1']
                label = f"pathb_w{w.replace('.','p')}_avg3_m0.09375_s{s}_d{d}_g0p6e1"
                jobs.append({'cmd': cmd,'optics_overlay': optics,'comparator_overlay': comp,'tia_overlay': tia,'json_out': f"out/{label}.json",'label': label})

    with queue.open('a', encoding='utf-8') as f:
        for j in jobs:
            f.write(json.dumps(j, separators=(',', ':')) + '\n')
    print(f"appended {len(jobs)} path B suite jobs to {queue}")


if __name__ == '__main__':
    main()



from __future__ import annotations
import json
from pathlib import Path


def main() -> None:
    queue = Path('queue/probes.jsonl')
    queue.parent.mkdir(parents=True, exist_ok=True)

    jobs: list[dict] = []

    optics = 'configs/packs/overlays/optics_projector_dmd_strong.yaml'
    cam_overlay = 'configs/packs/overlays/camera_projector_typ.yaml'
    comp = 'configs/packs/overlays/comparator_stage_c2_trims.yaml'
    tia = 'configs/packs/overlays/tia_stage_b2_low_noise.yaml'

    base = [
        '--trials','480','--no-sweeps','--no-drift','--light-output',
        '--apply-calibration','--no-adaptive-input','--no-path-b','--path-b-depth','0','--no-path-b-analog',
        '--classifier','chop','--normalize-dv','--use-avg-frames-for-path-a',
        '--avg-frames','3','--gate-thresh-mV','0.6','--gate-extra-frames','1',
        '--mask-bad-frac','0.05',
    ]

    seeds = [12801, 12802, 12803]
    windows = ['19.05','19.10']
    chans = [256, 576]

    for seed in seeds:
        for w in windows:
            for ch in chans:
                cmd = list(base) + ['--seed', str(seed), '--base-window-ns', w, '--channels', str(ch)]
                label = f"projbest_dmd_w{w.replace('.','p')}_ch{ch}_s{seed}"
                jobs.append({
                    'label': label,
                    'cmd': cmd,
                    'optics_overlay': optics,
                    'comparator_overlay': comp,
                    'tia_overlay': tia,
                    'camera_overlay': cam_overlay,
                    'json_out': f"out/{label}.json",
                })

    with queue.open('a', encoding='utf-8') as f:
        for j in jobs:
            f.write(json.dumps(j, separators=(',', ':')) + '\n')
    print(f"appended {len(jobs)} projector best-cal runs to {queue}")


if __name__ == '__main__':
    main()

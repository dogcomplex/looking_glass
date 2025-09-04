from __future__ import annotations
import json
from pathlib import Path


def main() -> None:
    queue = Path('queue/probes.jsonl')
    queue.parent.mkdir(parents=True, exist_ok=True)

    jobs: list[dict] = []

    optics = [
        ('mid', 'configs/packs/overlays/optics_projector_mid.yaml'),
        ('iso', 'configs/packs/overlays/optics_projector_isolated.yaml'),
        ('iso_strong', 'configs/packs/overlays/optics_projector_iso_strong.yaml'),
    ]
    cam_overlay = 'configs/packs/overlays/camera_projector_typ.yaml'

    base = [
        '--trials','320','--no-sweeps','--no-drift','--light-output',
        '--apply-calibration','--no-adaptive-input','--no-path-b','--path-b-depth','0','--no-path-b-analog',
        '--classifier','chop','--channels','576',
    ]

    # Pragmatic improvement ladder
    ladders = [
        ('base', []),
        ('norm', ['--normalize-dv']),
        ('avg2', ['--avg-frames','2']),
        ('avg3g', ['--avg-frames','3','--gate-thresh-mV','0.6','--gate-extra-frames','1']),
        ('mask7', ['--mask-bad-frac','0.07']),
        ('mask5', ['--mask-bad-frac','0.05']),
    ]

    seeds = [12701, 12702]
    windows = ['18.95','19.0','19.05']

    for tag, opt in optics:
        for seed in seeds:
            for w in windows:
                for ltag, flags in ladders:
                    cmd = list(base) + ['--seed', str(seed), '--base-window-ns', w] + flags
                    label = f"projimp_{tag}_w{w.replace('.','p')}_{ltag}_ch576_s{seed}"
                    jobs.append({
                        'label': label,
                        'cmd': cmd,
                        'optics_overlay': opt,
                        'comparator_overlay': 'configs/packs/overlays/comparator_stage_c2_trims.yaml',
                        'tia_overlay': 'configs/packs/overlays/tia_stage_b2_low_noise.yaml',
                        'camera_overlay': cam_overlay,
                        'json_out': f"out/{label}.json",
                    })

    with queue.open('a', encoding='utf-8') as f:
        for j in jobs:
            f.write(json.dumps(j, separators=(',', ':')) + '\n')
    print(f"appended {len(jobs)} projector improvement jobs to {queue}")


if __name__ == '__main__':
    main()

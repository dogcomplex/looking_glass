from __future__ import annotations
import json
from pathlib import Path


def main() -> None:
    queue = Path('queue/probes.jsonl')
    queue.parent.mkdir(parents=True, exist_ok=True)

    jobs: list[dict] = []

    # Optics overlays representing projector regimes
    optics_sets = [
        ('low', 'configs/packs/overlays/optics_projector_low.yaml'),
        ('mid', 'configs/packs/overlays/optics_projector_mid.yaml'),
        ('strong', 'configs/packs/overlays/optics_projector_strong.yaml'),
        ('isolated', 'configs/packs/overlays/optics_projector_isolated.yaml'),
    ]

    # Camera overlay tuned for projector visible band
    cam_overlay = 'configs/packs/overlays/camera_projector_typ.yaml'

    # Tricks/options
    tricks = [
        ('base', []),
        ('norm', ['--normalize-dv']),
        ('avg2', ['--avg-frames','2']),
        ('avg3g', ['--avg-frames','3','--gate-thresh-mV','0.6','--gate-extra-frames','1']),
        ('mask10', ['--mask-bad-frac','0.10']),
    ]

    # Channel scales (square numbers)
    chan_counts = [256, 576, 1024]

    base = [
        '--trials','240','--no-sweeps','--no-drift','--light-output',
        '--apply-calibration','--no-adaptive-input','--no-path-b','--path-b-depth','0','--no-path-b-analog',
        '--classifier','chop',
    ]

    seeds = [12601, 12602]
    windows = ['18.9','19.0','19.1']

    for oc_tag, opt_overlay in optics_sets:
        for seed in seeds:
            for w in windows:
                for chans in chan_counts:
                    for t_tag, t_flags in tricks:
                        cmd = list(base) + ['--seed', str(seed), '--base-window-ns', w, '--channels', str(chans)] + t_flags
                        label = f"projector_{oc_tag}_w{w.replace('.','p')}_{t_tag}_ch{chans}_s{seed}"
                        jobs.append({
                            'label': label,
                            'cmd': cmd,
                            'optics_overlay': opt_overlay,
                            'comparator_overlay': 'configs/packs/overlays/comparator_stage_c2_trims.yaml',
                            'tia_overlay': 'configs/packs/overlays/tia_stage_b2_low_noise.yaml',
                            'camera_overlay': cam_overlay,
                            'json_out': f"out/{label}.json",
                        })

    with queue.open('a', encoding='utf-8') as f:
        for j in jobs:
            f.write(json.dumps(j, separators=(',', ':')) + '\n')
    print(f"appended {len(jobs)} projector variant jobs to {queue}")


if __name__ == '__main__':
    main()

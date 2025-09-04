from __future__ import annotations
import json
from pathlib import Path


def main() -> None:
    queue = Path('queue/probes.jsonl')
    queue.parent.mkdir(parents=True, exist_ok=True)

    jobs: list[dict] = []

    # Overlays: amp-only, SA-only, both
    optics_amp = 'configs/packs/overlays/optics_stage_f_amp.yaml'
    optics_sa = 'configs/packs/overlays/optics_stage_g_saturable.yaml'
    optics_both = 'configs/packs/overlays/optics_stage_fg_amp_sat.yaml'
    comp = 'configs/packs/overlays/comparator_stage_c2_trims.yaml'
    tia = 'configs/packs/overlays/tia_stage_b2_low_noise.yaml'

    windows = ['18.90','19.00','19.10']
    depths = ['1','2','3','4']
    modes = [
        ('avg2', ['--avg-frames','2'], ''),
        ('avg3g', ['--avg-frames','3','--gate-thresh-mV','0.6','--gate-extra-frames','1'], '_g0p6e1'),
    ]
    base = [
        '--trials','320','--no-sweeps','--no-drift','--light-output',
        '--apply-calibration','--no-adaptive-input','--no-cold-input',
        '--classifier','chop','--mask-bad-frac','0.09375',
    ]

    seed = 12501
    for w in windows:
        for d in depths:
            for tag, flags, suffix in modes:
                for o_name, optics in (
                    ('amp', optics_amp),
                    ('sa', optics_sa),
                    ('amp_sa', optics_both),
                ):
                    cmd = list(base) + ['--seed', str(seed), '--base-window-ns', w, '--path-b-analog-depth', d] + flags
                    label = f"pathb_{o_name}_w{w.replace('.','p')}_{tag}_m0.09375_s{seed}_d{d}{suffix}"
                    jobs.append({
                        'label': label,
                        'cmd': cmd,
                        'optics_overlay': optics,
                        'comparator_overlay': comp,
                        'tia_overlay': tia,
                        'json_out': f"out/{label}.json",
                    })
            seed += 1

    with queue.open('a', encoding='utf-8') as f:
        for j in jobs:
            f.write(json.dumps(j, separators=(',', ':')) + '\n')
    print(f"appended {len(jobs)} path B amp/SA sweep jobs to {queue}")


if __name__ == '__main__':
    main()



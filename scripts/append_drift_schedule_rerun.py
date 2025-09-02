from __future__ import annotations
import json
from pathlib import Path


def main() -> None:
    queue = Path('queue/probes.jsonl')
    queue.parent.mkdir(parents=True, exist_ok=True)

    base_common = [
        '--trials','320','--no-sweeps','--light-output',
        '--apply-calibration','--no-adaptive-input','--no-cold-input',
        '--no-path-b','--path-b-depth','0','--no-path-b-analog',
        '--classifier','chop','--avg-frames','3','--mask-bad-frac','0.09375',
        '--gate-thresh-mV','0.6','--gate-extra-frames','1',
    ]

    optics = 'configs/packs/overlays/optics_stage_e2_power_mod.yaml'
    comp = 'configs/packs/overlays/comparator_stage_c2_trims.yaml'
    tia = 'configs/packs/overlays/tia_stage_b2_low_noise.yaml'

    slices = [
        ('T0', '19.00', '0.0', '0.30', True),
        ('T1', '19.02', '0.1', '0.32', False),
        ('T2', '19.04', '0.2', '0.34', False),
        ('T3', '19.06', '0.3', '0.36', True),
        ('T4', '19.08', '0.4', '0.38', False),
        ('T5', '19.10', '0.5', '0.40', False),
    ]

    jobs: list[dict] = []
    for seed in (9922, 9923):
        for tag, win, vth_b, noise, retrim in slices:
            cmd = list(base_common) + [
                '--seed', str(seed), '--base-window-ns', win,
                '--vth-bias-mV', vth_b, '--comp-input-noise-mV', noise,
            ]
            if not retrim:
                cmd += ['--no-cal']
            label = f"driftsched2_{tag}_w{win.replace('.', 'p')}_avg3_m0.09375_s{seed}_vth{vth_b}_n{noise}{'' if retrim else '_nocal'}"
            jobs.append({
                'cmd': cmd,
                'optics_overlay': optics,
                'comparator_overlay': comp,
                'tia_overlay': tia,
                'json_out': f"out/{label}.json",
                'label': label,
            })

    with queue.open('a', encoding='utf-8') as f:
        for j in jobs:
            f.write(json.dumps(j, separators=(',', ':')) + '\n')
    print(f"appended {len(jobs)} drift-schedule rerun jobs to {queue}")


if __name__ == '__main__':
    main()



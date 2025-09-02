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
        '--classifier','chop','--base-window-ns','19.0', '--mask-bad-frac','0.09375',
        '--avg-frames','3','--gate-thresh-mV','0.6','--gate-extra-frames','1',
        '--seed','9800',
    ]

    optics_bad = 'configs/packs/overlays/optics_stress_ct_stray.yaml'
    comp_bad = 'configs/packs/overlays/comparator_stress_sigma.yaml'
    tia_bad = 'configs/packs/overlays/tia_stress_gainvar.yaml'

    jobs: list[dict] = []

    # Combine one bad overlay at a time and all together
    cases = [
        ('opticsBad', optics_bad, 'configs/packs/overlays/comparator_stage_c2_trims.yaml', 'configs/packs/overlays/tia_stage_b2_low_noise.yaml'),
        ('compBad', 'configs/packs/overlays/optics_stage_e2_power_mod.yaml', comp_bad, 'configs/packs/overlays/tia_stage_b2_low_noise.yaml'),
        ('tiaBad', 'configs/packs/overlays/optics_stage_e2_power_mod.yaml', 'configs/packs/overlays/comparator_stage_c2_trims.yaml', tia_bad),
        ('allBad', optics_bad, comp_bad, tia_bad),
    ]

    for tag, opt, comp, tia in cases:
        cmd = list(base)
        label = f"invalidate_{tag}_avg3_m0.09375_s9800"
        jobs.append({'cmd': cmd,'optics_overlay': opt,'comparator_overlay': comp,'tia_overlay': tia,'json_out': f"out/{label}.json",'label': label})

    with queue.open('a', encoding='utf-8') as f:
        for j in jobs:
            f.write(json.dumps(j, separators=(',', ':')) + '\n')
    print(f"appended {len(jobs)} invalidation stress jobs to {queue}")


if __name__ == '__main__':
    main()



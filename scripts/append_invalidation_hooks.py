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
        '--classifier','chop','--base-window-ns','19.0','--mask-bad-frac','0.09375',
        '--avg-frames','3','--gate-thresh-mV','0.6','--gate-extra-frames','1',
    ]

    # Use good combo with stress overlays layered on top
    optics_good = 'configs/packs/overlays/optics_stage_e2_power_mod.yaml'
    comp_good = 'configs/packs/overlays/comparator_stage_c2_trims.yaml'
    tia_good = 'configs/packs/overlays/tia_stage_b2_low_noise.yaml'

    optics_speckle = 'configs/packs/overlays/optics_speckle_stress.yaml'
    comp_meta = 'configs/packs/overlays/comparator_metastable_stress.yaml'

    jobs: list[dict] = []

    # Speckle only, metastability only, both
    cases = [
        ('speckle', optics_speckle, comp_good, tia_good),
        ('meta', optics_good, comp_meta, tia_good),
        ('speckle_meta', optics_speckle, comp_meta, tia_good),
    ]

    seed = 9950
    for tag, opt, comp, tia in cases:
        cmd = list(base) + ['--seed', str(seed)]
        label = f"invhooks_{tag}_avg3_m0.09375_s{seed}"
        jobs.append({'cmd': cmd,'optics_overlay': opt,'comparator_overlay': comp,'tia_overlay': tia,'json_out': f"out/{label}.json",'label': label})
        seed += 1

    with queue.open('a', encoding='utf-8') as f:
        for j in jobs:
            f.write(json.dumps(j, separators=(',', ':')) + '\n')
    print(f"appended {len(jobs)} invalidation hook jobs to {queue}")


if __name__ == '__main__':
    main()



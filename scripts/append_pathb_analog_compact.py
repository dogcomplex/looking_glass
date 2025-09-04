from __future__ import annotations
import json
from pathlib import Path


def main() -> None:
    queue = Path('queue/probes.jsonl')
    queue.parent.mkdir(parents=True, exist_ok=True)

    jobs: list[dict] = []

    # Base overlays (good) and stress overlays
    optics_good = 'configs/packs/overlays/optics_stage_e2_power_mod.yaml'
    comp_good = 'configs/packs/overlays/comparator_stage_c2_trims.yaml'
    tia_good = 'configs/packs/overlays/tia_stage_b2_low_noise.yaml'
    optics_speckle = 'configs/packs/overlays/optics_speckle_stress.yaml'
    comp_meta = 'configs/packs/overlays/comparator_metastable_stress.yaml'

    # Compact grid
    seed = 12421  # fresh seed to avoid skip
    windows = ['18.90','19.00','19.10']
    depths = ['1','2','3','4','5','6']
    avg_variants = [
        ('avg2', ['--avg-frames','2'], ''),
        ('avg3g', ['--avg-frames','3','--gate-thresh-mV','0.6','--gate-extra-frames','1'], '_g0p6e1'),
    ]
    overlay_cases = [
        ('base', optics_good, comp_good),
        ('spkm_meta', optics_speckle, comp_meta),
    ]

    base = [
        '--trials','320','--no-sweeps','--no-drift','--light-output',
        '--apply-calibration','--no-adaptive-input','--no-cold-input',
        '--classifier','chop','--mask-bad-frac','0.09375',
    ]

    for w in windows:
        for d in depths:
            for mode_tag, mode_flags, suffix in avg_variants:
                for o_tag, opt_overlay, comp_overlay in overlay_cases:
                    cmd = list(base) + ['--seed', str(seed), '--base-window-ns', w, '--path-b-analog-depth', d] + mode_flags
                    label = f"pathbanalog_{o_tag}_w{w.replace('.','p')}_{mode_tag}_m0.09375_s{seed}_d{d}{suffix}"
                    jobs.append({
                        'label': label,
                        'cmd': cmd,
                        'optics_overlay': opt_overlay,
                        'comparator_overlay': comp_overlay,
                        'tia_overlay': tia_good,
                        'json_out': f"out/{label}.json",
                    })
            seed += 1

    with queue.open('a', encoding='utf-8') as f:
        for j in jobs:
            f.write(json.dumps(j, separators=(',', ':')) + '\n')
    print(f"appended {len(jobs)} path B analog compact sweep jobs to {queue}")


if __name__ == '__main__':
    main()



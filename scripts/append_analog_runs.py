from __future__ import annotations
import json
from pathlib import Path


def main() -> None:
    queue = Path('queue/probes.jsonl')
    queue.parent.mkdir(parents=True, exist_ok=True)

    jobs: list[dict] = []

    # Base good overlays (E2+C2+B2) and stress overlays layered via runner merge
    optics_good = 'configs/packs/overlays/optics_stage_e2_power_mod.yaml'
    comp_good = 'configs/packs/overlays/comparator_stage_c2_trims.yaml'
    tia_good = 'configs/packs/overlays/tia_stage_b2_low_noise.yaml'
    optics_speckle = 'configs/packs/overlays/optics_speckle_stress.yaml'
    comp_meta = 'configs/packs/overlays/comparator_metastable_stress.yaml'

    # 1) Cold analog input (Path A), clearly marked and fresh seeds
    cold_cases = [
        ('cold_lockin_avg2', ['--trials','320','--seed','12051','--no-sweeps','--no-drift','--light-output',
                               '--base-window-ns','19.0','--classifier','lockin','--lockin','--avg-frames','2',
                               '--apply-calibration','--no-path-b','--path-b-depth','0','--no-path-b-analog']),
        ('cold_chop_avg3',   ['--trials','320','--seed','12052','--no-sweeps','--no-drift','--light-output',
                               '--base-window-ns','19.0','--classifier','chop','--chop','--avg-frames','3',
                               '--apply-calibration','--no-path-b','--path-b-depth','0','--no-path-b-analog']),
        ('cold_avg_norm',    ['--trials','320','--seed','12053','--no-sweeps','--no-drift','--light-output',
                               '--base-window-ns','19.0','--classifier','avg','--avg-frames','2','--normalize-dv',
                               '--apply-calibration','--no-path-b','--path-b-depth','0','--no-path-b-analog']),
    ]
    for tag, cmd in cold_cases:
        label = f"analoginput_{tag}_w19_s{cmd[3]}"
        jobs.append({
            'label': label,
            'cmd': cmd,
            'optics_overlay': optics_speckle,  # stress speckle on cold input
            'comparator_overlay': comp_meta,
            'tia_overlay': tia_good,
            'json_out': f"out/{label}.json",
        })

    # 2) Path B analog loop runs (analog stages), clearly marked and fresh seeds
    pathb_cases = [
        ('pathb_anlg_d2_lockin', ['--trials','320','--seed','12101','--no-sweeps','--no-drift','--light-output',
                                   '--base-window-ns','19.0','--classifier','lockin','--lockin',
                                   '--path-b-analog-depth','2']),
        ('pathb_anlg_d3_chop',   ['--trials','320','--seed','12102','--no-sweeps','--no-drift','--light-output',
                                   '--base-window-ns','19.0','--classifier','chop','--chop',
                                   '--path-b-analog-depth','3']),
        ('pathb_anlg_d5_avg2',   ['--trials','320','--seed','12103','--no-sweeps','--no-drift','--light-output',
                                   '--base-window-ns','19.0','--classifier','avg','--avg-frames','2',
                                   '--path-b-analog-depth','5']),
    ]
    for tag, cmd in pathb_cases:
        label = f"analogpath_{tag}_w19_s{cmd[3]}"
        jobs.append({
            'label': label,
            'cmd': cmd,
            'optics_overlay': optics_good,   # start from good optics; rely on analog path dynamics
            'comparator_overlay': comp_good,
            'tia_overlay': tia_good,
            'json_out': f"out/{label}.json",
        })

    with queue.open('a', encoding='utf-8') as f:
        for j in jobs:
            f.write(json.dumps(j, separators=(',', ':')) + '\n')
    print(f"appended {len(jobs)} analog-input/path jobs to {queue}")


if __name__ == '__main__':
    main()



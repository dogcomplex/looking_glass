from __future__ import annotations
import json
from pathlib import Path


def main() -> None:
    queue = Path('queue/probes.jsonl')
    queue.parent.mkdir(parents=True, exist_ok=True)

    jobs: list[dict] = []

    # Good overlays
    optics_e2 = 'configs/packs/overlays/optics_stage_e2_power_mod.yaml'
    comp_c2 = 'configs/packs/overlays/comparator_stage_c2_trims.yaml'
    tia_b2 = 'configs/packs/overlays/tia_stage_b2_low_noise.yaml'

    # Robust preset knobs
    preset = ['--mask-bad-frac','0.09375','--avg-frames','3','--gate-thresh-mV','0.6','--gate-extra-frames','1']

    # Cold analog input (Path A), tuned robust
    cold = [
        ('cold_chop_avg3_gated', ['--trials','320','--seed','12251','--no-sweeps','--no-drift','--light-output',
                                   '--base-window-ns','19.0','--classifier','chop','--chop','--apply-calibration',
                                   *preset, '--no-path-b','--path-b-depth','0','--no-path-b-analog']),
        ('cold_lockin_avg3_gated', ['--trials','320','--seed','12252','--no-sweeps','--no-drift','--light-output',
                                     '--base-window-ns','19.0','--classifier','lockin','--lockin','--apply-calibration',
                                     *preset, '--no-path-b','--path-b-depth','0','--no-path-b-analog']),
    ]
    for tag, cmd in cold:
        label = f"analoginput_{tag}_w19_s{cmd[3]}"
        jobs.append({
            'label': label,
            'cmd': cmd,
            'optics_overlay': optics_e2,
            'comparator_overlay': comp_c2,
            'tia_overlay': tia_b2,
            'json_out': f"out/{label}.json",
        })

    # Path B analog loop, tuned robust at depths 2..4
    pathb = [
        ('pathb_d2_chop_avg3_gated', ['--trials','320','--seed','12351','--no-sweeps','--no-drift','--light-output',
                                       '--base-window-ns','19.0','--classifier','chop','--chop','--apply-calibration',
                                       *preset, '--path-b-analog-depth','2']),
        ('pathb_d3_chop_avg3_gated', ['--trials','320','--seed','12352','--no-sweeps','--no-drift','--light-output',
                                       '--base-window-ns','19.0','--classifier','chop','--chop','--apply-calibration',
                                       *preset, '--path-b-analog-depth','3']),
        ('pathb_d4_chop_avg3_gated', ['--trials','320','--seed','12353','--no-sweeps','--no-drift','--light-output',
                                       '--base-window-ns','19.0','--classifier','chop','--chop','--apply-calibration',
                                       *preset, '--path-b-analog-depth','4']),
    ]
    for tag, cmd in pathb:
        label = f"analogpath_{tag}_w19_s{cmd[3]}"
        jobs.append({
            'label': label,
            'cmd': cmd,
            'optics_overlay': optics_e2,
            'comparator_overlay': comp_c2,
            'tia_overlay': tia_b2,
            'json_out': f"out/{label}.json",
        })

    with queue.open('a', encoding='utf-8') as f:
        for j in jobs:
            f.write(json.dumps(j, separators=(',', ':')) + '\n')
    print(f"appended {len(jobs)} tuned analog-input/path jobs to {queue}")


if __name__ == '__main__':
    main()



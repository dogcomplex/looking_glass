from __future__ import annotations
import json
from pathlib import Path


def main() -> None:
    queue = Path('queue/probes.jsonl')
    queue.parent.mkdir(parents=True, exist_ok=True)

    jobs: list[dict] = []

    optics_upper = 'configs/packs/overlays/optics_upper_bound.yaml'
    optics_e2 = 'configs/packs/overlays/optics_stage_e2_power_mod.yaml'
    comp_c2 = 'configs/packs/overlays/comparator_stage_c2_trims.yaml'
    tia_b2 = 'configs/packs/overlays/tia_stage_b2_low_noise.yaml'

    seeds = ['9901','9902']
    # Upper bound optics, see if plateau breaks
    for s in seeds:
        cmd = [
            '--trials','1400','--no-sweeps','--light-output','--apply-calibration',
            '--no-adaptive-input','--no-cold-input','--no-path-b','--path-b-depth','0','--no-path-b-analog',
            '--classifier','chop','--channels','16','--base-window-ns','19.0','--avg-frames','3',
            '--mask-bad-frac','0.09375','--seed', s,'--gate-thresh-mV','0.6','--gate-extra-frames','1',
        ]
        label = f"accept_upper_ch16_w19p0_avg3_m0.09375_s{s}_g0p6e1"
        jobs.append({'label': label,'cmd': cmd,'optics_overlay': optics_upper,'comparator_overlay': comp_c2,'tia_overlay': tia_b2,'json_out': f"out/{label}.json"})

    # Slow-mode acceptance: longer window to see if integration lifts SNR
    for w in ['24.0','28.0']:
        cmd = [
            '--trials','1200','--no-sweeps','--light-output','--apply-calibration',
            '--no-adaptive-input','--no-cold-input','--no-path-b','--path-b-depth','0','--no-path-b-analog',
            '--classifier','chop','--channels','16','--base-window-ns', w,'--avg-frames','3',
            '--mask-bad-frac','0.09375','--seed','9903','--gate-thresh-mV','0.6','--gate-extra-frames','1',
        ]
        label = f"accept_slow_ch16_w{w.replace('.','p')}_avg3_m0.09375_s9903_g0p6e1"
        jobs.append({'label': label,'cmd': cmd,'optics_overlay': optics_e2,'comparator_overlay': comp_c2,'tia_overlay': tia_b2,'json_out': f"out/{label}.json"})

    # Normalized acceptance variant
    for s in seeds:
        cmd = [
            '--trials','1200','--no-sweeps','--light-output','--apply-calibration',
            '--no-adaptive-input','--no-cold-input','--no-path-b','--path-b-depth','0','--no-path-b-analog',
            '--classifier','chop','--channels','16','--base-window-ns','19.0','--avg-frames','3',
            '--mask-bad-frac','0.09375','--seed', s,'--gate-thresh-mV','0.6','--gate-extra-frames','1',
            '--normalize-dv',
        ]
        label = f"accept_norm_ch16_w19p0_avg3_m0.09375_s{s}_g0p6e1"
        jobs.append({'label': label,'cmd': cmd,'optics_overlay': optics_e2,'comparator_overlay': comp_c2,'tia_overlay': tia_b2,'json_out': f"out/{label}.json"})

    with queue.open('a', encoding='utf-8') as f:
        for j in jobs:
            f.write(json.dumps(j, separators=(',', ':')) + '\n')
    print(f"appended {len(jobs)} upper-bound and slow-mode acceptance jobs to {queue}")


if __name__ == '__main__':
    main()



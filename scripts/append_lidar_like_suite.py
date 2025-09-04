from __future__ import annotations
import json
from pathlib import Path


def main() -> None:
    queue = Path('queue/probes.jsonl')
    queue.parent.mkdir(parents=True, exist_ok=True)

    jobs: list[dict] = []

    comp = 'configs/packs/overlays/comparator_stage_c2_trims.yaml'
    tia = 'configs/packs/overlays/tia_stage_b2_low_noise.yaml'
    optics_ambient = 'configs/packs/overlays/optics_ambient_stress.yaml'

    # Compare lock-in vs chop/avg under ambient stress at small channel counts
    chans = ['1','2','8','16']
    windows = ['18.0','19.0','20.0']
    for ch in chans:
        for w in windows:
            # Lock-in path
            cmd_li = [
                '--trials','800','--no-sweeps','--light-output','--apply-calibration',
                '--no-adaptive-input','--no-path-b','--path-b-depth','0','--no-path-b-analog',
                '--classifier','lockin','--lockin','--channels', ch,
                '--base-window-ns', w, '--avg-frames','2', '--mask-bad-frac','0.05', '--seed','14801'
            ]
            label = f"lidar_like_lockin_ch{ch}_w{w.replace('.','p')}_avg2_m0p05"
            jobs.append({'label': label,'cmd': cmd_li,'optics_overlay': optics_ambient,'comparator_overlay': comp,'tia_overlay': tia,'json_out': f"out/{label}.json"})

            # Baseline chop/avg
            cmd_bl = [
                '--trials','800','--no-sweeps','--light-output','--apply-calibration',
                '--no-adaptive-input','--no-path-b','--path-b-depth','0','--no-path-b-analog',
                '--classifier','chop','--chop','--channels', ch,
                '--base-window-ns', w, '--avg-frames','3', '--normalize-dv', '--gate-thresh-mV','0.6','--gate-extra-frames','1',
                '--mask-bad-frac','0.05', '--seed','14802'
            ]
            label = f"lidar_like_baseline_ch{ch}_w{w.replace('.','p')}_avg3_norm_g0p6e1_m0p05"
            jobs.append({'label': label,'cmd': cmd_bl,'optics_overlay': optics_ambient,'comparator_overlay': comp,'tia_overlay': tia,'json_out': f"out/{label}.json"})

    with queue.open('a', encoding='utf-8') as f:
        for j in jobs:
            f.write(json.dumps(j, separators=(',', ':')) + '\n')
    print(f"appended {len(jobs)} LiDAR-like ambient lock-in vs baseline jobs to {queue}")


if __name__ == '__main__':
    main()



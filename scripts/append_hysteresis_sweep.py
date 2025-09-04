from __future__ import annotations
import json
from pathlib import Path


def main() -> None:
    queue = Path('queue/probes.jsonl')
    queue.parent.mkdir(parents=True, exist_ok=True)

    jobs: list[dict] = []

    optics = 'configs/packs/overlays/optics_iso_boost2.yaml'
    comp = 'configs/packs/overlays/comparator_stage_c2_trims.yaml'
    tia = 'configs/packs/overlays/tia_stage_b2_low_noise.yaml'

    channels = ['16','32']
    windows = ['18.9','19.0','19.1']
    hysteresis = ['0.3','0.4','0.5','0.7','0.8']

    for ch in channels:
        for w in windows:
            for h in hysteresis:
                cmd = [
                    '--trials','900','--no-sweeps','--light-output','--apply-calibration',
                    '--no-adaptive-input','--no-cold-input','--no-path-b','--path-b-depth','0','--no-path-b-analog',
                    '--classifier','chop','--channels', ch,'--base-window-ns', w,'--avg-frames','3',
                    '--mask-bad-frac','0.09375','--seed','9801','--gate-thresh-mV','0.6','--gate-extra-frames','1',
                    '--comp-hysteresis-mV', h,
                ]
                label = f"hyst_ch{ch}_w{w.replace('.','p')}_avg3_m0.09375_s9801_g0p6e1_h{h.replace('.','p')}"
                jobs.append({'label': label,'cmd': cmd,'optics_overlay': optics,'comparator_overlay': comp,'tia_overlay': tia,'json_out': f"out/{label}.json"})

    with queue.open('a', encoding='utf-8') as f:
        for j in jobs:
            f.write(json.dumps(j, separators=(',', ':')) + '\n')
    print(f"appended {len(jobs)} hysteresis sweep jobs to {queue}")


if __name__ == '__main__':
    main()



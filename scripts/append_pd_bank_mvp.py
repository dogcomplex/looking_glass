from __future__ import annotations
import json
from pathlib import Path


def main() -> None:
    queue = Path('queue/probes.jsonl')
    queue.parent.mkdir(parents=True, exist_ok=True)

    jobs: list[dict] = []

    optics = 'configs/packs/overlays/optics_stage_e2_power_mod.yaml'
    comp = 'configs/packs/overlays/comparator_stage_c2_trims.yaml'
    tia = 'configs/packs/overlays/tia_stage_b2_low_noise.yaml'

    for ch in ['2','4','8','16']:
        for w in ['18.5','19.0','19.5']:
            cmd = [
                '--trials','1000','--no-sweeps','--light-output','--apply-calibration',
                '--no-adaptive-input','--no-cold-input','--no-path-b','--path-b-depth','0','--no-path-b-analog',
                '--classifier','chop','--channels', ch,'--base-window-ns', w,'--avg-frames','3',
                '--mask-bad-frac','0.09375','--seed','9601','--gate-thresh-mV','0.6','--gate-extra-frames','1',
            ]
            label = f"pdbank_mvp_ch{ch}_w{w.replace('.','p')}_avg3_m0.09375_s9601_g0p6e1"
            jobs.append({'label': label,'cmd': cmd,'optics_overlay': optics,'comparator_overlay': comp,'tia_overlay': tia,'json_out': f"out/{label}.json"})

    with queue.open('a', encoding='utf-8') as f:
        for j in jobs:
            f.write(json.dumps(j, separators=(',', ':')) + '\n')
    print(f"appended {len(jobs)} PD bank MVP jobs to {queue}")


if __name__ == '__main__':
    main()



from __future__ import annotations
import json
from pathlib import Path


def main() -> None:
    queue = Path('queue/probes.jsonl')
    queue.parent.mkdir(parents=True, exist_ok=True)

    jobs: list[dict] = []

    # Tiers: Stage A hygiene vs Stage E2 power/iso boost; comparator/TIA: trims vs precision
    optics_tiers = [
        ('A', 'configs/packs/overlays/optics_stage_a_hygiene.yaml'),
        ('E2', 'configs/packs/overlays/optics_stage_e2_power_mod.yaml'),
        ('ISO2', 'configs/packs/overlays/optics_iso_boost2.yaml'),
    ]
    comp_tiers = [
        ('C2', 'configs/packs/overlays/comparator_stage_c2_trims.yaml'),
        ('C3', 'configs/packs/overlays/comparator_stage_c3_precision.yaml'),
    ]
    tia_tiers = [
        ('B2', 'configs/packs/overlays/tia_stage_b2_low_noise.yaml'),
        ('B3', 'configs/packs/overlays/tia_stage_b3_precision.yaml'),
    ]

    channels = ['8','16']
    windows = ['18.95','19.0','19.05']

    for (o_tag, o_path) in optics_tiers:
        for (c_tag, c_path) in comp_tiers:
            for (t_tag, t_path) in tia_tiers:
                for ch in channels:
                    for w in windows:
                        label = f"tier_{o_tag}_{c_tag}_{t_tag}_ch{ch}_w{w.replace('.','p')}_avg3_m0.09375_s10201_g0p6e1"
                        cmd = [
                            '--trials','1000','--no-sweeps','--light-output','--apply-calibration',
                            '--no-adaptive-input','--no-cold-input','--no-path-b','--path-b-depth','0','--no-path-b-analog',
                            '--classifier','chop','--channels', ch,'--base-window-ns', w,'--avg-frames','3',
                            '--mask-bad-frac','0.09375','--seed','10201','--gate-thresh-mV','0.6','--gate-extra-frames','1',
                        ]
                        jobs.append({'label': label,'cmd': cmd,'optics_overlay': o_path,'comparator_overlay': c_path,'tia_overlay': t_path,'json_out': f"out/{label}.json"})

    with queue.open('a', encoding='utf-8') as f:
        for j in jobs:
            f.write(json.dumps(j, separators=(',', ':')) + '\n')
    print(f"appended {len(jobs)} tier sensitivity jobs to {queue}")


if __name__ == '__main__':
    main()



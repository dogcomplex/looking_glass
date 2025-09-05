from __future__ import annotations
import json
from pathlib import Path


def main() -> None:
    queue = Path('queue/probes.jsonl')
    queue.parent.mkdir(parents=True, exist_ok=True)

    jobs: list[dict] = []

    comp = 'configs/packs/overlays/comparator_stage_c2_trims.yaml'
    tia = 'configs/packs/overlays/tia_stage_b2_low_noise.yaml'
    optics = 'configs/packs/overlays/optics_stage_e2_power_mod.yaml'

    # Emitter variants: budget noisy diode, VCSEL 8-ch, baseline packs
    emitters = [
        ('budget', 'configs/packs/overlays/emitter_budget_noisy.yaml'),
        ('vcsel8', 'configs/packs/overlays/emitter_vcsel_array_8ch.yaml'),
        ('obistyp', 'configs/packs/vendors/emitters/coherent_OBIS-850-nm_typ.yaml'),
    ]

    for tag, emit_pack in emitters:
        for ch in ['8','16']:
            label = f"emit_{tag}_ch{ch}_w19p0_avg3_m0.09375_s10501_g0p6e1"
            cmd = [
                '--trials','1000','--no-sweeps','--light-output','--apply-calibration',
                '--no-adaptive-input','--no-cold-input','--no-path-b','--path-b-depth','0','--no-path-b-analog',
                '--classifier','chop','--channels', ch,'--base-window-ns', '19.0','--avg-frames','3',
                '--mask-bad-frac','0.09375','--seed','10501','--gate-thresh-mV','0.6','--gate-extra-frames','1',
            ]
            jobs.append({
                'label': label,
                'cmd': cmd,
                'emitter_pack': emit_pack,
                'optics_overlay': optics,
                'comparator_overlay': comp,
                'tia_overlay': tia,
                'json_out': f"out/{label}.json",
            })

    with queue.open('a', encoding='utf-8') as f:
        for j in jobs:
            f.write(json.dumps(j, separators=(',', ':')) + '\n')
    print(f"appended {len(jobs)} cost-down emitter jobs to {queue}")


if __name__ == '__main__':
    main()



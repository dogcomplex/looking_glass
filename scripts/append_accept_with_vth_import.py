from __future__ import annotations
import json
from pathlib import Path


def main() -> None:
    queue = Path('queue/probes.jsonl')
    queue.parent.mkdir(parents=True, exist_ok=True)

    jobs: list[dict] = []

    optics = 'configs/packs/overlays/optics_stage_e2_power_mod.yaml'
    optics_grid = 'configs/packs/overlays/optics_accept_grid256.yaml'
    comp = 'configs/packs/overlays/comparator_stage_c2_trims.yaml'
    tia = 'configs/packs/overlays/tia_stage_b2_low_noise.yaml'

    # Export Vth at 16/32 ch, then import and run acceptance
    for ch in ['16','32']:
        export_label = f"accept_export_vth_ch{ch}_w19p0_avg3_m0.09375_s9951"
        export_cmd = [
            '--trials','600','--no-sweeps','--light-output','--apply-calibration',
            '--no-adaptive-input','--no-cold-input','--no-path-b','--path-b-depth','0','--no-path-b-analog',
            '--classifier','chop','--channels', ch,'--base-window-ns','19.0','--avg-frames','3',
            '--mask-bad-frac','0.09375','--seed','9951',
        ]
        jobs.append({'label': export_label,'cmd': export_cmd,'optics_overlay': optics,'comparator_overlay': comp,'tia_overlay': tia,'export_vth': f"out/{export_label}_vth.json",'json_out': f"out/{export_label}.json"})

        import_label = f"accept_import_vth_ch{ch}_w19p0_avg3_m0.09375_s9952"
        import_cmd = [
            '--trials','1200','--no-sweeps','--light-output','--apply-calibration',
            '--no-adaptive-input','--no-cold-input','--no-path-b','--path-b-depth','0','--no-path-b-analog',
            '--classifier','chop','--channels', ch,'--base-window-ns','19.0','--avg-frames','3',
            '--mask-bad-frac','0.09375','--seed','9952','--gate-thresh-mV','0.6','--gate-extra-frames','1',
        ]
        jobs.append({'label': import_label,'cmd': import_cmd,'optics_overlay': optics,'comparator_overlay': comp,'tia_overlay': tia,'import_vth': f"out/{export_label}_vth.json",'json_out': f"out/{import_label}.json"})

    # High-res projector-like grid acceptance variant (16 ch)
    for w in ['18.95','19.00','19.05']:
        label = f"accept_grid256_ch16_w{w.replace('.','p')}_avg3_m0.09375_s9961_g0p6e1"
        cmd = [
            '--trials','1200','--no-sweeps','--light-output','--apply-calibration',
            '--no-adaptive-input','--no-cold-input','--no-path-b','--path-b-depth','0','--no-path-b-analog',
            '--classifier','chop','--channels','16','--base-window-ns', w,'--avg-frames','3',
            '--mask-bad-frac','0.09375','--seed','9961','--gate-thresh-mV','0.6','--gate-extra-frames','1',
        ]
        jobs.append({'label': label,'cmd': cmd,'optics_overlay': optics_grid,'comparator_overlay': comp,'tia_overlay': tia,'json_out': f"out/{label}.json"})

    with queue.open('a', encoding='utf-8') as f:
        for j in jobs:
            f.write(json.dumps(j, separators=(',', ':')) + '\n')
    print(f"appended {len(jobs)} acceptance with Vth import and grid256 jobs to {queue}")


if __name__ == '__main__':
    main()



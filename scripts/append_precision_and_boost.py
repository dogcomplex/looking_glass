from __future__ import annotations
import json
from pathlib import Path


def main() -> None:
    queue = Path('queue/probes.jsonl')
    queue.parent.mkdir(parents=True, exist_ok=True)

    jobs: list[dict] = []

    comp_prec = 'configs/packs/overlays/comparator_stage_c3_precision.yaml'
    tia_prec = 'configs/packs/overlays/tia_stage_b3_precision.yaml'
    optics_iso_boost = 'configs/packs/overlays/optics_iso_boost.yaml'
    optics_iso_boost2 = 'configs/packs/overlays/optics_iso_boost2.yaml'

    for optics in (optics_iso_boost, optics_iso_boost2):
        for ch in ['16','32']:
            for w in ['18.9','19.0','19.1']:
                for m in ['0.09375','0.11']:
                    cmd = [
                        '--trials','1000','--no-sweeps','--light-output','--apply-calibration',
                        '--no-adaptive-input','--no-cold-input','--no-path-b','--path-b-depth','0','--no-path-b-analog',
                        '--classifier','chop','--channels', ch,'--base-window-ns', w,'--avg-frames','3',
                        '--mask-bad-frac', m,'--seed','9701','--gate-thresh-mV','0.6','--gate-extra-frames','1',
                    ]
                    label = f"prec_boost_ch{ch}_w{w.replace('.','p')}_avg3_m{m}_s9701_g0p6e1_{Path(optics).stem}"
                    jobs.append({'label': label,'cmd': cmd,'optics_overlay': optics,'comparator_overlay': comp_prec,'tia_overlay': tia_prec,'json_out': f"out/{label}.json"})

    # Tile gain variation sweep to estimate equalization needs
    optics_gainvar = 'configs/packs/overlays/optics_projector_iso_strong.yaml'
    for pct in ['0.0','1.0','2.0','3.0']:
        cmd = [
            '--trials','900','--no-sweeps','--light-output','--apply-calibration',
            '--no-adaptive-input','--no-cold-input','--no-path-b','--path-b-depth','0','--no-path-b-analog',
            '--classifier','chop','--channels','32','--base-window-ns','19.0','--avg-frames','3',
            '--mask-bad-frac','0.09375','--seed','9711','--gate-thresh-mV','0.6','--gate-extra-frames','1',
        ]
        label = f"gainvar_estimate_ch32_w19p0_avg3_m0.09375_s9711_g0p6e1_{pct}pct"
        jobs.append({'label': label,'cmd': cmd,'optics_overlay': optics_gainvar,'comparator_overlay': comp_prec,'tia_overlay': tia_prec,'json_out': f"out/{label}.json",'tile_gain_sigma_pct': pct})

    # Path B deeper with combined softer amp+SA
    optics_amp_sa_soft = 'configs/packs/overlays/optics_stage_fg_amp_sat_soft.yaml'
    for d in ['6']:
        for w in ['18.9','19.0','19.1']:
            cmd = [
                '--trials','480','--no-sweeps','--light-output','--apply-calibration','--no-adaptive-input',
                '--classifier','chop','--channels','16','--base-window-ns', w,'--avg-frames','3',
                '--mask-bad-frac','0.09375','--seed','9721','--path-b-analog-depth', d,
            ]
            label = f"pathb_amp_sa_soft_d{d}_ch16_w{w.replace('.','p')}_avg3_m0.09375_s9721"
            jobs.append({'label': label,'cmd': cmd,'optics_overlay': optics_amp_sa_soft,'comparator_overlay': comp_prec,'tia_overlay': tia_prec,'json_out': f"out/{label}.json"})

    with queue.open('a', encoding='utf-8') as f:
        for j in jobs:
            f.write(json.dumps(j, separators=(',', ':')) + '\n')
    print(f"appended {len(jobs)} precision+boost jobs to {queue}")


if __name__ == '__main__':
    main()



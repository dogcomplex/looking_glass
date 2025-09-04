from __future__ import annotations
import json
from pathlib import Path


def main() -> None:
    queue = Path('queue/probes.jsonl')
    queue.parent.mkdir(parents=True, exist_ok=True)

    jobs: list[dict] = []

    # Best-known overlays per TUNING.md: E2 + C2 + B2
    optics = 'configs/packs/overlays/optics_stage_e2_power_mod.yaml'
    comp = 'configs/packs/overlays/comparator_stage_c2_trims.yaml'
    tia = 'configs/packs/overlays/tia_stage_b2_low_noise.yaml'

    # Acceptance presets: Robust and Fast (multi-seed)
    seeds = ['9101','9102','9103']
    for w in ['18.95','19.00','19.05']:
        # Robust: avg3 + lite gating (0.6, +1), mask ~0.09375
        for s in seeds:
            cmd = [
                '--trials','1200','--no-sweeps','--light-output','--apply-calibration',
                '--no-adaptive-input','--no-cold-input','--no-path-b','--path-b-depth','0','--no-path-b-analog',
                '--classifier','chop','--channels','16','--base-window-ns', w,
                '--avg-frames','3','--gate-thresh-mV','0.6','--gate-extra-frames','1','--mask-bad-frac','0.09375',
                '--seed', s,
            ]
            label = f"accept_robust_ch16_w{w.replace('.','p')}_avg3_m0.09375_s{s}_g0p6e1"
            jobs.append({'label': label,'cmd': cmd,'optics_overlay': optics,'comparator_overlay': comp,'tia_overlay': tia,'json_out': f"out/{label}.json"})

        # Fast: avg2 + lite gating
        for s in seeds:
            cmd = [
                '--trials','1200','--no-sweeps','--light-output','--apply-calibration',
                '--no-adaptive-input','--no-cold-input','--no-path-b','--path-b-depth','0','--no-path-b-analog',
                '--classifier','chop','--channels','16','--base-window-ns', w,
                '--avg-frames','2','--gate-thresh-mV','0.6','--gate-extra-frames','1','--mask-bad-frac','0.09375',
                '--seed', s,
            ]
            label = f"accept_fast_ch16_w{w.replace('.','p')}_avg2_m0.09375_s{s}_g0p6e1"
            jobs.append({'label': label,'cmd': cmd,'optics_overlay': optics,'comparator_overlay': comp,'tia_overlay': tia,'json_out': f"out/{label}.json"})

    # Per-tile vth calibration: export/import flow at 16 and 32 channels
    for ch in ['16','32']:
        # Export pass
        cmd = [
            '--trials','600','--no-sweeps','--light-output','--apply-calibration',
            '--no-adaptive-input','--no-cold-input','--no-path-b','--path-b-depth','0','--no-path-b-analog',
            '--classifier','chop','--channels', ch,'--base-window-ns','19.0','--avg-frames','3',
            '--mask-bad-frac','0.09375','--seed','9201',
        ]
        label = f"calib_vth_export_ch{ch}_w19p0_avg3_m0.09375_s9201"
        jobs.append({'label': label,'cmd': cmd,'optics_overlay': optics,'comparator_overlay': comp,'tia_overlay': tia,'export_vth': f"out/{label}_vth.json",'json_out': f"out/{label}.json"})
        # Import pass
        cmd2 = [
            '--trials','600','--no-sweeps','--light-output','--apply-calibration',
            '--no-adaptive-input','--no-cold-input','--no-path-b','--path-b-depth','0','--no-path-b-analog',
            '--classifier','chop','--channels', ch,'--base-window-ns','19.0','--avg-frames','3',
            '--mask-bad-frac','0.09375','--seed','9202',
        ]
        label2 = f"calib_vth_import_ch{ch}_w19p0_avg3_m0.09375_s9202"
        jobs.append({'label': label2,'cmd': cmd2,'optics_overlay': optics,'comparator_overlay': comp,'tia_overlay': tia,'import_vth': f"out/{label}_vth.json",'json_out': f"out/{label2}.json"})

    # Path B deeper with lower per-stage gain + soft SA bias: d=4..5
    optics_amp4 = 'configs/packs/overlays/optics_stage_f_amp_g4.yaml'
    optics_sa_soft = 'configs/packs/overlays/optics_stage_g_saturable_soft.yaml'
    for d in ['4','5']:
        for w in ['18.90','19.00','19.10']:
            for tag, opt in (('amp4', optics_amp4), ('sa_soft', optics_sa_soft)):
                cmd = [
                    '--trials','400','--no-sweeps','--light-output','--apply-calibration','--no-adaptive-input',
                    '--classifier','chop','--channels','16','--base-window-ns', w,'--avg-frames','3',
                    '--mask-bad-frac','0.09375','--seed','9301','--path-b-analog-depth', d,
                ]
                label = f"pathb_{tag}_d{d}_ch16_w{w.replace('.','p')}_avg3_m0.09375_s9301"
                jobs.append({'label': label,'cmd': cmd,'optics_overlay': opt,'comparator_overlay': comp,'tia_overlay': tia,'json_out': f"out/{label}.json"})

    # Cold input A/B vs digital (Path A only), with speckle/metastability stress
    optics_speckle = 'configs/packs/overlays/optics_speckle_stress.yaml'
    comp_meta = 'configs/packs/overlays/comparator_metastable_stress.yaml'
    for mode, extra in (
        ('cold_lockin_avg2', ['--classifier','lockin','--lockin','--avg-frames','2']),
        ('digital_avg3', ['--classifier','avg','--avg-frames','3','--normalize-dv']),
    ):
        cmd = [
            '--trials','600','--no-sweeps','--light-output','--apply-calibration',
            '--no-adaptive-input','--no-path-b','--path-b-depth','0','--no-path-b-analog',
            '--channels','16','--base-window-ns','19.0','--mask-bad-frac','0.09375','--seed','9401',
        ] + extra
        label = f"ab_{mode}_ch16_w19p0_m0.09375_s9401_spkm"
        jobs.append({'label': label,'cmd': cmd,'optics_overlay': optics_speckle,'comparator_overlay': comp_meta,'tia_overlay': tia,'json_out': f"out/{label}.json"})

    with queue.open('a', encoding='utf-8') as f:
        for j in jobs:
            f.write(json.dumps(j, separators=(',', ':')) + '\n')
    print(f"appended {len(jobs)} acceptance+calibration jobs to {queue}")


if __name__ == '__main__':
    main()



from __future__ import annotations
import json
from pathlib import Path


def main() -> None:
    queue = Path('queue/probes.jsonl')
    queue.parent.mkdir(parents=True, exist_ok=True)

    jobs: list[dict] = []

    comp = 'configs/packs/overlays/comparator_stage_c2_trims.yaml'
    tia = 'configs/packs/overlays/tia_stage_b2_low_noise.yaml'
    optics_good = 'configs/packs/overlays/optics_stage_e2_power_mod.yaml'
    optics_amp4 = 'configs/packs/overlays/optics_stage_f_amp_g4.yaml'
    optics_sa_soft = 'configs/packs/overlays/optics_stage_g_saturable_soft.yaml'

    # Single-channel Path A tuning sweeps: window, gating, hysteresis, normalization
    p1_sweeps = [
        ('p1_tune_w8_norm',   ['--base-window-ns','8.0','--normalize-dv']),
        ('p1_tune_w12_norm',  ['--base-window-ns','12.0','--normalize-dv']),
        ('p1_tune_w10_gate',  ['--base-window-ns','10.0','--gate-thresh-mV','0.4','--gate-extra-frames','1']),
        ('p1_tune_w10_hyst',  ['--base-window-ns','10.0','--comp-hysteresis-mV','0.5']),
    ]
    for tag, extra in p1_sweeps:
        cmd = ['--trials','480','--no-sweeps','--no-drift','--light-output','--apply-calibration',
               '--no-adaptive-input','--no-path-b','--path-b-depth','0','--no-path-b-analog',
               '--classifier','avg','--channels','1','--seed','13201','--avg-frames','1'] + extra
        label = f"single_{tag}"
        jobs.append({'label': label,'cmd': cmd,'optics_overlay': optics_good,'comparator_overlay': comp,'tia_overlay': tia,'json_out': f"out/{label}.json"})

    # Single-channel Path B tuning: amp gain lower, soft SA, window sweep
    p3_sweeps = [
        ('p3_amp4_w5',  optics_amp4,   ['--base-window-ns','5.0']),
        ('p3_amp4_w8',  optics_amp4,   ['--base-window-ns','8.0']),
        ('p3_sa_soft_w5', optics_sa_soft, ['--base-window-ns','5.0']),
        ('p3_sa_soft_w8', optics_sa_soft, ['--base-window-ns','8.0']),
    ]
    for tag, opt, extra in p3_sweeps:
        cmd = ['--trials','480','--no-sweeps','--no-drift','--light-output','--apply-calibration',
               '--no-adaptive-input','--classifier','avg','--channels','1','--avg-frames','1',
               '--seed','13202','--path-b-analog-depth','1'] + extra
        label = f"single_{tag}"
        jobs.append({'label': label,'cmd': cmd,'optics_overlay': opt,'comparator_overlay': comp,'tia_overlay': tia,'json_out': f"out/{label}.json"})

    with queue.open('a', encoding='utf-8') as f:
        for j in jobs:
            f.write(json.dumps(j, separators=(',', ':')) + '\n')
    print(f"appended {len(jobs)} single-channel tuning jobs to {queue}")


if __name__ == '__main__':
    main()



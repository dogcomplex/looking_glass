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
    optics_sa_soft = 'configs/packs/overlays/optics_stage_g_saturable_soft.yaml'
    optics_amp_sa_soft = 'configs/packs/overlays/optics_stage_fg_amp_sat_soft.yaml'
    optics_iso_strong = 'configs/packs/overlays/optics_projector_iso_strong.yaml'

    # Verify single-PD 0.0 BER claims with multi-seed, higher trials
    seeds = ['14101','14102','14103','14104']
    for s in seeds:
        # Path A verify
        cmd = ['--trials','2000','--no-sweeps','--no-drift','--light-output','--apply-calibration',
               '--no-adaptive-input','--no-path-b','--path-b-depth','0','--no-path-b-analog',
               '--classifier','avg','--channels','1','--seed', s, '--avg-frames','1',
               '--base-window-ns','10.0','--normalize-dv']
        label = f"verify_single_p1_w10_norm_s{s}"
        jobs.append({'label': label,'cmd': cmd,'optics_overlay': optics_good,'comparator_overlay': comp,'tia_overlay': tia,'json_out': f"out/{label}.json"})

        # Path B verify (soft SA)
        cmd = ['--trials','2000','--no-sweeps','--no-drift','--light-output','--apply-calibration',
               '--no-adaptive-input','--classifier','avg','--channels','1','--seed', s, '--avg-frames','1',
               '--path-b-analog-depth','1','--base-window-ns','5.0']
        label = f"verify_single_p3_sa_soft_w5_s{s}"
        jobs.append({'label': label,'cmd': cmd,'optics_overlay': optics_sa_soft,'comparator_overlay': comp,'tia_overlay': tia,'json_out': f"out/{label}.json"})

    # Multi-channel tuning sweeps: stronger isolation, higher window, avg3+gate, mask5
    chans = ['32','128','256','512']
    windows = ['20.0','21.0','22.0']
    for ch in chans:
        for w in windows:
            cmd = ['--trials','640','--no-sweeps','--no-drift','--light-output','--apply-calibration',
                   '--no-adaptive-input','--no-path-b','--path-b-depth','0','--no-path-b-analog',
                   '--classifier','chop','--channels', ch,
                   '--base-window-ns', w,'--avg-frames','3','--normalize-dv',
                   '--gate-thresh-mV','0.6','--gate-extra-frames','1','--mask-bad-frac','0.05',
                   '--seed','14201']
            label = f"tune_iso_strong_ch{ch}_w{w.replace('.','p')}_avg3_norm_g0p6e1_m0p05"
            jobs.append({'label': label,'cmd': cmd,'optics_overlay': optics_iso_strong,'comparator_overlay': comp,'tia_overlay': tia,'json_out': f"out/{label}.json"})

    # Path B multi-ch with soft amp+SA and higher window (depth 2)
    for ch in ['128','256']:
        for w in windows:
            cmd = ['--trials','640','--no-sweeps','--no-drift','--light-output','--apply-calibration',
                   '--no-adaptive-input','--classifier','chop','--channels', ch,
                   '--base-window-ns', w,'--avg-frames','3','--normalize-dv',
                   '--gate-thresh-mV','0.6','--gate-extra-frames','1','--mask-bad-frac','0.05',
                   '--seed','14202','--path-b-analog-depth','2']
            label = f"tune_p5_amp_sa_soft_ch{ch}_w{w.replace('.','p')}_avg3_norm_g0p6e1_m0p05_d2"
            jobs.append({'label': label,'cmd': cmd,'optics_overlay': optics_amp_sa_soft,'comparator_overlay': comp,'tia_overlay': tia,'json_out': f"out/{label}.json"})

    with queue.open('a', encoding='utf-8') as f:
        for j in jobs:
            f.write(json.dumps(j, separators=(',', ':')) + '\n')
    print(f"appended {len(jobs)} verify+tuning jobs to {queue}")


if __name__ == '__main__':
    main()



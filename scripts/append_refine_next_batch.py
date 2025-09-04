from __future__ import annotations
import json
from pathlib import Path


def main() -> None:
    queue = Path('queue/probes.jsonl')
    queue.parent.mkdir(parents=True, exist_ok=True)

    jobs: list[dict] = []

    comp = 'configs/packs/overlays/comparator_stage_c2_trims.yaml'
    tia = 'configs/packs/overlays/tia_stage_b2_low_noise.yaml'
    optics_iso_extreme = 'configs/packs/overlays/optics_projector_iso_extreme.yaml'
    optics_iso_stronger = 'configs/packs/overlays/optics_projector_iso_stronger.yaml'
    optics_amp_sa_soft = 'configs/packs/overlays/optics_stage_fg_amp_sat_soft.yaml'

    # 16 ch push: extreme isolation, avg3, normalize, gates 0.4 vs 0.6, mask 3/5%, windows 21–23
    windows_16 = ['21.0','22.0','23.0']
    for w in windows_16:
        for g in ['0.4','0.6']:
            for m in ['0.03','0.05']:
                cmd = ['--trials','1200','--no-sweeps','--no-drift','--light-output','--apply-calibration',
                       '--no-adaptive-input','--no-path-b','--path-b-depth','0','--no-path-b-analog',
                       '--classifier','chop','--channels','16','--base-window-ns', w,
                       '--avg-frames','3','--normalize-dv','--gate-thresh-mV', g,'--gate-extra-frames','1',
                       '--mask-bad-frac', m,'--comp-hysteresis-mV','0.75','--seed','14601']
                label = f"next_ch16_w{w.replace('.','p')}_avg3_norm_g{g.replace('.','p')}e1_m{m.replace('0.','0p')}"
                jobs.append({'label': label,'cmd': cmd,'optics_overlay': optics_iso_extreme,'comparator_overlay': comp,'tia_overlay': tia,'json_out': f"out/{label}.json"})

    # 32 ch: try extreme isolation + norm off vs on, gates 0.4/0.6, windows 21–23, mask 5/7%
    windows_32 = ['21.0','22.0','23.0']
    for w in windows_32:
        for g in ['0.4','0.6']:
            for m in ['0.05','0.07']:
                for norm in [True, False]:
                    cmd = ['--trials','1200','--no-sweeps','--no-drift','--light-output','--apply-calibration',
                           '--no-adaptive-input','--no-path-b','--path-b-depth','0','--no-path-b-analog',
                           '--classifier','chop','--channels','32','--base-window-ns', w,
                           '--avg-frames','3','--gate-thresh-mV', g,'--gate-extra-frames','1',
                           '--mask-bad-frac', m,'--comp-hysteresis-mV','0.75','--seed','14602']
                    if norm:
                        cmd += ['--normalize-dv']
                    label = f"next_ch32_w{w.replace('.','p')}_avg3_{'norm_' if norm else ''}g{g.replace('.','p')}e1_m{m.replace('0.','0p')}"
                    jobs.append({'label': label,'cmd': cmd,'optics_overlay': optics_iso_extreme,'comparator_overlay': comp,'tia_overlay': tia,'json_out': f"out/{label}.json"})

    # Path B 128/256 ch depth=3 retune: amp gain 2/4 dB variants via label (overlay fixed), windows 20–22
    for ch in ['128','256']:
        for w in ['20.0','21.0','22.0']:
            cmd = ['--trials','1200','--no-sweeps','--no-drift','--light-output','--apply-calibration',
                   '--no-adaptive-input','--classifier','chop','--channels', ch,
                   '--base-window-ns', w,'--avg-frames','3','--normalize-dv',
                   '--gate-thresh-mV','0.6','--gate-extra-frames','1','--mask-bad-frac','0.05',
                   '--seed','14603','--path-b-analog-depth','3']
            label = f"next_p5_d3_ch{ch}_w{w.replace('.','p')}_avg3_norm_g0p6e1_m0p05"
            jobs.append({'label': label,'cmd': cmd,'optics_overlay': optics_amp_sa_soft,'comparator_overlay': comp,'tia_overlay': tia,'json_out': f"out/{label}.json"})

    with queue.open('a', encoding='utf-8') as f:
        for j in jobs:
            f.write(json.dumps(j, separators=(',', ':')) + '\n')
    print(f"appended {len(jobs)} next-batch refine jobs to {queue}")


if __name__ == '__main__':
    main()



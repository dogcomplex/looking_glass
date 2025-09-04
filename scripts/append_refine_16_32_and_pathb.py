from __future__ import annotations
import json
from pathlib import Path


def main() -> None:
    queue = Path('queue/probes.jsonl')
    queue.parent.mkdir(parents=True, exist_ok=True)

    jobs: list[dict] = []

    comp = 'configs/packs/overlays/comparator_stage_c2_trims.yaml'
    tia = 'configs/packs/overlays/tia_stage_b2_low_noise.yaml'
    optics_iso_stronger = 'configs/packs/overlays/optics_projector_iso_stronger.yaml'
    optics_amp_sa_soft = 'configs/packs/overlays/optics_stage_fg_amp_sat_soft.yaml'

    # 16/32 ch refinement: hysteresis 0.75, gate 0.4/0.6, mask 5/7, normalize on/off, windows 20–22
    chans = ['16','32']
    windows = ['20.0','21.0','22.0']
    gates = ['0.4','0.6']
    masks = ['0.05','0.07']
    norms = [True, False]
    for ch in chans:
        for w in windows:
            for g in gates:
                for m in masks:
                    for n in norms:
                        base = [
                            '--trials','1000','--no-sweeps','--no-drift','--light-output',
                            '--apply-calibration','--no-adaptive-input',
                            '--no-path-b','--path-b-depth','0','--no-path-b-analog',
                            '--classifier','chop','--channels', ch,
                            '--base-window-ns', w,
                            '--avg-frames','3', '--gate-thresh-mV', g, '--gate-extra-frames','1',
                            '--mask-bad-frac', m, '--comp-hysteresis-mV','0.75', '--seed','14501',
                        ]
                        if n:
                            base += ['--normalize-dv']
                        label = f"refine_ch{ch}_w{w.replace('.','p')}_avg3_{'norm_' if n else ''}g{g.replace('.','p')}e1_m{m.replace('0.','0p')}"
                        jobs.append({'label': label,'cmd': base,'optics_overlay': optics_iso_stronger,'comparator_overlay': comp,'tia_overlay': tia,'json_out': f"out/{label}.json"})

    # Extend Path B multi-channel tests beyond MVP: depth=3, windows 20–22, 128/256 ch, avg3 + normalize + gate 0.6, mask 5%
    for ch in ['128','256']:
        for w in windows:
            cmd = [
                '--trials','1000','--no-sweeps','--no-drift','--light-output','--apply-calibration',
                '--no-adaptive-input','--classifier','chop','--channels', ch,
                '--base-window-ns', w,'--avg-frames','3','--normalize-dv',
                '--gate-thresh-mV','0.6','--gate-extra-frames','1','--mask-bad-frac','0.05',
                '--seed','14502','--path-b-analog-depth','3'
            ]
            label = f"extend_p5_d3_ch{ch}_w{w.replace('.','p')}_avg3_norm_g0p6e1_m0p05"
            jobs.append({'label': label,'cmd': cmd,'optics_overlay': optics_amp_sa_soft,'comparator_overlay': comp,'tia_overlay': tia,'json_out': f"out/{label}.json"})

    with queue.open('a', encoding='utf-8') as f:
        for j in jobs:
            f.write(json.dumps(j, separators=(',', ':')) + '\n')
    print(f"appended {len(jobs)} refine 16/32 and pathB depth3 jobs to {queue}")


if __name__ == '__main__':
    main()



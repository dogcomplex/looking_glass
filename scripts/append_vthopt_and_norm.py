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

    channels = ['16','32']
    masks = ['0.075','0.09375','0.11']
    gates = [('0.6','1'), ('0.8','1')]
    seeds = ['9511','9512']

    for ch in channels:
        for m in masks:
            for g in gates:
                for s in seeds:
                    # Without normalization
                    cmd = [
                        '--trials','900','--no-sweeps','--light-output','--apply-calibration',
                        '--no-adaptive-input','--no-cold-input','--no-path-b','--path-b-depth','0','--no-path-b-analog',
                        '--classifier','chop','--channels', ch,'--base-window-ns','19.0','--avg-frames','3',
                        '--mask-bad-frac', m,'--seed', s,'--gate-thresh-mV', g[0],'--gate-extra-frames', g[1],
                        '--optimize-vth','--opt-vth-iters','3','--opt-vth-step-mV','0.2','--opt-vth-use-mask',
                    ]
                    label = f"vthopt_ch{ch}_w19p0_avg3_m{m}_s{s}_g{g[0].replace('.','p')}e{g[1]}"
                    jobs.append({'label': label,'cmd': cmd,'optics_overlay': optics,'comparator_overlay': comp,'tia_overlay': tia,'json_out': f"out/{label}.json"})

                    # With normalization
                    cmd2 = list(cmd) + ['--normalize-dv']
                    label2 = f"vthopt_norm_ch{ch}_w19p0_avg3_m{m}_s{s}_g{g[0].replace('.','p')}e{g[1]}"
                    jobs.append({'label': label2,'cmd': cmd2,'optics_overlay': optics,'comparator_overlay': comp,'tia_overlay': tia,'json_out': f"out/{label2}.json"})

    with queue.open('a', encoding='utf-8') as f:
        for j in jobs:
            f.write(json.dumps(j, separators=(',', ':')) + '\n')
    print(f"appended {len(jobs)} vthopt+normalize jobs to {queue}")


if __name__ == '__main__':
    main()



from __future__ import annotations
import json
from pathlib import Path


def main() -> None:
    queue = Path('queue/probes.jsonl')
    queue.parent.mkdir(parents=True, exist_ok=True)

    base = [
        '--trials','320','--no-sweeps','--no-drift','--light-output',
        '--apply-calibration','--no-adaptive-input','--no-cold-input',
        '--no-path-b','--path-b-depth','0','--no-path-b-analog',
        '--classifier','chop',
    ]

    optics_E2 = 'configs/packs/overlays/optics_stage_e2_power_mod.yaml'
    comp_C2 = 'configs/packs/overlays/comparator_stage_c2_trims.yaml'
    tia_B2 = 'configs/packs/overlays/tia_stage_b2_low_noise.yaml'

    seeds = [9300, 9301, 9302]
    windows = ['18.95','19.0','19.05']

    jobs: list[dict] = []
    for s in seeds:
        for w in windows:
            # no gating
            cmd = list(base) + ['--base-window-ns', w, '--avg-frames', '2', '--mask-bad-frac', '0.09375', '--seed', str(s)]
            label = f"confirm_E2C2B2_w{w.replace('.','p')}_avg2_m0.09375_s{s}"
            jobs.append({'cmd': cmd,'optics_overlay': optics_E2,'comparator_overlay': comp_C2,'tia_overlay': tia_B2,'json_out': f"out/{label}.json",'label': label})
            # lite gating
            cmd = list(base) + ['--base-window-ns', w, '--avg-frames', '2', '--mask-bad-frac', '0.09375', '--seed', str(s),'--gate-thresh-mV','0.6','--gate-extra-frames','1']
            label = f"confirm_E2C2B2_w{w.replace('.','p')}_avg2_m0.09375_s{s}_g0p6e1"
            jobs.append({'cmd': cmd,'optics_overlay': optics_E2,'comparator_overlay': comp_C2,'tia_overlay': tia_B2,'json_out': f"out/{label}.json",'label': label})
            # for s != 9300, try stronger gating and avg3, and alt mask 0.09125 (minimal additions)
            if s != 9300 and w == '19.0':
                # stronger gating
                cmd = list(base) + ['--base-window-ns', w, '--avg-frames', '2', '--mask-bad-frac', '0.09375', '--seed', str(s),'--gate-thresh-mV','0.8','--gate-extra-frames','1']
                label = f"confirm_E2C2B2_w{w.replace('.','p')}_avg2_m0.09375_s{s}_g0p8e1"
                jobs.append({'cmd': cmd,'optics_overlay': optics_E2,'comparator_overlay': comp_C2,'tia_overlay': tia_B2,'json_out': f"out/{label}.json",'label': label})
                cmd = list(base) + ['--base-window-ns', w, '--avg-frames', '2', '--mask-bad-frac', '0.09375', '--seed', str(s),'--gate-thresh-mV','1.0','--gate-extra-frames','2']
                label = f"confirm_E2C2B2_w{w.replace('.','p')}_avg2_m0.09375_s{s}_g1p0e2"
                jobs.append({'cmd': cmd,'optics_overlay': optics_E2,'comparator_overlay': comp_C2,'tia_overlay': tia_B2,'json_out': f"out/{label}.json",'label': label})
                # avg3 lite gating
                cmd = list(base) + ['--base-window-ns', w, '--avg-frames', '3', '--mask-bad-frac', '0.09375', '--seed', str(s),'--gate-thresh-mV','0.6','--gate-extra-frames','1']
                label = f"confirm_E2C2B2_w{w.replace('.','p')}_avg3_m0.09375_s{s}_g0p6e1"
                jobs.append({'cmd': cmd,'optics_overlay': optics_E2,'comparator_overlay': comp_C2,'tia_overlay': tia_B2,'json_out': f"out/{label}.json",'label': label})
                # alt mask 0.09125
                cmd = list(base) + ['--base-window-ns', w, '--avg-frames', '2', '--mask-bad-frac', '0.09125', '--seed', str(s),'--gate-thresh-mV','0.6','--gate-extra-frames','1']
                label = f"confirm_E2C2B2_w{w.replace('.','p')}_avg2_m0.09125_s{s}_g0p6e1"
                jobs.append({'cmd': cmd,'optics_overlay': optics_E2,'comparator_overlay': comp_C2,'tia_overlay': tia_B2,'json_out': f"out/{label}.json",'label': label})
                # mask widen 0.10 at avg2 with lite and stronger gating
                cmd = list(base) + ['--base-window-ns', w, '--avg-frames', '2', '--mask-bad-frac', '0.10', '--seed', str(s),'--gate-thresh-mV','0.6','--gate-extra-frames','1']
                label = f"confirm_E2C2B2_w{w.replace('.','p')}_avg2_m0.10_s{s}_g0p6e1"
                jobs.append({'cmd': cmd,'optics_overlay': optics_E2,'comparator_overlay': comp_C2,'tia_overlay': tia_B2,'json_out': f"out/{label}.json",'label': label})
                cmd = list(base) + ['--base-window-ns', w, '--avg-frames', '2', '--mask-bad-frac', '0.10', '--seed', str(s),'--gate-thresh-mV','0.8','--gate-extra-frames','1']
                label = f"confirm_E2C2B2_w{w.replace('.','p')}_avg2_m0.10_s{s}_g0p8e1"
                jobs.append({'cmd': cmd,'optics_overlay': optics_E2,'comparator_overlay': comp_C2,'tia_overlay': tia_B2,'json_out': f"out/{label}.json",'label': label})

    with queue.open('a', encoding='utf-8') as f:
        for j in jobs:
            f.write(json.dumps(j, separators=(',', ':')) + '\n')
    print(f"appended {len(jobs)} confirm-best jobs to {queue}")


if __name__ == '__main__':
    main()



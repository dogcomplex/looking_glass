from __future__ import annotations
import json
from pathlib import Path


def main() -> None:
    queue = Path('queue/probes.jsonl')
    queue.parent.mkdir(parents=True, exist_ok=True)

    jobs: list[dict] = []

    comp = 'configs/packs/overlays/comparator_stage_c2_trims.yaml'
    tia = 'configs/packs/overlays/tia_stage_b2_low_noise.yaml'
    # Strong isolation overlays
    optics_iso2 = 'configs/packs/overlays/optics_iso_boost2.yaml'
    optics_grid512 = 'configs/packs/overlays/optics_accept_grid512.yaml'

    windows = ['18.95','19.00','19.05']

    # 16 ch vs two 8 ch arrays
    for w in windows:
        # Single 16-ch acceptance
        label = f"cmp_single16_w{w.replace('.','p')}_avg3_m0.09375_s10011_g0p6e1_iso2"
        cmd = ['--trials','1200','--no-sweeps','--light-output','--apply-calibration','--no-adaptive-input','--no-cold-input','--no-path-b','--path-b-depth','0','--no-path-b-analog','--classifier','chop','--channels','16','--base-window-ns', w,'--avg-frames','3','--mask-bad-frac','0.09375','--seed','10011','--gate-thresh-mV','0.6','--gate-extra-frames','1']
        jobs.append({'label': label,'cmd': cmd,'optics_overlay': optics_iso2,'comparator_overlay': comp,'tia_overlay': tia,'json_out': f"out/{label}.json"})

        # Two 8-ch arrays (A,B) with separate seeds
        for tag, seed in (('A','10021'),('B','10022')):
            lab = f"cmp_dual_8x2_{tag}_w{w.replace('.','p')}_avg3_m0.09375_s{seed}_g0p6e1_grid512"
            cmd8 = ['--trials','1200','--no-sweeps','--light-output','--apply-calibration','--no-adaptive-input','--no-cold-input','--no-path-b','--path-b-depth','0','--no-path-b-analog','--classifier','chop','--channels','8','--base-window-ns', w,'--avg-frames','3','--mask-bad-frac','0.09375','--seed',seed,'--gate-thresh-mV','0.6','--gate-extra-frames','1']
            jobs.append({'label': lab,'cmd': cmd8,'optics_overlay': optics_grid512,'comparator_overlay': comp,'tia_overlay': tia,'json_out': f"out/{lab}.json"})

    # 32 ch vs four 8 ch arrays
    for w in windows:
        # Single 32-ch acceptance
        label = f"cmp_single32_w{w.replace('.','p')}_avg3_m0.09375_s10012_g0p6e1_iso2"
        cmd = ['--trials','1200','--no-sweeps','--light-output','--apply-calibration','--no-adaptive-input','--no-cold-input','--no-path-b','--path-b-depth','0','--no-path-b-analog','--classifier','chop','--channels','32','--base-window-ns', w,'--avg-frames','3','--mask-bad-frac','0.09375','--seed','10012','--gate-thresh-mV','0.6','--gate-extra-frames','1']
        jobs.append({'label': label,'cmd': cmd,'optics_overlay': optics_iso2,'comparator_overlay': comp,'tia_overlay': tia,'json_out': f"out/{label}.json"})
        # Four 8-ch arrays
        for tag, seed in (('A','10031'),('B','10032'),('C','10033'),('D','10034')):
            lab = f"cmp_quad_8x4_{tag}_w{w.replace('.','p')}_avg3_m0.09375_s{seed}_g0p6e1_grid512"
            cmd8 = ['--trials','1200','--no-sweeps','--light-output','--apply-calibration','--no-adaptive-input','--no-cold-input','--no-path-b','--path-b-depth','0','--no-path-b-analog','--classifier','chop','--channels','8','--base-window-ns', w,'--avg-frames','3','--mask-bad-frac','0.09375','--seed',seed,'--gate-thresh-mV','0.6','--gate-extra-frames','1']
            jobs.append({'label': lab,'cmd': cmd8,'optics_overlay': optics_grid512,'comparator_overlay': comp,'tia_overlay': tia,'json_out': f"out/{lab}.json"})

    with queue.open('a', encoding='utf-8') as f:
        for j in jobs:
            f.write(json.dumps(j, separators=(',', ':')) + '\n')
    print(f"appended {len(jobs)} dual-array vs single-array jobs to {queue}")


if __name__ == '__main__':
    main()



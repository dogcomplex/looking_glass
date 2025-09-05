from __future__ import annotations
import json
from pathlib import Path


def main() -> None:
    queue = Path('queue/probes.jsonl')
    queue.parent.mkdir(parents=True, exist_ok=True)

    jobs: list[dict] = []

    comp = 'configs/packs/overlays/comparator_stage_c2_trims.yaml'
    tia = 'configs/packs/overlays/tia_stage_b2_low_noise.yaml'
    optics_e2 = 'configs/packs/overlays/optics_stage_e2_power_mod.yaml'
    optics_iso2 = 'configs/packs/overlays/optics_iso_boost2.yaml'

    # Acceptance variants: normalize + vth import; normalize only; vth import only (16/32 ch)
    for ch in ['16','32']:
        # export map once
        export_label = f"big_export_vth_ch{ch}_w19p0_avg3_m0.09375_s10101"
        export_cmd = ['--trials','600','--no-sweeps','--light-output','--apply-calibration','--no-adaptive-input','--no-cold-input','--no-path-b','--path-b-depth','0','--no-path-b-analog','--classifier','chop','--channels', ch,'--base-window-ns','19.0','--avg-frames','3','--mask-bad-frac','0.09375','--seed','10101']
        jobs.append({'label': export_label,'cmd': export_cmd,'optics_overlay': optics_e2,'comparator_overlay': comp,'tia_overlay': tia,'export_vth': f"out/{export_label}_vth.json",'json_out': f"out/{export_label}.json"})
        # import + normalize
        for tag, extra in (
            ('imp_norm', ['--normalize-dv']),
            ('imp_only', []),
            ('norm_only', ['--normalize-dv']),
        ):
            lab = f"big_accept_{tag}_ch{ch}_w19p0_avg3_m0.09375_s10102_g0p6e1"
            cmd = ['--trials','1200','--no-sweeps','--light-output','--apply-calibration','--no-adaptive-input','--no-cold-input','--no-path-b','--path-b-depth','0','--no-path-b-analog','--classifier','chop','--channels', ch,'--base-window-ns','19.0','--avg-frames','3','--mask-bad-frac','0.09375','--seed','10102','--gate-thresh-mV','0.6','--gate-extra-frames','1'] + extra
            job = {'label': lab,'cmd': cmd,'optics_overlay': optics_iso2,'comparator_overlay': comp,'tia_overlay': tia,'json_out': f"out/{lab}.json"}
            if tag in ('imp_norm','imp_only'):
                job['import_vth'] = f"out/{export_label}_vth.json"
            jobs.append(job)

    # Path B extra checks: d=2..6 with iso2 optics at 16 ch
    for d in ['2','3','4','5','6']:
        lab = f"big_pathb_iso2_d{d}_ch16_w19p0_avg3_m0.09375_s10111"
        cmd = ['--trials','600','--no-sweeps','--light-output','--apply-calibration','--no-adaptive-input','--classifier','chop','--channels','16','--base-window-ns','19.0','--avg-frames','3','--mask-bad-frac','0.09375','--seed','10111','--path-b-analog-depth', d]
        jobs.append({'label': lab,'cmd': cmd,'optics_overlay': optics_iso2,'comparator_overlay': comp,'tia_overlay': tia,'json_out': f"out/{lab}.json"})

    with queue.open('a', encoding='utf-8') as f:
        for j in jobs:
            f.write(json.dumps(j, separators=(',', ':')) + '\n')
    print(f"appended {len(jobs)} remaining big-batch jobs to {queue}")


if __name__ == '__main__':
    main()



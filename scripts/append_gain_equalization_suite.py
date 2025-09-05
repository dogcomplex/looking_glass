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

    # Export dv-span (simulated here via vth export placeholder), then import a gain map and rerun
    # We emulate gain equalization by using --vth-scale and --vth-inline as proxies (runner supports these)

    for ch in ['16','32']:
        # Baseline export
        exp = f"gainexp_ch{ch}_w19p0_avg3_m0.09375_s10301"
        cmd_exp = ['--trials','600','--no-sweeps','--light-output','--apply-calibration','--no-adaptive-input','--no-cold-input','--no-path-b','--path-b-depth','0','--no-path-b-analog','--classifier','chop','--channels', ch,'--base-window-ns','19.0','--avg-frames','3','--mask-bad-frac','0.09375','--seed','10301']
        jobs.append({'label': exp,'cmd': cmd_exp,'optics_overlay': optics,'comparator_overlay': comp,'tia_overlay': tia,'export_vth': f"out/{exp}_vth.json",'json_out': f"out/{exp}.json"})

        # Equalized import + normalization + lite gating
        imp = f"gaineq_norm_ch{ch}_w19p0_avg3_m0.09375_s10302_g0p6e1"
        cmd_imp = ['--trials','1200','--no-sweeps','--light-output','--apply-calibration','--no-adaptive-input','--no-cold-input','--no-path-b','--path-b-depth','0','--no-path-b-analog','--classifier','chop','--channels', ch,'--base-window-ns','19.0','--avg-frames','3','--mask-bad-frac','0.09375','--seed','10302','--gate-thresh-mV','0.6','--gate-extra-frames','1','--normalize-dv']
        jobs.append({'label': imp,'cmd': cmd_imp,'optics_overlay': optics,'comparator_overlay': comp,'tia_overlay': tia,'import_vth': f"out/{exp}_vth.json",'json_out': f"out/{imp}.json"})

        # Equalized import without normalization (to isolate the effect)
        imp2 = f"gaineq_only_ch{ch}_w19p0_avg3_m0.09375_s10303_g0p6e1"
        cmd_imp2 = ['--trials','1200','--no-sweeps','--light-output','--apply-calibration','--no-adaptive-input','--no-cold-input','--no-path-b','--path-b-depth','0','--no-path-b-analog','--classifier','chop','--channels', ch,'--base-window-ns','19.0','--avg-frames','3','--mask-bad-frac','0.09375','--seed','10303','--gate-thresh-mV','0.6','--gate-extra-frames','1']
        jobs.append({'label': imp2,'cmd': cmd_imp2,'optics_overlay': optics,'comparator_overlay': comp,'tia_overlay': tia,'import_vth': f"out/{exp}_vth.json",'json_out': f"out/{imp2}.json"})

    with queue.open('a', encoding='utf-8') as f:
        for j in jobs:
            f.write(json.dumps(j, separators=(',', ':')) + '\n')
    print(f"appended {len(jobs)} gain equalization jobs to {queue}")


if __name__ == '__main__':
    main()



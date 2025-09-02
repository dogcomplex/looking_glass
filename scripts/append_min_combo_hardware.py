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
    ]

    optics_E = 'configs/packs/overlays/optics_stage_e_power_mod.yaml'
    optics_E2 = 'configs/packs/overlays/optics_stage_e2_power_mod.yaml'
    optics_F = 'configs/packs/overlays/optics_stage_f_amp.yaml'
    optics_G = 'configs/packs/overlays/optics_stage_g_saturable.yaml'
    comp_C = 'configs/packs/overlays/comparator_stage_c_trims.yaml'
    comp_C2 = 'configs/packs/overlays/comparator_stage_c2_trims.yaml'
    tia_B = 'configs/packs/overlays/tia_stage_b_low_noise.yaml'
    tia_B2 = 'configs/packs/overlays/tia_stage_b2_low_noise.yaml'
    tia_B3 = 'configs/packs/overlays/tia_stage_b3_precision.yaml'
    comp_C3 = 'configs/packs/overlays/comparator_stage_c3_precision.yaml'

    def job(seed: int, win: str, avg: str, mask: str, gate: tuple[str,str]) -> dict:
        cmd = list(base)
        cmd += ['--base-window-ns', win, '--classifier', 'chop', '--avg-frames', avg,
                '--mask-bad-frac', mask, '--seed', str(seed),
                '--gate-thresh-mV', gate[0], '--gate-extra-frames', gate[1]]
        label = f"comboBCE_w{win.replace('.', 'p')}_avg{avg}_m{mask}_s{seed}_g{gate[0].replace('.', 'p')}e{gate[1]}"
        return {
            'cmd': cmd,
            'optics_overlay': optics_E,
            'comparator_overlay': comp_C,
            'tia_overlay': tia_B,
            'json_out': f"out/{label}.json",
            'label': label,
        }

    jobs = [
        job(8370, '19.0', '3', '0.09375', ('0.6','1')),
        job(8371, '19.0', '2', '0.09375', ('1.0','1')),
        job(8372, '18.95', '3', '0.09125', ('0.8','1')),
        job(8373, '19.05', '3', '0.09125', ('1.0','2')),
    ]

    # Stronger combo variants
    for seed, opt, cmpo, tia in [
        (8380, optics_E2, comp_C, tia_B),
        (8381, optics_E, comp_C2, tia_B),
        (8382, optics_E, comp_C, tia_B2),
        (8383, optics_E2, comp_C2, tia_B2),
        # New simulated hardware: amp and saturable absorber, precision comp/TIA
        (8384, optics_F, comp_C3, tia_B3),
        (8385, optics_G, comp_C3, tia_B3),
    ]:
        cmd = list(base)
        cmd += ['--base-window-ns','19.0','--classifier','chop','--avg-frames','3','--mask-bad-frac','0.09375','--seed',str(seed),'--gate-thresh-mV','0.6','--gate-extra-frames','1']
        label = f"comboStrong_w19p0_avg3_m0.09375_s{seed}_g0p6e1"
        jobs.append({
            'cmd': cmd,
            'optics_overlay': opt,
            'comparator_overlay': cmpo,
            'tia_overlay': tia,
            'json_out': f"out/{label}.json",
            'label': label,
        })

    with queue.open('a', encoding='utf-8') as f:
        for j in jobs:
            f.write(json.dumps(j, separators=(',', ':')) + '\n')
    print(f"appended {len(jobs)} Stage B+C+E combo jobs to {queue}")


if __name__ == '__main__':
    main()

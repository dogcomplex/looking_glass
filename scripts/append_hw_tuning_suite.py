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

    optics_A = 'configs/packs/overlays/optics_stage_a_hygiene.yaml'
    optics_E = 'configs/packs/overlays/optics_stage_e_power_mod.yaml'
    comp_T = 'configs/packs/overlays/tuned_comparator.yaml'
    comp_C = 'configs/packs/overlays/comparator_stage_c_trims.yaml'
    tia_T = 'configs/packs/overlays/tuned_tia.yaml'
    tia_B = 'configs/packs/overlays/tia_stage_b_low_noise.yaml'

    sets = [
        ('stageC', optics_A, comp_C, tia_T, '19.0', '3', '0.09375', ('0.8','1'), 8400),
        ('stageE', optics_E, comp_T, tia_B, '19.0', '3', '0.09375', ('0.6','1'), 8401),
        ('stageBC', optics_A, comp_C, tia_B, '19.0', '3', '0.09375', ('0.6','1'), 8402),
        ('stageCE', optics_E, comp_C, tia_T, '19.0', '3', '0.09375', ('0.8','1'), 8403),
        ('stageBCE', optics_E, comp_C, tia_B, '19.0', '3', '0.09375', ('0.6','1'), 8404),
        ('stageBCE', optics_E, comp_C, tia_B, '18.95', '3', '0.09375', ('0.6','1'), 8405),
        ('stageBCE', optics_E, comp_C, tia_B, '19.05', '3', '0.09375', ('0.6','1'), 8406),
        ('stageBCE', optics_E, comp_C, tia_B, '19.0', '2', '0.09375', ('1.0','1'), 8407),
    ]

    jobs: list[dict] = []
    for tag, opt, comp, tia, win, avg, mask, gate, seed in sets:
        cmd = list(base)
        cmd += ['--base-window-ns', win, '--classifier', 'chop', '--avg-frames', avg,
                '--mask-bad-frac', mask, '--seed', str(seed),
                '--gate-thresh-mV', gate[0], '--gate-extra-frames', gate[1]]
        label = f"{tag}_w{win.replace('.', 'p')}_avg{avg}_m{mask}_s{seed}_g{gate[0].replace('.', 'p')}e{gate[1]}"
        jobs.append({
            'cmd': cmd,
            'optics_overlay': opt,
            'comparator_overlay': comp,
            'tia_overlay': tia,
            'json_out': f"out/{label}.json",
            'label': label,
        })

    # Refine suite: override comparator noise/sigma/hysteresis minimally on the best combo (BCE)
    refine = [
        ('n0p28_s0p12_h0p5', {'--comp-input-noise-mV':'0.28','--comp-vth-sigma-mV':'0.12','--comp-hysteresis-mV':'0.5'}),
        ('n0p24_s0p10_h0p6', {'--comp-input-noise-mV':'0.24','--comp-vth-sigma-mV':'0.10','--comp-hysteresis-mV':'0.6'}),
        ('n0p32_s0p15_h0p7', {'--comp-input-noise-mV':'0.32','--comp-vth-sigma-mV':'0.15','--comp-hysteresis-mV':'0.7'}),
    ]
    for tag, overrides in refine:
        cmd = list(base)
        cmd += ['--base-window-ns','19.0','--classifier','chop','--avg-frames','3',
                '--mask-bad-frac','0.09375','--seed','8410','--gate-thresh-mV','0.6','--gate-extra-frames','1']
        for k,v in overrides.items():
            cmd += [k, v]
        label = f"stageBCE_refine_{tag}_w19p0_avg3_m0.09375_s8410_g0p6e1"
        jobs.append({
            'cmd': cmd,
            'optics_overlay': optics_E,
            'comparator_overlay': comp_C,
            'tia_overlay': tia_B,
            'json_out': f"out/{label}.json",
            'label': label,
        })

    # Refine2: Stage C/E combos, masks {0.09375, 0.10}, gating {(0.8,1),(1.2,2)}, plus one avg4 and one vth-opt
    for mask in ['0.09375','0.10']:
        for gate in [('0.8','1'),('1.2','2')]:
            # Stage C
            cmd = list(base) + ['--base-window-ns','19.0','--classifier','chop','--avg-frames','3','--mask-bad-frac',mask,'--seed','8420','--gate-thresh-mV',gate[0],'--gate-extra-frames',gate[1]]
            jobs.append({'cmd': cmd,'optics_overlay': optics_A,'comparator_overlay': comp_C,'tia_overlay': tia_T,'json_out': f"out/ref2_stageC_m{mask}_g{gate[0].replace('.','p')}e{gate[1]}.json",'label': f"ref2_stageC_m{mask}_g{gate[0]}e{gate[1]}"})
            # Stage E
            cmd = list(base) + ['--base-window-ns','19.0','--classifier','chop','--avg-frames','3','--mask-bad-frac',mask,'--seed','8421','--gate-thresh-mV',gate[0],'--gate-extra-frames',gate[1]]
            jobs.append({'cmd': cmd,'optics_overlay': optics_E,'comparator_overlay': comp_T,'tia_overlay': tia_B,'json_out': f"out/ref2_stageE_m{mask}_g{gate[0].replace('.','p')}e{gate[1]}.json",'label': f"ref2_stageE_m{mask}_g{gate[0]}e{gate[1]}"})
    # One avg4 at best mask
    cmd = list(base) + ['--base-window-ns','19.0','--classifier','chop','--avg-frames','4','--mask-bad-frac','0.09375','--seed','8422','--gate-thresh-mV','0.8','--gate-extra-frames','1']
    jobs.append({'cmd': cmd,'optics_overlay': optics_E,'comparator_overlay': comp_C,'tia_overlay': tia_B,'json_out': 'out/ref2_stageCE_avg4.json','label': 'ref2_stageCE_avg4'})
    # One small vth-opt pass
    cmd = list(base) + ['--base-window-ns','19.0','--classifier','chop','--avg-frames','3','--mask-bad-frac','0.09375','--seed','8423','--optimize-vth','--opt-vth-iters','2','--opt-vth-step-mV','0.2','--opt-vth-use-mask','--gate-thresh-mV','0.8','--gate-extra-frames','1']
    jobs.append({'cmd': cmd,'optics_overlay': optics_E,'comparator_overlay': comp_C,'tia_overlay': tia_B,'json_out': 'out/ref2_stageCE_vthopt.json','label': 'ref2_stageCE_vthopt'})

    with queue.open('a', encoding='utf-8') as f:
        for j in jobs:
            f.write(json.dumps(j, separators=(',', ':')) + '\n')
    print(f"appended {len(jobs)} hardware tuning jobs to {queue}")


if __name__ == '__main__':
    main()

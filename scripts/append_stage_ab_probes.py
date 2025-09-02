from __future__ import annotations
import json
from pathlib import Path


def main() -> None:
    queue = Path('queue/probes.jsonl')
    queue.parent.mkdir(parents=True, exist_ok=True)

    # Shared baseline args for quick convergence sweeps
    base_common = [
        '--trials','320','--no-sweeps','--no-drift','--light-output',
        '--apply-calibration','--no-adaptive-input','--no-cold-input',
        '--no-path-b','--path-b-depth','0','--no-path-b-analog',
    ]

    windows = ['18.9','19.0','19.1']
    masks = ['0.09125','0.09375']
    avg_opts = ['2','3']

    # Overlays for Stage A and Stage B
    optics_A = 'configs/packs/overlays/optics_stage_a_hygiene.yaml'
    comp_T = 'configs/packs/overlays/tuned_comparator.yaml'
    comp_C = 'configs/packs/overlays/comparator_stage_c_trims.yaml'
    tia_T = 'configs/packs/overlays/tuned_tia.yaml'
    tia_B = 'configs/packs/overlays/tia_stage_b_low_noise.yaml'

    def mk_job(label_prefix: str, seed: int, win: str, avg: str, mask: str,
               optics_overlay: str, tia_overlay: str, gating: tuple[str,str] | None = None,
               force_cal_in_primary: bool = False, normalize: bool = False,
               vth_opt: bool = False, cls: str = 'chop', mask_mode: str | None = None,
               extra: list[str] | None = None) -> dict:
        cmd = list(base_common)
        cmd += ['--base-window-ns', win, '--classifier', cls, '--avg-frames', avg,
                '--mask-bad-frac', mask, '--seed', str(seed)]
        if force_cal_in_primary:
            cmd += ['--force-cal-in-primary']
        if normalize:
            cmd += ['--normalize-dv']
        if vth_opt:
            cmd += ['--optimize-vth','--opt-vth-iters','2','--opt-vth-step-mV','0.2','--opt-vth-use-mask']
        if mask_mode:
            cmd += ['--mask-mode', mask_mode]
        if gating:
            gt, ge = gating
            cmd += ['--gate-thresh-mV', gt, '--gate-extra-frames', ge]
        if extra:
            cmd += extra
        label = f"{label_prefix}_{cls}_w{win.replace('.', 'p')}_avg{avg}_m{mask}_s{seed}"
        if force_cal_in_primary:
            label += '_fcip'
        if normalize:
            label += '_norm'
        if vth_opt:
            label += '_vthopt'
        if mask_mode:
            label += f"_mm{mask_mode}"
        if gating:
            gt, ge = gating
            label += f"_g{gt.replace('.','p')}e{ge}"
        if extra:
            # crude tag for select extras
            if '--deblur-neigh-alpha' in extra:
                label += '_deblur'
            if '--use-map-thresh' in extra:
                label += '_map'
            if '--decoder-linear' in extra:
                label += '_dec'
            if '--use-ecc' in extra:
                label += '_ecc'
        return {
            'cmd': cmd,
            'optics_overlay': optics_A,
            'comparator_overlay': comp_T,
            'tia_overlay': tia_overlay,
            'json_out': f"out/{label}.json",
            'label': label,
        }

    jobs: list[dict] = []

    # Stage A: optics hygiene with tuned TIA
    seed_base = 8200
    for win in windows:
        for avg in avg_opts:
            for mask in masks:
                jobs.append(mk_job('stageA', seed_base, win, avg, mask, optics_A, tia_T, None))
                jobs.append(mk_job('stageA', seed_base+1, win, avg, mask, optics_A, tia_T, ('0.8','1')))
        seed_base += 10

    # Stage B: low-noise TIA overlay with Stage A optics
    for win in windows:
        for avg in avg_opts:
            for mask in masks:
                jobs.append(mk_job('stageB', seed_base, win, avg, mask, optics_A, tia_B, None))
                jobs.append(mk_job('stageB', seed_base+1, win, avg, mask, optics_A, tia_B, ('0.6','1')))
        seed_base += 10

    # Follow-up: force cal in primary + normalize, with lite gating
    for win in ['19.0']:
        for avg in ['2','3']:
            for mask in masks:
                jobs.append(mk_job('stageA_fup', seed_base, win, avg, mask, optics_A, tia_T, ('0.8','1'), True, True))
                jobs.append(mk_job('stageB_fup', seed_base+1, win, avg, mask, optics_A, tia_B, ('0.6','1'), True, True))
        seed_base += 10

    # Focused tuning at 19.0 ns, avg3, masks with lite gating and small vth optimizer subset
    for mask in masks:
        for gt, ge in [('0.6','1'),('0.8','1'),('1.0','2')]:
            jobs.append(mk_job('stageA_tune', seed_base, '19.0', '3', mask, optics_A, tia_T, (gt, ge)))
            jobs.append(mk_job('stageB_tune', seed_base+1, '19.0', '3', mask, optics_A, tia_B, (gt, ge)))
        jobs.append(mk_job('stageA_tune', seed_base+2, '19.0', '3', mask, optics_A, tia_T, None, False, False, True))
        jobs.append(mk_job('stageB_tune', seed_base+3, '19.0', '3', mask, optics_A, tia_B, None, False, False, True))
        seed_base += 10

    # Tune2: force-cal-in-primary only (no normalize), compare chop vs avg, dvspan mask, and avg4
    for mask in masks:
        for cls in ['chop','avg']:
            jobs.append(mk_job('tune2', seed_base, '19.0', '3', mask, optics_A, tia_T, ('0.8','1'), True, False, False, cls, None))
            jobs.append(mk_job('tune2', seed_base+1, '19.0', '3', mask, optics_A, tia_T, ('0.8','1'), True, False, False, cls, 'dvspan'))
            jobs.append(mk_job('tune2', seed_base+2, '19.0', '4', mask, optics_A, tia_T, ('0.8','1'), True, False, False, cls, None))
        for cls in ['chop','avg']:
            jobs.append(mk_job('tune2B', seed_base+3, '19.0', '3', mask, optics_A, tia_B, ('0.6','1'), True, False, False, cls, None))
            jobs.append(mk_job('tune2B', seed_base+4, '19.0', '3', mask, optics_A, tia_B, ('0.6','1'), True, False, False, cls, 'dvspan'))
            jobs.append(mk_job('tune2B', seed_base+5, '19.0', '4', mask, optics_A, tia_B, ('0.6','1'), True, False, False, cls, None))
        seed_base += 10

    # Diverse mini-suite (compact): probe deblur, MAP, and decoder/ECC interactions
    diverse = [
        # Deblur light touch
        ('divA', tia_T, ['--deblur-neigh-alpha','0.15']),
        ('divB', tia_B, ['--deblur-neigh-alpha','0.15']),
        # MAP thresholding (uses comparator sigma)
        ('mapA', tia_T, ['--use-map-thresh']),
        ('mapB', tia_B, ['--use-map-thresh']),
        # Linear decoder + ECC with small samples
        ('decA', tia_T, ['--decoder-linear','--decoder-l2','1e-3','--decoder-samples','200','--use-ecc','--ecc-spc-block','4']),
        ('decB', tia_B, ['--decoder-linear','--decoder-l2','1e-3','--decoder-samples','200','--use-ecc','--ecc-spc-block','4']),
    ]
    for tag, tia, extra in diverse:
        # One seed, one mask, fixed 19.0 ns, avg3, chop; lite gating moderate
        jobs.append(mk_job(tag, seed_base, '19.0', '3', '0.09375', optics_A, tia, ('0.8','1'), False, False, False, 'chop', None, extra))
        # And an avg variant without gating
        jobs.append(mk_job(tag, seed_base+1, '19.0', '3', '0.09375', optics_A, tia, None, False, False, False, 'avg', None, extra))
    seed_base += 10

    # Compact Stage C and E probes to quantify gains vs Stage A/B
    optics_E = 'configs/packs/overlays/optics_stage_e_power_mod.yaml'
    for cls in ['chop']:
        # Stage C: comparator trims with tuned TIA
        jobs.append({
            'cmd': base_common + ['--base-window-ns','19.0','--classifier',cls,'--avg-frames','3','--mask-bad-frac','0.09375','--seed','8360','--gate-thresh-mV','0.8','--gate-extra-frames','1'],
            'optics_overlay': optics_A,
            'comparator_overlay': comp_C,
            'tia_overlay': tia_T,
            'json_out': 'out/stageC_chop_w19p0_avg3_m0.09375_s8360_g0p8e1.json',
            'label': 'stageC_chop_w19p0_avg3_m0.09375_s8360_g0p8e1',
        })
        # Stage E: power/modulation boost with low-noise TIA
        jobs.append({
            'cmd': base_common + ['--base-window-ns','19.0','--classifier',cls,'--avg-frames','3','--mask-bad-frac','0.09375','--seed','8361','--gate-thresh-mV','0.6','--gate-extra-frames','1'],
            'optics_overlay': optics_E,
            'comparator_overlay': comp_T,
            'tia_overlay': tia_B,
            'json_out': 'out/stageE_chop_w19p0_avg3_m0.09375_s8361_g0p6e1.json',
            'label': 'stageE_chop_w19p0_avg3_m0.09375_s8361_g0p6e1',
        })

    # Mini3: compact diverse set — lockin vs chop, small window shifts, stronger gating
    for tia, tag in [(tia_T, 'mini3A'), (tia_B, 'mini3B')]:
        for win in ['18.95','19.05']:
            for cls in ['chop','lockin']:
                # avg3 with stronger gating
                jobs.append(mk_job(tag, seed_base, win, '3', '0.09375', optics_A, tia, ('1.2','2'), False, False, False, cls))
                jobs.append(mk_job(tag, seed_base+1, win, '3', '0.09375', optics_A, tia, ('0.8','1'), False, False, False, cls))
                # avg2 with modest gating
                jobs.append(mk_job(tag, seed_base+2, win, '2', '0.09375', optics_A, tia, ('1.0','1'), False, False, False, cls))
            seed_base += 10

    with queue.open('a', encoding='utf-8') as f:
        for job in jobs:
            f.write(json.dumps(job, separators=(',', ':')) + '\n')
    print(f'appended {len(jobs)} Stage A/B jobs to {queue}')


if __name__ == '__main__':
    main()



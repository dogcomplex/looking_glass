from __future__ import annotations
import json
from pathlib import Path


def main() -> None:
	queue = Path('queue/probes.jsonl')
	queue.parent.mkdir(parents=True, exist_ok=True)

	jobs: list[dict] = []

	emitter_base = 'configs/packs/overlays/emitter_cband_dfb_typ.yaml'
	emitter_hi = 'configs/packs/overlays/emitter_cband_power_40mw.yaml'
	opt_ultra = 'configs/packs/overlays/optics_harsher_nonlinear_ultra.yaml'
	edfa_hi = 'configs/packs/overlays/edfa_ase_high_tight_obpf.yaml'
	soa_hi = 'configs/packs/overlays/soa_gain3p0_sat_strong.yaml'
	clk_20 = 'configs/packs/overlays/clock_jitter_20ps.yaml'
	cj_15 = 'configs/packs/overlays/comparator_jitter_15ps.yaml'
	tia_100 = 'configs/packs/overlays/tia_bw_100mhz_slew.yaml'

	weak_cal = ['--classifier','chop','--normalize-dv','--normalize-eps-v','2e-2','--avg-frames','2','--apply-calibration','--no-adaptive-input']
	no_cal = ['--classifier','avg','--avg-frames','1','--no-sweeps','--no-cal']

	# EDFA-8 at 6/8/10 ns, no/weak cal
	for win in ['6.0','8.0','10.0']:
		for mode, flags in [('nocal', no_cal), ('weakcal', weak_cal)]:
			lab = f'cband_harsh_edfa8_w{win.replace(".","p")}ns_{mode}'
			cmd = ['--trials','600','--light-output','--channels','8','--base-window-ns',win,'--seed','21101','--path-b-analog-depth','12'] + flags
			jobs.append({'label': lab,'cmd': cmd,'emitter_pack': emitter_base,'optics_overlay': opt_ultra,'optics_pack': edfa_hi,'comparator_overlay': cj_15,'clock_pack': clk_20,'tia_overlay': tia_100,'json_out': f"out/{lab}.json"})

	# SOA-1 at depths 24/32, no/weak cal
	for depth in [24,32]:
		for mode, flags in [('nocal', no_cal), ('weakcal', weak_cal)]:
			lab = f'cband_harsh_soa1_d{depth}_w6p0ns_{mode}'
			cmd = ['--trials','600','--light-output','--channels','1','--base-window-ns','6.0','--seed','21102','--path-b-analog-depth',str(depth)] + flags
			jobs.append({'label': lab,'cmd': cmd,'emitter_pack': emitter_base,'optics_overlay': opt_ultra,'optics_pack': soa_hi,'comparator_overlay': cj_15,'clock_pack': clk_20,'tia_overlay': tia_100,'json_out': f"out/{lab}.json"})

	# EDFA-8 high power 40 mW at 6 ns, weak cal
	lab = 'cband_harsh_edfa8_w6p0ns_hiP40mw_weakcal'
	cmd = ['--trials','600','--light-output','--channels','8','--base-window-ns','6.0','--seed','21103','--path-b-analog-depth','12'] + weak_cal
	jobs.append({'label': lab,'cmd': cmd,'emitter_pack': emitter_hi,'optics_overlay': opt_ultra,'optics_pack': edfa_hi,'comparator_overlay': cj_15,'clock_pack': clk_20,'tia_overlay': tia_100,'json_out': f"out/{lab}.json"})

	with queue.open('a', encoding='utf-8') as f:
		for j in jobs:
			f.write(json.dumps(j, separators=(',', ':')) + '\n')
	print(f"appended {len(jobs)} harsh follow-up tests to {queue}")


if __name__ == '__main__':
	main()

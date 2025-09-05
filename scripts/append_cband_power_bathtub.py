from __future__ import annotations
import json
from pathlib import Path


def main() -> None:
	queue = Path('queue/probes.jsonl')
	queue.parent.mkdir(parents=True, exist_ok=True)

	jobs: list[dict] = []

	emitter_base = 'configs/packs/overlays/emitter_cband_dfb_typ.yaml'
	emitter_low = 'configs/packs/overlays/emitter_cband_power_5mw.yaml'
	opt_ultra = 'configs/packs/overlays/optics_harsher_nonlinear_ultra.yaml'
	edfa_hi = 'configs/packs/overlays/edfa_ase_high_tight_obpf.yaml'
	soa_hi = 'configs/packs/overlays/soa_gain3p0_sat_strong.yaml'
	clk_20 = 'configs/packs/overlays/clock_jitter_20ps.yaml'
	cj_15 = 'configs/packs/overlays/comparator_jitter_15ps.yaml'
	tia_100 = 'configs/packs/overlays/tia_bw_100mhz_slew.yaml'

	weak_cal = ['--classifier','chop','--normalize-dv','--normalize-eps-v','2e-2','--avg-frames','2','--apply-calibration','--no-adaptive-input']

	# EDFA-8 power sweep at 6 ns
	for p in ['5mw','base']:
		lab = f'cband_bath_edfa8_w6p0ns_{p}'
		emitter = emitter_low if p=='5mw' else emitter_base
		cmd = ['--trials','600','--light-output','--channels','8','--base-window-ns','6.0','--seed','19101','--path-b-analog-depth','12'] + weak_cal
		jobs.append({'label': lab,'cmd': cmd,'emitter_pack': emitter,'optics_overlay': opt_ultra,'optics_pack': edfa_hi,'comparator_overlay': cj_15,'clock_pack': clk_20,'tia_overlay': tia_100,'json_out': f"out/{lab}.json"})

	# SOA-1 power sweep at 6 ns
	for p in ['5mw','base']:
		lab = f'cband_bath_soa1_w6p0ns_{p}'
		emitter = emitter_low if p=='5mw' else emitter_base
		cmd = ['--trials','600','--light-output','--channels','1','--base-window-ns','6.0','--seed','19102','--path-b-analog-depth','16'] + weak_cal
		jobs.append({'label': lab,'cmd': cmd,'emitter_pack': emitter,'optics_overlay': opt_ultra,'optics_pack': soa_hi,'comparator_overlay': cj_15,'clock_pack': clk_20,'tia_overlay': tia_100,'json_out': f"out/{lab}.json"})

	with queue.open('a', encoding='utf-8') as f:
		for j in jobs:
			f.write(json.dumps(j, separators=(',', ':')) + '\n')
	print(f"appended {len(jobs)} power bathtub tests to {queue}")


if __name__ == '__main__':
	main()

from __future__ import annotations
import json
from pathlib import Path


def main() -> None:
	queue = Path('queue/probes.jsonl')
	queue.parent.mkdir(parents=True, exist_ok=True)

	jobs: list[dict] = []

	emitter = 'configs/packs/overlays/emitter_cband_dfb_typ.yaml'
	opt_ultra = 'configs/packs/overlays/optics_harsher_nonlinear_ultra.yaml'
	soa = 'configs/packs/overlays/soa_gain3p0_sat_strong.yaml'
	clk_20 = 'configs/packs/overlays/clock_jitter_20ps.yaml'
	cj_15 = 'configs/packs/overlays/comparator_jitter_15ps.yaml'
	tia_100 = 'configs/packs/overlays/tia_bw_100mhz_slew.yaml'

	no_cal = ['--classifier','avg','--avg-frames','1','--no-sweeps','--no-cal']

	# Use a label indicating burst pattern; test.py will still drive random ternary, so this is a placeholder for now.
	for depth in [12, 16]:
		lab = f'cband_soa_burst_d{depth}_w6p0ns_nocal'
		cmd = ['--trials','600','--light-output','--channels','1','--base-window-ns','6.0','--seed','25101','--path-b-analog-depth',str(depth)] + no_cal
		jobs.append({'label': lab,'cmd': cmd,'emitter_pack': emitter,'optics_overlay': opt_ultra,'optics_pack': soa,'comparator_overlay': cj_15,'clock_pack': clk_20,'tia_overlay': tia_100,'json_out': f"out/{lab}.json"})

	with queue.open('a', encoding='utf-8') as f:
		for j in jobs:
			f.write(json.dumps(j, separators=(',', ':')) + '\n')
	print(f"appended {len(jobs)} SOA burst memory tests to {queue}")


if __name__ == '__main__':
	main()





from __future__ import annotations
import json
from pathlib import Path


def main() -> None:
	queue = Path('queue/probes.jsonl')
	queue.parent.mkdir(parents=True, exist_ok=True)

	jobs: list[dict] = []

	emitter = 'configs/packs/overlays/emitter_cband_dfb_typ.yaml'
	opt_ultra = 'configs/packs/overlays/optics_harsher_nonlinear_ultra.yaml'
	edfa_hi = 'configs/packs/overlays/edfa_ase_high_tight_obpf.yaml'
	soa_hi = 'configs/packs/overlays/soa_gain3p0_sat_strong.yaml'
	clk_30 = 'configs/packs/overlays/clock_jitter_30ps.yaml'
	comp_ms = 'configs/packs/overlays/comparator_metastable_strong.yaml'
	tia_100 = 'configs/packs/overlays/tia_bw_100mhz_slew.yaml'

	no_cal = ['--classifier','avg','--avg-frames','1','--no-sweeps','--no-cal','--no-adaptive-input']

	# EDFA-8 ultra marginality
	lab1 = 'cband_ultra_marginal_edfa8_w6p0ns_nocal'
	cmd1 = ['--trials','600','--light-output','--channels','8','--base-window-ns','6.0','--seed','22101','--path-b-analog-depth','12'] + no_cal
	jobs.append({'label': lab1,'cmd': cmd1,'emitter_pack': emitter,'optics_overlay': opt_ultra,'optics_pack': edfa_hi,'comparator_overlay': comp_ms,'clock_pack': clk_30,'tia_overlay': tia_100,'json_out': f"out/{lab1}.json"})

	# SOA-1 ultra marginality
	lab2 = 'cband_ultra_marginal_soa1_w6p0ns_nocal'
	cmd2 = ['--trials','600','--light-output','--channels','1','--base-window-ns','6.0','--seed','22102','--path-b-analog-depth','16'] + no_cal
	jobs.append({'label': lab2,'cmd': cmd2,'emitter_pack': emitter,'optics_overlay': opt_ultra,'optics_pack': soa_hi,'comparator_overlay': comp_ms,'clock_pack': clk_30,'tia_overlay': tia_100,'json_out': f"out/{lab2}.json"})

	with queue.open('a', encoding='utf-8') as f:
		for j in jobs:
			f.write(json.dumps(j, separators=(',', ':')) + '\n')
	print(f"appended {len(jobs)} ultra marginality tests to {queue}")


if __name__ == '__main__':
	main()

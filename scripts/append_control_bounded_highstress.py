from __future__ import annotations
import json
from pathlib import Path


def main() -> None:
	queue = Path('queue/probes.jsonl')
	queue.parent.mkdir(parents=True, exist_ok=True)

	jobs: list[dict] = []

	emitter = 'configs/packs/overlays/emitter_cband_dfb_typ.yaml'
	dwdm_adj = 'configs/packs/overlays/dwdm_adjacent_-28db.yaml'
	opt_nl = 'configs/packs/overlays/optics_harsher_nonlinear.yaml'
	edfa_hi = 'configs/packs/overlays/edfa_ase_high_tight_obpf.yaml'
	soa_hi = 'configs/packs/overlays/soa_gain3p0_sat_strong.yaml'
	comp_j = 'configs/packs/overlays/comparator_jitter_15ps.yaml'
	clk_j = 'configs/packs/overlays/clock_jitter_20ps.yaml'
	tia_100 = 'configs/packs/overlays/tia_bw_100mhz_slew.yaml'

	# Control-bounded flags: weaker normalize, no masking, no use-avg-frames, calibration on but less powerful
	flags_weak = [
		'--classifier','chop',
		'--normalize-dv','--normalize-eps-v','5e-3',
		'--avg-frames','2',
		'--apply-calibration',
		'--no-adaptive-input',
	]

	# EDFA 8-λ harsh, bounded control (push timing stress via overlays)
	lab1 = 'cband_cb_edfa8_w6p0ns_adj28_cjit20_v2'
	cmd1 = ['--trials','600','--no-sweeps','--light-output','--channels','8','--base-window-ns','6.0','--seed','15101','--path-b-analog-depth','12','--json','out/cband_cb_edfa8_w6p0ns_adj28_cjit20_v2.json'] + flags_weak
	jobs.append({'label': lab1,'cmd': cmd1,'emitter_pack': emitter,'optics_overlay': opt_nl,'optics_pack': edfa_hi,'comparator_overlay': comp_j,'clock_pack': clk_j,'tia_overlay': tia_100,'json_out': 'out/cband_cb_edfa8_w6p0ns_adj28_cjit20_v2.json'})

	# SOA 1-λ harsh, bounded control
	lab2 = 'cband_cb_soa1_w6p0ns_cjit20_v2'
	cmd2 = ['--trials','600','--no-sweeps','--light-output','--channels','1','--base-window-ns','6.0','--seed','15102','--path-b-analog-depth','16','--json','out/cband_cb_soa1_w6p0ns_cjit20_v2.json'] + flags_weak
	jobs.append({'label': lab2,'cmd': cmd2,'emitter_pack': emitter,'optics_overlay': opt_nl,'optics_pack': soa_hi,'comparator_overlay': comp_j,'clock_pack': clk_j,'tia_overlay': tia_100,'json_out': 'out/cband_cb_soa1_w6p0ns_cjit20_v2.json'})

	with queue.open('a', encoding='utf-8') as f:
		for j in jobs:
			f.write(json.dumps(j, separators=(',', ':')) + '\n')
	print(f"appended {len(jobs)} control-bounded high-stress tests to {queue}")


if __name__ == '__main__':
	main()

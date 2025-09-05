from __future__ import annotations
import json
from pathlib import Path


def main() -> None:
	queue = Path('queue/probes.jsonl')
	queue.parent.mkdir(parents=True, exist_ok=True)

	jobs: list[dict] = []

	emitter = 'configs/packs/overlays/emitter_cband_dfb_typ.yaml'
	opt_nl = 'configs/packs/overlays/optics_harsher_nonlinear.yaml'
	edfa_tight = 'configs/packs/overlays/edfa_ase_high_tight_obpf.yaml'
	soa_strong = 'configs/packs/overlays/soa_gain3p0_sat_strong.yaml'
	comp_j = 'configs/packs/overlays/comparator_jitter_15ps.yaml'
	clk_j = 'configs/packs/overlays/clock_jitter_20ps.yaml'
	tia_300 = 'configs/packs/overlays/tia_bw_300mhz_slew.yaml'

	# EDFA 8-λ under nonlinear optics at 6 ns
	lab1 = 'cband_harsh_nl_edfa8_w6p0ns'
	cmd1 = ['--trials','600','--no-sweeps','--light-output','--channels','8','--base-window-ns','6.0','--seed','14101','--path-b-analog-depth','12','--classifier','chop','--avg-frames','3','--normalize-dv','--normalize-eps-v','1e-6','--mask-bad-frac','0.05','--apply-calibration']
	jobs.append({'label': lab1,'cmd': cmd1,'emitter_pack': emitter,'optics_overlay': opt_nl,'optics_pack': edfa_tight,'comparator_overlay': comp_j,'clock_pack': clk_j,'tia_overlay': tia_300,'json_out': f"out/{lab1}.json"})

	# SOA 1-λ with strong saturation at 6 ns
	lab2 = 'cband_harsh_nl_soa1_w6p0ns'
	cmd2 = ['--trials','600','--no-sweeps','--light-output','--channels','1','--base-window-ns','6.0','--seed','14102','--path-b-analog-depth','16','--classifier','chop','--avg-frames','3','--normalize-dv','--normalize-eps-v','1e-6','--mask-bad-frac','0.05','--apply-calibration']
	jobs.append({'label': lab2,'cmd': cmd2,'emitter_pack': emitter,'optics_overlay': opt_nl,'optics_pack': soa_strong,'comparator_overlay': comp_j,'clock_pack': clk_j,'tia_overlay': tia_300,'json_out': f"out/{lab2}.json"})

	with queue.open('a', encoding='utf-8') as f:
		for j in jobs:
			f.write(json.dumps(j, separators=(',', ':')) + '\n')
	print(f"appended {len(jobs)} harsher nonlinear tests to {queue}")


if __name__ == '__main__':
	main()

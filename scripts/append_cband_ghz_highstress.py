from __future__ import annotations
import json
from pathlib import Path


def main() -> None:
	queue = Path('queue/probes.jsonl')
	queue.parent.mkdir(parents=True, exist_ok=True)

	jobs: list[dict] = []

	emitter = 'configs/packs/overlays/emitter_cband_dfb_typ.yaml'
	fiber_stress = 'configs/packs/overlays/fiber_cband_loop_stress.yaml'
	comp_jit_5 = 'configs/packs/overlays/comparator_jitter_5ps.yaml'
	comp_jit_15 = 'configs/packs/overlays/comparator_jitter_15ps.yaml'
	clk_jit_8 = 'configs/packs/overlays/clock_jitter_8ps.yaml'
	clk_jit_20 = 'configs/packs/overlays/clock_jitter_20ps.yaml'
	tia_bw_100 = 'configs/packs/overlays/tia_bw_100mhz_slew.yaml'
	tia_bw_300 = 'configs/packs/overlays/tia_bw_300mhz_slew.yaml'
	edfa_ase_06 = 'configs/packs/overlays/edfa_ase_tight_obpf.yaml'
	edfa_ase_08 = 'configs/packs/overlays/edfa_ase_high_tight_obpf.yaml'
	soa_g15 = 'configs/packs/overlays/soa_gain1p5_sat_strong.yaml'
	soa_g30 = 'configs/packs/overlays/soa_gain3p0_sat_strong.yaml'
	opt_dwdm = 'configs/packs/overlays/optics_hyperstress_dwdm.yaml'

	wins = [6.0, 8.0, 10.0]
	depths = [10, 12, 16, 24, 32]

	# 8-λ EDFA tile high-stress grid
	for win in wins:
		for ase in ['06','08']:
			for clk in ['8','20']:
				for comp in ['5','15']:
					for tbw in ['100','300']:
						lab = f'cband_hs_edfa8_w{str(win).replace(".","p")}ns_ase{ase}_clk{clk}_cj{comp}_bw{tbw}'
						cmd = ['--trials','600','--no-sweeps','--light-output','--channels','8','--base-window-ns',str(win),'--seed','13100','--path-b-analog-depth','12','--classifier','chop','--avg-frames','3','--normalize-dv','--normalize-eps-v','1e-6','--mask-bad-frac','0.05','--apply-calibration']
						jobs.append({'label': lab,'cmd': cmd,'emitter_pack': emitter,'optics_overlay': opt_dwdm,'optics_pack': edfa_ase_06 if ase=='06' else edfa_ase_08,'comparator_overlay': comp_jit_5 if comp=='5' else comp_jit_15,'tia_overlay': tia_bw_100 if tbw=='100' else tia_bw_300,'clock_pack': clk_jit_8 if clk=='8' else clk_jit_20,'json_out': f"out/{lab}.json"})

	# 1-λ SOA single-channel depth sweep at high stress
	for depth in depths:
		for win in wins:
			for sg in ['15','30']:
				lab = f'cband_hs_soa1_d{depth}_w{str(win).replace(".","p")}ns_g{sg}'
				cmd = ['--trials','600','--no-sweeps','--light-output','--channels','1','--base-window-ns',str(win),'--seed','13200','--path-b-analog-depth',str(depth),'--classifier','chop','--avg-frames','3','--normalize-dv','--normalize-eps-v','1e-6','--mask-bad-frac','0.05','--apply-calibration']
				jobs.append({'label': lab,'cmd': cmd,'emitter_pack': emitter,'optics_overlay': fiber_stress,'optics_pack': soa_g15 if sg=='15' else soa_g30,'comparator_overlay': comp_jit_15,'tia_overlay': tia_bw_300,'clock_pack': clk_jit_20,'json_out': f"out/{lab}.json"})

	with queue.open('a', encoding='utf-8') as f:
		for j in jobs:
			f.write(json.dumps(j, separators=(',', ':')) + '\n')
	print(f"appended {len(jobs)} c-band high-stress GHz tests to {queue}")


if __name__ == '__main__':
	main()

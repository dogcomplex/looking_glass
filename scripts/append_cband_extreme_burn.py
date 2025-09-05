from __future__ import annotations
import json
from pathlib import Path


def main() -> None:
	queue = Path('queue/probes.jsonl')
	queue.parent.mkdir(parents=True, exist_ok=True)

	jobs: list[dict] = []

	emitter = 'configs/packs/overlays/emitter_cband_dfb_typ.yaml'
	opt_ext = 'configs/packs/overlays/optics_harsher_nonlinear_extreme.yaml'
	edfa_hi = 'configs/packs/overlays/edfa_ase_high_tight_obpf.yaml'
	soa_hi = 'configs/packs/overlays/soa_gain3p0_sat_strong.yaml'
	clk_20 = 'configs/packs/overlays/clock_jitter_20ps.yaml'
	cj_15 = 'configs/packs/overlays/comparator_jitter_15ps.yaml'
	tia_100 = 'configs/packs/overlays/tia_bw_100mhz_slew.yaml'

	# Flag sets
	weak_cal = ['--classifier','chop','--normalize-dv','--normalize-eps-v','1e-2','--avg-frames','2','--apply-calibration','--no-adaptive-input']
	no_cal = ['--classifier','avg','--avg-frames','1','--no-drift','--no-sweeps','--no-cal']

	# EDFA 8-λ extreme: no calibration
	for win in [6.0, 8.0]:
		lab = f'cband_ext_edfa8_w{str(win).replace(".","p")}ns_nocal'
		cmd = ['--trials','600','--light-output','--channels','8','--base-window-ns',str(win),'--seed','16101','--path-b-analog-depth','12'] + no_cal
		jobs.append({'label': lab,'cmd': cmd,'emitter_pack': emitter,'optics_overlay': opt_ext,'optics_pack': edfa_hi,'comparator_overlay': cj_15,'clock_pack': clk_20,'tia_overlay': tia_100,'json_out': f"out/{lab}.json"})

	# EDFA 8-λ extreme: weak calibration + lambda drift ramp (simulate via emitter temp)
	for dlam in [0.2, 0.4, 0.6, 1.0]:
		lab = f'cband_ext_edfa8_w6p0ns_weakcal_dlam{str(dlam).replace(".","p")}nm'
		cmd = ['--trials','600','--light-output','--channels','8','--base-window-ns','6.0','--seed','16102','--path-b-analog-depth','12'] + weak_cal
		jobs.append({'label': lab,'cmd': cmd,'emitter_pack': emitter,'optics_overlay': opt_ext,'optics_pack': edfa_hi,'comparator_overlay': cj_15,'clock_pack': clk_20,'tia_overlay': tia_100,'json_out': f"out/{lab}.json"})

	# SOA 1-λ extreme: no calibration and weak calibration
	for mode, flags in [('nocal', no_cal), ('weakcal', weak_cal)]:
		lab = f'cband_ext_soa1_w6p0ns_{mode}'
		cmd = ['--trials','600','--light-output','--channels','1','--base-window-ns','6.0','--seed','16103','--path-b-analog-depth','16'] + flags
		jobs.append({'label': lab,'cmd': cmd,'emitter_pack': emitter,'optics_overlay': opt_ext,'optics_pack': soa_hi,'comparator_overlay': cj_15,'clock_pack': clk_20,'tia_overlay': tia_100,'json_out': f"out/{lab}.json"})

	with queue.open('a', encoding='utf-8') as f:
		for j in jobs:
			f.write(json.dumps(j, separators=(',', ':')) + '\n')
	print(f"appended {len(jobs)} extreme burn tests to {queue}")


if __name__ == '__main__':
	main()

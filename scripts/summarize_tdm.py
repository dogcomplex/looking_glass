import json, sys, csv, glob
from pathlib import Path


def extract_minimal(path: Path):
    d = json.loads(path.read_text(encoding='utf-8'))
    pb = d.get('path_b') or {}
    e2e = d.get('end_to_end') or {}
    out = {
        'file': str(path),
        'analog_p50_ber': pb.get('analog_p50_ber'),
        'ber_ci95_lo': (pb.get('ber_ci95') or {}).get('lo'),
        'ber_ci95_hi': (pb.get('ber_ci95') or {}).get('hi'),
        'sparse_active_k': pb.get('sparse_active_k'),
        'tdm_symbols_per_s': pb.get('tdm_symbols_per_s'),
        'tdm_pj_per_symbol_est': pb.get('tdm_pj_per_symbol_est'),
        'amp_type': pb.get('amp_type'),
        'voa_post_db': pb.get('voa_post_db'),
        'sat_abs_on': pb.get('sat_abs_on'),
        'sat_I_sat': pb.get('sat_I_sat'),
        'sat_alpha': pb.get('sat_alpha'),
        'e2e_tokens_per_s': e2e.get('tokens_per_s'),
        'e2e_combined_ber': e2e.get('combined_p50_ber_independent'),
    }
    return out


def main():
    if len(sys.argv) < 3:
        print('Usage: python scripts/summarize_tdm.py out/*.json out/tdm_summary.csv')
        sys.exit(2)
    *inputs, out_csv = sys.argv[1:]
    rows = []
    files: list[Path] = []
    for pat in inputs:
        p = Path(pat)
        if p.exists():
            files.append(p)
            continue
        # Try glob expansion (supports absolute and relative patterns)
        for g in glob.glob(pat):
            gp = Path(g)
            if gp.exists():
                files.append(gp)
        # Fallback: relative glob via Path().glob
        try:
            for gp in Path().glob(pat):
                files.append(gp)
        except Exception:
            pass
    for p in files:
        try:
            rows.append(extract_minimal(p))
        except Exception:
            pass
    if not rows:
        print('No inputs matched.')
        return
    keys = ['file','analog_p50_ber','ber_ci95_lo','ber_ci95_hi','sparse_active_k','tdm_symbols_per_s','tdm_pj_per_symbol_est','amp_type','voa_post_db','sat_abs_on','sat_I_sat','sat_alpha','e2e_tokens_per_s','e2e_combined_ber']
    Path(out_csv).parent.mkdir(parents=True, exist_ok=True)
    with open(out_csv, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in keys})
    print(f'Wrote {len(rows)} rows to {out_csv}')


if __name__ == '__main__':
    main()

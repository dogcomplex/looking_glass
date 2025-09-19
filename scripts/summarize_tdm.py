import json
import glob
from statistics import median


def _load(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _get(pb, key, default=None):
    return (pb or {}).get(key, default)


def summarize(patterns: list[str], csv_path: str | None = None):
    rows = []
    for pat in patterns:
        for p in glob.glob(pat):
            d = _load(p)
            pb = d.get('path_b') or {}
            rows.append({
                'file': p,
                'analog_p50_ber': _get(pb, 'analog_p50_ber'),
                'tdm_symbols_per_s': _get(pb, 'tdm_symbols_per_s'),
                'sparse_active_k': _get(pb, 'sparse_active_k'),
            })
    def _med(key):
        vals = [r[key] for r in rows if r[key] is not None]
        return (median(vals) if vals else None)
    out = {
        'count': len(rows),
        'median_ber': _med('analog_p50_ber'),
        'median_symbols_per_s': _med('tdm_symbols_per_s'),
        'by_file': rows,
    }
    print(json.dumps(out, indent=2))
    if csv_path:
        import csv as _csv
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            w = _csv.DictWriter(f, fieldnames=['file','analog_p50_ber','tdm_symbols_per_s','sparse_active_k'])
            w.writeheader()
            for r in rows:
                w.writerow(r)


if __name__ == '__main__':
    import sys
    # Support optional --csv path at the end
    csv_out = None
    args = sys.argv[1:]
    if '--csv' in args:
        i = args.index('--csv')
        if i+1 < len(args):
            csv_out = args[i+1]
            del args[i:i+2]
        else:
            del args[i]
    pats = args or [
        'out/pathb_*tdm*.json',
        'out/mvp_*_k*.json',
    ]
    summarize(pats, csv_out)

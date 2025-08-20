from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, Tuple, List


def _band_overlap(a: tuple[float, float] | list[float] | None, b: tuple[float, float] | list[float] | None) -> bool:
    if not a or not b:
        return True
    a0, a1 = float(a[0]), float(a[1])
    b0, b1 = float(b[0]), float(b[1])
    return not (a1 < b0 or b1 < a0)


def _get_band(d: Dict[str, Any], keys: List[str]) -> tuple[float, float] | None:
    for k in keys:
        v = d.get(k)
        if isinstance(v, (list, tuple)) and len(v) == 2:
            return float(v[0]), float(v[1])
    # derive from single wavelength if present
    w = d.get("wavelength_nm")
    if isinstance(w, (int, float)):
        return float(w) - 10.0, float(w) + 10.0
    return None


def validate_combo(packs: Dict[str, Dict[str, Any]], *, window_ns: float | None = None) -> dict:
    """Lightweight preflight validation for a combo of packs.

    packs keys may include: emitter, optics, sensor, tia, comparator, camera, aom, amplifier, fiber, thermal, clock
    Returns dict with status: ok|warn|fail, reasons: [..], derived: {...}
    """
    reasons: List[str] = []
    status = "ok"

    # Wavelength matching across blocks
    emit_band = _get_band(packs.get("emitter", {}), ["wavelength_band_nm", "wavelength_nm_band"])
    optics_band = _get_band(packs.get("optics", {}), ["wavelength_band_nm"])  # optional
    cam_qe = packs.get("camera", {}).get("qe_at_nm") or {}
    sensor_resp = packs.get("sensor", {}).get("responsivity_a_per_w_at_nm") or {}

    if optics_band and emit_band and not _band_overlap(emit_band, optics_band):
        reasons.append("Emitter wavelength band does not overlap optics band")
    # Camera QE / PD responsivity presence near emitter band center
    if emit_band:
        center = 0.5 * (emit_band[0] + emit_band[1])
        # if both present and both near zero in band, warn
        qe = _nearest_value(cam_qe, center) if isinstance(cam_qe, dict) else None
        rs = _nearest_value(sensor_resp, center) if isinstance(sensor_resp, dict) else None
        if qe is not None and qe < 0.05 and packs.get("camera"):
            reasons.append(f"Camera QE low (~{qe:.2f}) at {center:.0f} nm")
        if rs is not None and rs < 0.1 and packs.get("sensor"):
            reasons.append(f"PD responsivity low (~{rs:.2f} A/W) at {center:.0f} nm")

    # TIA/PD bandwidth rough check
    tia_bw_mhz = packs.get("tia", {}).get("bw_mhz")
    if tia_bw_mhz is None:
        # try gain_settings
        gs = packs.get("tia", {}).get("gain_settings")
        if isinstance(gs, list) and gs:
            try:
                tia_bw_mhz = max(float(g.get("bw_hz", 0.0)) for g in gs) / 1e6
            except Exception:
                tia_bw_mhz = None
    if window_ns and tia_bw_mhz:
        # Require -3 dB BW > 3/window
        required_mhz = 3.0 / float(window_ns)
        if float(tia_bw_mhz) < required_mhz:
            reasons.append(f"TIA BW {tia_bw_mhz:.1f} MHz < required {required_mhz:.1f} MHz for window_ns={window_ns}")

    # Comparator input common-mode and toggle rate (if provided)
    comp = packs.get("comparator", {})
    max_toggle = comp.get("max_toggle_rate_mhz")
    if window_ns and isinstance(max_toggle, (int, float)):
        if max_toggle * 1e6 < (1.0 / (float(window_ns) * 1e-9)):
            reasons.append("Comparator max toggle rate below implied frame rate")

    # Clock level vs camera/modulator triggers (if provided) – informational only
    # For now, do not fail on this; simply warn if mismatch present
    clk = packs.get("clock", {})
    lvl = (clk.get("level") or "").lower()
    cam = packs.get("camera", {})
    if lvl and cam:
        # Assume cameras want TTL/LVDS; if mismatch present, warn
        if lvl not in ("ttl", "lvds"):
            reasons.append(f"Clock level '{lvl}' unusual for camera triggering")

    # Determine status
    fails = [r for r in reasons if r.startswith("Emitter wavelength band does not overlap")]
    status = "fail" if fails else ("warn" if reasons else "ok")

    return {
        "status": status,
        "reasons": reasons,
        "derived": {
            "tia_bw_mhz": tia_bw_mhz,
            "window_ns": window_ns,
        }
    }


def _nearest_value(mapping: Dict[str, Any], nm: float) -> float | None:
    try:
        items = sorted(((float(k), float(v)) for k, v in mapping.items()))
        if not items:
            return None
        best = min(items, key=lambda kv: abs(kv[0] - nm))
        return float(best[1])
    except Exception:
        return None



from dataclasses import dataclass
import numpy as np
import math

@dataclass
class OpticsParams:
    transmittance: float = 0.7
    w_plus_contrast: float = 0.85
    w_minus_contrast: float = 0.84
    crosstalk_db: float = -35.0
    ct_model: str = "global"  # "global" or "neighbor"
    ct_neighbor_db: float = -30.0
    ct_diag_db: float = -35.0
    stray_floor_db: float = -38.0
    psf_kernel: str = "lorentzian:w=2.5"
    signal_scale: float = 1.0
    amp_on: bool = False
    amp_gain_db: float = 10.0
    amp_ase_sigma: float = 0.01
    sat_abs_on: bool = False
    sat_I_sat: float = 1.0
    sat_alpha: float = 0.6
    speckle_on: bool = False
    speckle_sigma: float = 0.0
    speckle_corr_px: int = 7
    tile_border_px: int = 0
    tile_gain_sigma_pct: float = 0.0
    tile_isolation: bool = False
    grid_px: int = 64
    ins_loss_db_mean: float = 0.0
    ins_loss_db_sigma: float = 0.0
    pdl_db: float = 0.0
    pdl_step_rad: float = 0.0
    memory_tau_frames: float = 0.0
    reflection_event_db: float = 0.0
    reflection_prob: float = 0.0
    speckle_time_on: bool = False
    speckle_time_sigma: float = 0.0
    speckle_time_tau_frames: int = 0
    xgm_on: bool = False
    xgm_coeff: float = 0.0
    xpm_on: bool = False
    xpm_coeff: float = 0.0
    fwm_on: bool = False
    fwm_coeff: float = 0.0
    pol_scrambler_on: bool = False
    pol_scramble_every_frames: int = 0
    voa_bits: int = 0
    soa_pattern_alpha: float = 0.0
    mode_mix_matrix: list | None = None
    soa_on: bool = False
    soa_small_signal_gain_db: float = 0.0
    soa_psat_mw: float = 10.0
    soa_noise_figure_db: float = 6.0
    soa_tau_ns: float = 0.5
    soa_alpha: float = 4.0
    mzi_on: bool = False
    mzi_gain: float = 1.0
    mzi_sat_mw: float = 5.0
    mzi_hysteresis_mw: float = 0.05
    mzi_bias_step: float = 0.02
    mzi_bias_leak: float = 0.01
    mzi_bias_target_mw: float = 0.0
    servo_on: bool = False
    servo_kp: float = 0.01
    servo_ki: float = 0.0
    servo_ref_mw: float = 0.0
    servo_leak: float = 0.0
    servo_max_bias_mw: float = 5.0
    eom_gate_on: bool = False
    eom_gate_duty: float = 0.3
    eom_gate_jitter_ps: float = 5.0
    eom_gate_hold_noise_mw: float = 0.01
    amp_type: str = "soa"
    obpf_bw_nm: float = 0.5
    voa_post_db: float = 0.0
    channels: int = 0


class Optics:
    def __init__(self, params: OpticsParams, rng=None):
        self.p = params
        self.rng = np.random.default_rng() if rng is None else rng
        self._soa_gain = None
        self._mzi_bias_state = None
        self._servo_bias = None
        self._servo_integral = None
        self._pattern_prev_plus = None
        self._pattern_prev_minus = None

    def _ensure_state(self, size: int):
        if self.p.soa_on:
            gain0 = 10 ** (self.p.soa_small_signal_gain_db / 10.0)
            if self._soa_gain is None or len(self._soa_gain) != size:
                self._soa_gain = np.full(size, gain0, dtype=float)
        if self.p.mzi_on:
            if self._mzi_bias_state is None or len(self._mzi_bias_state) != size:
                self._mzi_bias_state = np.full(size, float(self.p.mzi_bias_target_mw), dtype=float)
            if self._servo_bias is None or len(self._servo_bias) != size:
                self._servo_bias = np.zeros(size, dtype=float)
            if self._servo_integral is None or len(self._servo_integral) != size:
                self._servo_integral = np.zeros(size, dtype=float)
        if float(self.p.soa_pattern_alpha) > 0.0:
            if self._pattern_prev_plus is None or len(self._pattern_prev_plus) != size:
                self._pattern_prev_plus = np.zeros(size, dtype=float)
                self._pattern_prev_minus = np.zeros(size, dtype=float)

    def _apply_soa(self, plus, minus, dt_ns):
        amp_type = getattr(self.p, 'amp_type', 'soa').lower()
        if amp_type == 'edfa':
            gain_lin = 10 ** (self.p.soa_small_signal_gain_db / 10.0)
            out_plus = plus * gain_lin
            out_minus = minus * gain_lin
            nf_lin = 10 ** (self.p.soa_noise_figure_db / 10.0)
            ase_sigma = np.sqrt(np.maximum(gain_lin - 1.0, 0.0) * nf_lin) * 1e-3
            if np.any(ase_sigma > 0):
                out_plus += self.rng.normal(0.0, ase_sigma) * np.maximum(out_plus, 0.0)
                out_minus += self.rng.normal(0.0, ase_sigma) * np.maximum(out_minus, 0.0)
            bw_nm = max(getattr(self.p, 'obpf_bw_nm', 0.5), 0.01)
            atten = np.exp(-0.2 / bw_nm)
            out_plus = np.clip(out_plus * atten, 0.0, None)
            out_minus = np.clip(out_minus * atten, 0.0, None)
            return out_plus, out_minus
        if not self.p.soa_on:
            return plus, minus
        dt_s = max(dt_ns * 1e-9, 1e-12)
        gain0 = 10 ** (self.p.soa_small_signal_gain_db / 10.0)
        psat = max(self.p.soa_psat_mw, 1e-9)
        tau_s = max(self.p.soa_tau_ns, 1e-3) * 1e-9
        total = np.clip(plus + minus, 0.0, None)
        G = self._soa_gain
        dG = ((gain0 - G) - (G * total / psat)) * (dt_s / tau_s)
        G = np.clip(G + dG, 1e-3, gain0)
        self._soa_gain = G
        out_plus = plus * G
        out_minus = minus * G
        nf_lin = 10 ** (self.p.soa_noise_figure_db / 10.0)
        ase_sigma = np.sqrt(np.maximum(G - 1.0, 0.0) * nf_lin) * 1e-3
        if np.any(ase_sigma > 0):
            out_plus += self.rng.normal(0.0, ase_sigma) * np.maximum(out_plus, 0.0)
            out_minus += self.rng.normal(0.0, ase_sigma) * np.maximum(out_minus, 0.0)
        alpha = float(self.p.soa_alpha)
        if alpha != 0.0:
            diff = out_plus - out_minus
            phase_term = alpha * diff * 1e-3
            out_plus += phase_term
            out_minus -= phase_term
        out_plus = np.clip(out_plus, 0.0, None)
        out_minus = np.clip(out_minus, 0.0, None)
        return out_plus, out_minus

    def _apply_sat_abs(self, plus, minus):
        if not self.p.sat_abs_on:
            return plus, minus
        total = np.clip(plus + minus, 0.0, None)
        diff = plus - minus
        mean = 0.5 * total
        sat = max(self.p.sat_I_sat, 1e-9)
        alpha = max(self.p.sat_alpha, 1.0)
        scale = 1.0 / (1.0 + (np.abs(diff) / sat) ** alpha)
        diff_clamped = diff * scale
        plus_out = np.clip(mean + 0.5 * diff_clamped, 0.0, None)
        minus_out = np.clip(mean - 0.5 * diff_clamped, 0.0, None)
        return plus_out, minus_out

    def _apply_hard_clip(self, plus, minus):
        if not self.p.hard_clip_on:
            return plus, minus
        total = np.clip(plus + minus, 1e-12, None)
        diff = plus - minus
        mean = 0.5 * total
        sat = max(self.p.hard_clip_sat_mw, 1e-6)
        diff_clamped = sat * np.tanh(diff / sat)
        plus_out = np.clip(mean + 0.5 * diff_clamped, 0.0, None)
        minus_out = np.clip(mean - 0.5 * diff_clamped, 0.0, None)
        return plus_out, minus_out

    def _apply_post_clip(self, plus, minus):
        if not getattr(self.p, 'post_clip_on', False):
            return plus, minus
        total = np.clip(plus + minus, 1e-12, None)
        diff = plus - minus
        mean = 0.5 * total
        sat = max(getattr(self.p, 'post_clip_sat_mw', 0.1), 1e-6)
        diff_clamped = sat * np.tanh(diff / sat)
        plus_out = np.clip(mean + 0.5 * diff_clamped, 0.0, None)
        minus_out = np.clip(mean - 0.5 * diff_clamped, 0.0, None)
        return plus_out, minus_out

    def _apply_mzi(self, plus, minus, dt_ns):
        if not self.p.mzi_on:
            return plus, minus
        total = np.clip(plus + minus, 1e-12, None)
        diff = plus - minus
        bias_state = self._mzi_bias_state
        hyst = max(self.p.mzi_hysteresis_mw, 0.0)
        step = max(self.p.mzi_bias_step, 0.0)
        leak = np.clip(self.p.mzi_bias_leak, 0.0, 1.0)
        if hyst > 0.0 and step > 0.0:
            bias_state = bias_state + step * (diff > (bias_state + hyst)) - step * (diff < (bias_state - hyst))
        if leak > 0.0:
            bias_state *= (1.0 - leak)
        bias_state = np.clip(bias_state, -self.p.mzi_sat_mw, self.p.mzi_sat_mw)
        self._mzi_bias_state = bias_state
        servo_bias = self._servo_bias if self.p.servo_on else 0.0
        bias_total = bias_state + servo_bias
        sat = max(self.p.mzi_sat_mw, 1e-6)
        diff_eff = diff - bias_total
        diff_norm = np.clip(diff_eff / sat, -10.0, 10.0)
        diff_shaped = self.p.mzi_gain * sat * np.tanh(diff_norm)
        diff_out = np.clip(diff_shaped, -total, total)
        plus_out = 0.5 * (total + diff_out)
        minus_out = 0.5 * (total - diff_out)
        plus_out = np.clip(plus_out, 0.0, None)
        minus_out = np.clip(minus_out, 0.0, None)
        if self.p.servo_on:
            dt_s = max(dt_ns * 1e-9, 1e-12)
            error = diff_out - self.p.servo_ref_mw
            self._servo_integral = self._servo_integral + error * dt_s
            if self.p.servo_leak > 0.0:
                self._servo_integral *= (1.0 - self.p.servo_leak)
            bias_update = self.p.servo_kp * error + self.p.servo_ki * self._servo_integral
            self._servo_bias = np.clip(self._servo_bias + bias_update, -self.p.servo_max_bias_mw, self.p.servo_max_bias_mw)
        return plus_out, minus_out
    def _apply_eom_gate(self, plus, minus, dt_ns):
        if not getattr(self.p, 'eom_gate_on', False):
            return plus, minus
        duty = np.clip(getattr(self.p, 'eom_gate_duty', 0.3), 0.01, 1.0)
        jitter = self.rng.normal(0.0, getattr(self.p, 'eom_gate_jitter_ps', 0.0) * 1e-3)
        effective = np.clip(duty + jitter, 0.01, 1.0)
        hold_noise = getattr(self.p, 'eom_gate_hold_noise_mw', 0.0)
        plus = plus * effective + self.rng.normal(0.0, hold_noise, size=plus.shape)
        minus = minus * effective + self.rng.normal(0.0, hold_noise, size=minus.shape)
        return np.clip(plus, 0.0, None), np.clip(minus, 0.0, None)

    def _apply_mode_mix(self, arr):
        mat = self.p.mode_mix_matrix
        if isinstance(mat, (list, tuple)):
            mat = np.array(mat, dtype=float)
            if mat.ndim == 2 and mat.shape == (len(arr), len(arr)):
                return mat @ arr
        return arr

    def _apply_neighbor_ct(self, arr):
        bleed = 10 ** (self.p.ct_neighbor_db / 10.0)
        diag_bleed = 10 ** (self.p.ct_diag_db / 10.0)
        shifted = np.roll(arr, 1) + np.roll(arr, -1)
        arr = arr + bleed * shifted
        diag = np.roll(np.roll(arr, 1), 1) + np.roll(np.roll(arr, 1), -1)
        diag += np.roll(np.roll(arr, -1), 1) + np.roll(np.roll(arr, -1), -1)
        arr = arr + diag_bleed * diag
        return arr

    def simulate(self, power_vec_plus, power_vec_minus, dt_ns):
        plus = np.clip(np.asarray(power_vec_plus, dtype=float), 0.0, None)
        minus = np.clip(np.asarray(power_vec_minus, dtype=float), 0.0, None)
        size = len(plus)
        self._ensure_state(size)
        if self.p.mode_mix_matrix:
            plus = self._apply_mode_mix(plus)
            minus = self._apply_mode_mix(minus)
            plus = np.clip(plus, 0.0, None)
            minus = np.clip(minus, 0.0, None)
        if self.p.ct_model == "neighbor" and size > 0:
            plus = self._apply_neighbor_ct(plus)
            minus = self._apply_neighbor_ct(minus)
        elif self.p.ct_model == "global" and size > 0:
            bleed = 10 ** (self.p.crosstalk_db / 10.0)
            total = plus + minus
            plus = plus + bleed * total
            minus = minus + bleed * total
        if self.p.voa_bits > 0:
            levels = max(2, 1 << int(self.p.voa_bits))
            span = max(float(plus.max(initial=0.0)), float(minus.max(initial=0.0)), 1e-12)
            step = span / (levels - 1) if levels > 1 else span
            if step > 0:
                plus = np.round(plus / step) * step
                minus = np.round(minus / step) * step
        if float(self.p.soa_pattern_alpha) > 0.0:
            alpha = float(self.p.soa_pattern_alpha)
            plus = (1 - alpha) * plus + alpha * self._pattern_prev_plus
            minus = (1 - alpha) * minus + alpha * self._pattern_prev_minus
            self._pattern_prev_plus = plus
            self._pattern_prev_minus = minus
        if self.p.soa_on or getattr(self.p, 'amp_type', 'soa').lower() == 'edfa':
            plus, minus = self._apply_soa(plus, minus, dt_ns)
        if self.p.sat_abs_on:
            plus, minus = self._apply_sat_abs(plus, minus)
        if self.p.hard_clip_on:
            plus, minus = self._apply_hard_clip(plus, minus)
        if self.p.mzi_on:
            plus, minus = self._apply_mzi(plus, minus, dt_ns)
        if getattr(self.p, 'post_clip_on', False):
            plus, minus = self._apply_post_clip(plus, minus)
        if getattr(self.p, 'voa_post_db', 0.0) != 0.0:
            voa_scale = 10 ** (-self.p.voa_post_db / 10.0)
            plus = plus * voa_scale
            minus = minus * voa_scale
        if getattr(self.p, 'eom_gate_on', False):
            plus, minus = self._apply_eom_gate(plus, minus, dt_ns)
        loss_db = float(self.p.ins_loss_db_mean)
        if float(self.p.ins_loss_db_sigma) > 0.0:
            loss_db = self.rng.normal(loss_db, float(self.p.ins_loss_db_sigma))
        trans_scale = float(self.p.transmittance) * 10 ** (-loss_db / 10.0)
        plus = plus * trans_scale
        minus = minus * trans_scale
        stray = 10 ** (self.p.stray_floor_db / 10.0)
        mean_total = np.mean(plus + minus)
        plus += stray * mean_total
        minus += stray * mean_total
        return plus, minus, plus.tolist(), minus.tolist()

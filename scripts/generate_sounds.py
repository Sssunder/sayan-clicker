"""Generate warm, cozy 16-bit 44.1 kHz mono WAV sound assets for Sayan Clicker."""

from __future__ import annotations

import math
import random
import struct
import wave
from dataclasses import dataclass
from pathlib import Path

SAMPLE_RATE = 44100
MAX_INT16 = 32767
TWO_PI = 2.0 * math.pi


class BiquadFilter:
    """Second-order IIR biquad filter for gentle spectral shaping."""

    def __init__(self, b0: float, b1: float, b2: float, a1: float, a2: float) -> None:
        self.b0 = b0
        self.b1 = b1
        self.b2 = b2
        self.a1 = a1
        self.a2 = a2
        self.x1 = 0.0
        self.x2 = 0.0
        self.y1 = 0.0
        self.y2 = 0.0

    @classmethod
    def lowpass(cls, cutoff_hz: float, q: float = 0.7071, sample_rate: int = SAMPLE_RATE) -> BiquadFilter:
        """Create a second-order Butterworth-style lowpass filter."""
        w0 = TWO_PI * cutoff_hz / sample_rate
        cos_w0 = math.cos(w0)
        alpha = math.sin(w0) / (2.0 * q)
        a0 = 1.0 + alpha
        b1 = (1.0 - cos_w0) / a0
        return cls(
            b0=0.5 * b1,
            b1=b1,
            b2=0.5 * b1,
            a1=(-2.0 * cos_w0) / a0,
            a2=(1.0 - alpha) / a0,
        )

    @classmethod
    def bandpass(cls, center_hz: float, q: float = 1.4, sample_rate: int = SAMPLE_RATE) -> BiquadFilter:
        """Create a constant-0dB-peak second-order bandpass filter."""
        w0 = TWO_PI * center_hz / sample_rate
        cos_w0 = math.cos(w0)
        alpha = math.sin(w0) / (2.0 * q)
        a0 = 1.0 + alpha
        return cls(
            b0=alpha / a0,
            b1=0.0,
            b2=-alpha / a0,
            a1=(-2.0 * cos_w0) / a0,
            a2=(1.0 - alpha) / a0,
        )

    def process(self, x: float) -> float:
        """Filter a single sample using Direct Form I."""
        y = (
            self.b0 * x
            + self.b1 * self.x1
            + self.b2 * self.x2
            - self.a1 * self.y1
            - self.a2 * self.y2
        )
        self.x2 = self.x1
        self.x1 = x
        self.y2 = self.y1
        self.y1 = y
        return y

    def process_buffer(self, samples: list[float]) -> list[float]:
        """Filter an entire sample buffer in sequence."""
        return [self.process(x) for x in samples]


@dataclass(frozen=True)
class PurrConfig:
    """Parameters defining a cozy feline purr timbre."""

    duration_s: float
    pulse_hz: float
    harmonic_weights: tuple[float, ...]
    breath_hz: float
    lowpass_hz: float
    breath_cycles: float
    noise_mix: float
    fade_in_s: float
    fade_out_s: float
    target_peak: float
    seed: int


@dataclass(frozen=True)
class BellNote:
    """Parameters for a soft chime/bell tone placed on a timeline."""

    freq_hz: float
    start_s: float
    decay_tau_s: float
    gain: float = 1.0
    attack_s: float = 0.005
    pitch_scoop: float = 0.0


def raised_cosine_ramp(t: float) -> float:
    """Map t in [0, 1] onto a C1-smooth raised-cosine ramp."""
    if t <= 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    return 0.5 * (1.0 - math.cos(math.pi * t))


def apply_fade_envelope(samples: list[float], fade_in_s: float, fade_out_s: float) -> list[float]:
    """Apply smooth raised-cosine fade-in and fade-out without clicking."""
    n = len(samples)
    fade_in_n = max(1, int(round(fade_in_s * SAMPLE_RATE)))
    fade_out_n = max(1, int(round(fade_out_s * SAMPLE_RATE)))
    out = list(samples)
    for i in range(n):
        gain = 1.0
        if i < fade_in_n:
            gain *= raised_cosine_ramp(i / fade_in_n)
        dist_from_end = n - 1 - i
        if dist_from_end < fade_out_n:
            gain *= raised_cosine_ramp(dist_from_end / fade_out_n)
        out[i] *= gain
    return out


def remove_dc(samples: list[float]) -> list[float]:
    """Subtract mean DC offset before enveloping so endpoints stay strictly zero."""
    if not samples:
        return []
    mean_dc = sum(samples) / len(samples)
    return [x - mean_dc for x in samples]


def quantize_pcm16(samples: list[float], target_peak: float) -> list[int]:
    """Scale float samples safely to target_peak and quantize to signed int16."""
    if not samples:
        return []
    peak = max((abs(x) for x in samples), default=0.0)
    scale = (target_peak * MAX_INT16 / peak) if peak > 1e-9 else 0.0
    pcm: list[int] = []
    for x in samples:
        val = int(round(x * scale))
        if val > MAX_INT16:
            val = MAX_INT16
        elif val < -MAX_INT16:
            val = -MAX_INT16
        pcm.append(val)
    return pcm


def finalize_pcm16(
    samples: list[float],
    fade_in_s: float,
    fade_out_s: float,
    target_peak: float,
) -> list[int]:
    """Remove DC offset, apply smooth end fades, and scale cleanly to int16."""
    centered = remove_dc(samples)
    enveloped = apply_fade_envelope(centered, fade_in_s=fade_in_s, fade_out_s=fade_out_s)
    return quantize_pcm16(enveloped, target_peak=target_peak)


def synthesize_purr(cfg: PurrConfig) -> list[int]:
    """Synthesize a soft amplitude-modulated cat purr with warm breath noise."""
    total_samples = int(round(cfg.duration_s * SAMPLE_RATE))
    rng = random.Random(cfg.seed)

    raw_noise = [rng.uniform(-1.0, 1.0) for _ in range(total_samples)]
    bp_noise = BiquadFilter.bandpass(cfg.breath_hz, q=1.45).process_buffer(raw_noise)
    soft_noise = BiquadFilter.lowpass(cfg.lowpass_hz + 50.0, q=0.7071).process_buffer(bp_noise)
    noise_rms = math.sqrt(sum(x * x for x in soft_noise) / max(1, total_samples)) or 1.0

    tone_filter = BiquadFilter.lowpass(cfg.lowpass_hz, q=0.7071)
    tone_buf: list[float] = [0.0] * total_samples
    mod_buf: list[float] = [0.0] * total_samples
    breath_buf: list[float] = [0.0] * total_samples

    phase = 0.0
    lfo_phase = 0.0
    for i in range(total_samples):
        t = i / SAMPLE_RATE
        # Gentle organic drift keeps the purr alive rather than mechanical.
        inst_hz = cfg.pulse_hz + 0.40 * math.sin(TWO_PI * 1.35 * t)
        phase += TWO_PI * inst_hz / SAMPLE_RATE
        lfo_phase += TWO_PI * inst_hz / SAMPLE_RATE

        lfo = 0.5 + 0.5 * math.sin(lfo_phase)
        mod = 0.38 + 0.62 * (lfo ** 1.35)
        breath = 0.78 + 0.22 * math.sin(TWO_PI * (cfg.breath_cycles / cfg.duration_s) * t - 0.5 * math.pi)

        tone = 0.0
        for idx, weight in enumerate(cfg.harmonic_weights, start=1):
            tone += weight * math.sin(idx * phase)

        tone_buf[i] = tone_filter.process(tone * mod * breath)
        mod_buf[i] = mod
        breath_buf[i] = breath

    tone_rms = math.sqrt(sum(x * x for x in tone_buf) / max(1, total_samples)) or 1.0
    mixed: list[float] = [0.0] * total_samples
    tone_weight = 1.0 - cfg.noise_mix
    for i in range(total_samples):
        norm_tone = tone_buf[i] / tone_rms
        norm_noise = (soft_noise[i] / noise_rms) * (0.55 + 0.45 * mod_buf[i]) * breath_buf[i]
        mixed[i] = tone_weight * norm_tone + cfg.noise_mix * norm_noise

    return finalize_pcm16(mixed, cfg.fade_in_s, cfg.fade_out_s, cfg.target_peak)


def synthesize_tap(
    duration_s: float = 0.10,
    f_start: float = 260.0,
    f_end: float = 140.0,
    target_peak: float = 0.16,
    seed: int = 1,
) -> list[int]:
    """Synthesize a quiet rounded paw 'тык': soft low thump + faint tap attack."""
    total_samples = int(round(duration_s * SAMPLE_RATE))
    rng = random.Random(seed)
    attack_noise = BiquadFilter.lowpass(900.0, q=0.7071).process_buffer(
        [rng.uniform(-1.0, 1.0) for _ in range(total_samples)]
    )

    samples: list[float] = [0.0] * total_samples
    phase = 0.0
    for i in range(total_samples):
        u = i / max(1, total_samples - 1)
        t = i / SAMPLE_RATE
        freq = f_end + (f_start - f_end) * math.exp(-u * 6.0)
        phase += TWO_PI * freq / SAMPLE_RATE
        attack = raised_cosine_ramp(t / 0.004)
        decay = math.exp(-u * 5.0)
        tail = 1.0 - raised_cosine_ramp((u - 0.8) / 0.2)
        env = attack * decay * tail
        body = math.sin(phase) + 0.15 * math.sin(2.0 * phase)
        samples[i] = env * (body + 0.10 * attack_noise[i])

    return finalize_pcm16(samples, fade_in_s=0.003, fade_out_s=0.020, target_peak=target_peak)


def synthesize_meow(
    duration_s: float = 0.42,
    target_peak: float = 0.20,
    seed: int = 103,
    f_a: float = 420.0,
    f_b: float = 475.0,
    f_c: float = 620.0,
    f_d: float = 460.0,
    trill_depth: float = 0.10,
) -> list[int]:
    """Synthesize a relaxed, unobtrusive kitten mew with zero harsh buzz."""
    total_samples = int(round(duration_s * SAMPLE_RATE))
    rng = random.Random(seed)
    breath_air = BiquadFilter.bandpass(780.0, q=1.8).process_buffer(
        [rng.uniform(-1.0, 1.0) for _ in range(total_samples)]
    )
    vocal_lp = BiquadFilter.lowpass(1900.0, q=0.7071)

    samples: list[float] = [0.0] * total_samples
    phase = 0.0
    for i in range(total_samples):
        t = i / SAMPLE_RATE
        u = i / max(1, total_samples - 1)

        # Smooth pitch contour: f_a -> f_b ("mrr") -> f_c -> settle at f_d.
        if u < 0.14:
            freq = f_a + (f_b - f_a) * raised_cosine_ramp(u / 0.14)
        elif u < 0.46:
            freq = f_b + (f_c - f_b) * raised_cosine_ramp((u - 0.14) / 0.32)
        else:
            freq = f_c - (f_c - f_d) * raised_cosine_ramp((u - 0.46) / 0.54)

        phase += TWO_PI * freq / SAMPLE_RATE

        trill = 1.0 - trill_depth * (1.0 - raised_cosine_ramp(u / 0.18)) * (
            0.5 - 0.5 * math.cos(TWO_PI * 28.0 * t)
        )

        vowel_brightness = math.sin(math.pi * min(1.0, u / 0.92)) ** 0.8
        voice = (
            1.00 * math.sin(phase)
            + 0.18 * vowel_brightness * math.sin(2.0 * phase)
            + 0.05 * (vowel_brightness ** 1.5) * math.sin(3.0 * phase)
        )

        attack = raised_cosine_ramp(t / 0.030)
        release = raised_cosine_ramp((duration_s - t) / 0.125)
        body = 0.78 + 0.22 * math.sin(math.pi * min(1.0, u / 0.85))
        env = attack * release * body * trill

        samples[i] = vocal_lp.process((voice + 0.03 * breath_air[i]) * env)

    return finalize_pcm16(samples, fade_in_s=0.012, fade_out_s=0.045, target_peak=target_peak)


def add_bell_note(buffer: list[float], note: BellNote) -> None:
    """Render a soft sine/triangle bell tone additively into buffer."""
    total_samples = len(buffer)
    start_idx = int(round(note.start_s * SAMPLE_RATE))
    if start_idx >= total_samples:
        return

    phase = 0.0
    # Stop rendering once exponential tail is inaudibly small (-80 dB).
    max_len = min(total_samples - start_idx, int(round(note.decay_tau_s * 9.5 * SAMPLE_RATE)))
    for k in range(max_len):
        t = k / SAMPLE_RATE
        scoop = 1.0 + note.pitch_scoop * math.exp(-t / 0.008)
        phase += TWO_PI * (note.freq_hz * scoop) / SAMPLE_RATE

        attack = raised_cosine_ramp(t / note.attack_s)
        decay = math.exp(-t / note.decay_tau_s)
        shimmer_decay = math.exp(-t / (note.decay_tau_s * 0.45))

        # Warm fundamental + gentle decaying 2nd harmonic + subtle soft-triangle 3rd harmonic.
        tone = (
            0.84 * math.sin(phase)
            + 0.12 * shimmer_decay * math.sin(2.0 * phase)
            - 0.04 * shimmer_decay * math.sin(3.0 * phase)
        )
        buffer[start_idx + k] += note.gain * attack * decay * tone


def add_soft_pop(buffer: list[float], start_s: float, start_hz: float, end_hz: float, duration_s: float, gain: float) -> None:
    """Render a tiny cozy percussive pop/paw-tap into buffer."""
    start_idx = int(round(start_s * SAMPLE_RATE))
    count = int(round(duration_s * SAMPLE_RATE))
    phase = 0.0
    for k in range(count):
        idx = start_idx + k
        if idx >= len(buffer):
            break
        u = k / max(1, count - 1)
        freq = start_hz + (end_hz - start_hz) * u
        phase += TWO_PI * freq / SAMPLE_RATE
        env = raised_cosine_ramp(u / 0.25) * math.exp(-u * 4.2) * (1.0 - raised_cosine_ramp((u - 0.75) / 0.25))
        buffer[idx] += gain * env * math.sin(phase)


def synthesize_notes_sequence(
    duration_s: float,
    notes: tuple[BellNote, ...],
    target_peak: float,
    fade_out_s: float,
    pops: tuple[tuple[float, float, float, float, float], ...] = (),
) -> list[int]:
    """Render a sequence of soft bell notes and optional warm pops into PCM16."""
    buf = [0.0] * int(round(duration_s * SAMPLE_RATE))
    for note in notes:
        add_bell_note(buf, note)
    for pop_args in pops:
        add_soft_pop(buf, *pop_args)
    return finalize_pcm16(buf, fade_in_s=0.003, fade_out_s=fade_out_s, target_peak=target_peak)


def write_wav_mono16(path: Path, pcm_samples: list[int], sample_rate: int = SAMPLE_RATE) -> None:
    """Write mono 16-bit PCM WAV data cleanly to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = struct.pack(f"<{len(pcm_samples)}h", *pcm_samples)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(raw)


def generate_all_sounds(output_dir: Path) -> dict[str, Path]:
    """Synthesize all cozy feline WAV assets into output_dir."""
    sound_specs: dict[str, list[int]] = {
        "tap1.wav": synthesize_tap(duration_s=0.10, f_start=240.0, f_end=130.0, target_peak=0.16, seed=11),
        "tap2.wav": synthesize_tap(duration_s=0.09, f_start=300.0, f_end=170.0, target_peak=0.16, seed=22),
        "tap3.wav": synthesize_tap(duration_s=0.08, f_start=360.0, f_end=210.0, target_peak=0.15, seed=33),
        "meow.wav": synthesize_meow(duration_s=0.42, target_peak=0.20, seed=103),
        "meow2.wav": synthesize_meow(
            duration_s=0.30, target_peak=0.18, seed=205,
            f_a=520.0, f_b=560.0, f_c=760.0, f_d=560.0, trill_depth=0.08,
        ),
        "treat.wav": synthesize_notes_sequence(
            duration_s=0.24,
            notes=(
                BellNote(freq_hz=1046.50, start_s=0.000, decay_tau_s=0.048, gain=0.85, attack_s=0.004),
                BellNote(freq_hz=1318.51, start_s=0.072, decay_tau_s=0.058, gain=1.00, attack_s=0.004),
            ),
            pops=((0.000, 290.0, 520.0, 0.020, 0.16),),
            target_peak=0.20,
            fade_out_s=0.030,
        ),
        "levelup.wav": synthesize_notes_sequence(
            duration_s=0.58,
            notes=(
                BellNote(freq_hz=523.25, start_s=0.000, decay_tau_s=0.085, gain=0.78, attack_s=0.006),
                BellNote(freq_hz=659.25, start_s=0.092, decay_tau_s=0.092, gain=0.84, attack_s=0.006),
                BellNote(freq_hz=783.99, start_s=0.184, decay_tau_s=0.105, gain=0.90, attack_s=0.006),
                BellNote(freq_hz=1046.50, start_s=0.280, decay_tau_s=0.135, gain=1.00, attack_s=0.006),
            ),
            target_peak=0.22,
            fade_out_s=0.085,
        ),
        "zoomies.wav": synthesize_notes_sequence(
            duration_s=0.36,
            notes=(
                BellNote(freq_hz=523.25, start_s=0.000, decay_tau_s=0.025, gain=0.72, attack_s=0.003, pitch_scoop=0.06),
                BellNote(freq_hz=659.25, start_s=0.040, decay_tau_s=0.025, gain=0.76, attack_s=0.003, pitch_scoop=0.06),
                BellNote(freq_hz=587.33, start_s=0.080, decay_tau_s=0.025, gain=0.80, attack_s=0.003, pitch_scoop=0.05),
                BellNote(freq_hz=783.99, start_s=0.120, decay_tau_s=0.025, gain=0.84, attack_s=0.003, pitch_scoop=0.06),
                BellNote(freq_hz=880.00, start_s=0.160, decay_tau_s=0.025, gain=0.88, attack_s=0.003, pitch_scoop=0.06),
                BellNote(freq_hz=1046.50, start_s=0.200, decay_tau_s=0.027, gain=0.92, attack_s=0.003, pitch_scoop=0.06),
                BellNote(freq_hz=987.77, start_s=0.240, decay_tau_s=0.027, gain=0.95, attack_s=0.003, pitch_scoop=0.05),
                BellNote(freq_hz=1318.51, start_s=0.280, decay_tau_s=0.042, gain=1.00, attack_s=0.003, pitch_scoop=0.07),
            ),
            pops=(
                (0.000, 185.0, 95.0, 0.016, 0.14),
                (0.080, 195.0, 100.0, 0.016, 0.14),
                (0.160, 210.0, 105.0, 0.016, 0.14),
                (0.240, 225.0, 115.0, 0.016, 0.14),
            ),
            target_peak=0.20,
            fade_out_s=0.032,
        ),
    }

    written: dict[str, Path] = {}
    for filename, samples in sound_specs.items():
        dest = output_dir / filename
        write_wav_mono16(dest, samples)
        written[filename] = dest
    return written


def main() -> None:
    """Entry point for generating WAV assets relative to project root."""
    project_root = Path(__file__).resolve().parent.parent
    sounds_dir = project_root / "assets" / "sounds"
    written = generate_all_sounds(sounds_dir)
    for name, path in written.items():
        print(f"Generated {name} -> {path} ({path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()

"""Sound for the launch film: the music bed, the sound cues and the mix (voice on top, music ducked under it).

Everything is synthesised here (numpy), so it is free, licence-clean and identical on every render:
  - the bed: a warm pad in D (Dadd9, Bm7, Gmaj7, Asus4, one chord a bar of 72 BPM), a sparse felt-piano motif, and a soft
    low pulse under the product chapters; near silence (one sustained note and room tone) for the cold open; the pad alone
    under Trust; it resolves on D major for the last card;
  - cues: a dry UI tick on each click, a two-note chime when an agent's answer lands, a warm seal on approval, a soft
    whoosh when the new tile appears, a low swell at the reveal, a low tone when the figure is struck through;
  - the mix: music ducked about 18 dB under the voice (150 ms down, 600 ms back up).
The Lyria bed via OpenRouter was tried first (10 Oct): its only endpoint was down and returned no audio, at no cost.
"""
import wave
from pathlib import Path

import numpy as np

SR = 48000
BEAT = 60 / 72
BAR = 4 * BEAT
D = {"D2": 73.42, "A2": 110.0, "B2": 123.47, "D3": 146.83, "E3": 164.81, "F#3": 185.0, "G3": 196.0, "A3": 220.0, "B3": 246.94,
     "C#4": 277.18, "D4": 293.66, "E4": 329.63, "F#4": 369.99, "G4": 392.0, "A4": 440.0, "B4": 493.88, "D5": 587.33}
CHORDS = [["D3", "A3", "E4", "F#4"], ["B2", "F#3", "A3", "D4"], ["G3", "B3", "D4", "F#4"], ["A2", "E3", "A3", "D4"]]
SUS = ["D3", "A3", "E4"]
MOTIF = ["F#4", "A4", "E4", "D4", "B3", "D4", "A3", "E4"]


def db(x: float) -> float:
    return 10 ** (x / 20)


def _env(n: int, a: float, r: float) -> np.ndarray:
    t = np.arange(n) / SR
    return np.minimum(1, t / max(a, 1e-3)) * np.minimum(1, (n / SR - t) / max(r, 1e-3))


def pad_note(f: float, n: int, rng) -> np.ndarray:
    t = np.arange(n) / SR
    out = np.zeros(n)
    for det in (-0.12, 0.0, 0.11):
        ph = rng.uniform(0, 6.28)
        ff = f * (1 + det / 100)
        out += np.sin(2 * np.pi * ff * t + ph) + 0.18 * np.sin(4 * np.pi * ff * t + ph) + 0.06 * np.sin(6 * np.pi * ff * t + ph)
    return out / 3


def piano(f: float, secs: float = 3.5) -> np.ndarray:
    t = np.arange(int(secs * SR)) / SR
    tone = sum(a * np.sin(2 * np.pi * f * k * t) * np.exp(-t * (1.2 + k * 0.9)) for k, a in ((1, 1), (2, .35), (3, .12), (4, .05)))
    return tone * np.minimum(1, t / 0.012)


def lowpass(x: np.ndarray, hz: float) -> np.ndarray:
    """A gentle low-pass (first-order response, applied in the frequency domain)."""
    f = np.fft.rfftfreq(len(x), 1 / SR)
    return np.fft.irfft(np.fft.rfft(x) / np.sqrt(1 + (f / hz) ** 2), len(x))


def reverb(x: np.ndarray) -> np.ndarray:
    out = x.copy()
    for ms, g in ((47, .32), (83, .27), (131, .22), (197, .18), (283, .14), (409, .1), (587, .07)):
        k = int(ms / 1000 * SR)
        out[k:] += g * x[:-k]
    return out


def bed(total: float, sections: dict) -> np.ndarray:
    """The music bed, `total` seconds. sections: cold (end of the near-silent open), reveal (the swell lands),
    pulse (start, end) of the product chapters, padonly (start, end) of Trust, close (start of the last card)."""
    rng = np.random.default_rng(7)
    n = int(total * SR)
    x = np.zeros(n)
    cold, reveal = sections["cold"], sections["reveal"]
    # cold open: one sustained D4 and room tone
    k = int(min(reveal, total) * SR)
    x[:k] += 0.16 * pad_note(D["D4"], k, rng) * _env(k, 2.5, 1.5)
    x[:k] += 0.04 * pad_note(D["A3"], k, rng) * _env(k, 6, 1.5) * (np.arange(k) / SR > cold)
    # pad from the reveal, one chord a bar, crossfaded
    t0 = reveal
    i = 0
    while t0 < total:
        chord = ["D3", "A3", "D4", "F#4"] if t0 >= sections["close"] else CHORDS[i % 4]
        L = min(BAR + 1.2, total - t0)
        m = int(L * SR)
        a = int(t0 * SR)
        seg = sum(pad_note(D[c], m, rng) for c in chord) / len(chord)
        x[a:a + m] += 0.30 * seg[:n - a] * _env(m, 1.0, 1.2)[:n - a]
        t0 += BAR
        i += 1
    # piano motif, sparse, not under Trust
    t = reveal + BAR
    j = 0
    while t < total - 2:
        if not (sections["padonly"][0] <= t < sections["padonly"][1]):
            p = piano(D[MOTIF[j % len(MOTIF)]])
            a = int(t * SR)
            x[a:a + len(p)] += 0.11 * p[:n - a]
        t += 2 * BEAT if j % 4 != 3 else 4 * BEAT
        j += 1
    # low pulse under the product chapters
    s, e = sections["pulse"]
    t = s
    while t < e:
        p = np.sin(2 * np.pi * D["D2"] * np.arange(int(0.6 * SR)) / SR) * np.exp(-np.arange(int(0.6 * SR)) / SR * 7)
        a = int(t * SR)
        x[a:a + len(p)] += 0.09 * p[:n - a] * min(1, (t - s) / 4, (e - t) / 3)
        t += BEAT
    # room tone
    x += 0.004 * lowpass(rng.standard_normal(n), 900)
    x = reverb(lowpass(x, 3200))
    fade = int(2.5 * SR)
    x[-fade:] *= np.linspace(1, 0, fade)
    return x / (np.abs(x).max() + 1e-9) * db(-14)


# ---- cues ------------------------------------------------------------------------------------------------------------------------

def cue(kind: str) -> np.ndarray:
    rng = np.random.default_rng(len(kind))
    if kind == "tick":
        m = int(0.04 * SR)
        t = np.arange(m) / SR
        y = (np.diff(rng.standard_normal(m + 1)) * 0.5 + np.sin(2 * np.pi * 2300 * t)) * np.exp(-t * 140)
        return y * db(-27)
    if kind == "chime":
        y = np.zeros(int(1.4 * SR))
        for off, f in ((0, 880.0), (0.11, 1174.66)):
            p = piano(f, 1.2)
            a = int(off * SR)
            y[a:a + len(p)] += p
        return reverb(y) * db(-25)
    if kind == "seal":
        t = np.arange(int(0.7 * SR)) / SR
        y = (np.sin(2 * np.pi * 110 * t) + 0.5 * np.sin(2 * np.pi * 220 * t) + 0.2 * np.sin(2 * np.pi * 330 * t)) * np.exp(-t * 6) * np.minimum(1, t / 0.005)
        return reverb(y) * db(-17)
    if kind == "whoosh":
        m = int(0.8 * SR)
        y = lowpass(rng.standard_normal(m), 1400) * np.sin(np.pi * np.arange(m) / m) ** 2
        return y / np.abs(y).max() * db(-26)
    if kind == "swell":
        m = int(3.2 * SR)
        t = np.arange(m) / SR
        env = np.minimum(1, t / 2.5) ** 2 * np.minimum(1, (3.2 - t) / 0.7)
        y = (np.sin(2 * np.pi * 55 * t) + 0.6 * np.sin(2 * np.pi * 110 * t) + 0.3 * lowpass(rng.standard_normal(m), 500)) * env
        return y / np.abs(y).max() * db(-15)
    if kind == "strike":
        m = int(0.6 * SR)
        t = np.arange(m) / SR
        y = (np.sin(2 * np.pi * 98 * t) * 0.8 + lowpass(rng.standard_normal(m), 2500) * 0.6) * np.exp(-t * 9) * np.minimum(1, t / 0.004)
        return y / np.abs(y).max() * db(-21)
    raise KeyError(kind)


# ---- the mix ---------------------------------------------------------------------------------------------------------------------

def read_wav(p: Path) -> np.ndarray:
    with wave.open(str(p)) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(float) / 32768
        if w.getnchannels() == 2:
            x = x.reshape(-1, 2).mean(1)
        rate = w.getframerate()
    if rate != SR:
        x = np.interp(np.arange(int(len(x) * SR / rate)) * rate / SR, np.arange(len(x)), x)
    return x


def place(track: np.ndarray, clip: np.ndarray, at: float, gain: float = 1.0) -> None:
    a = int(at * SR)
    if a >= len(track):
        return
    b = min(len(track), a + len(clip))
    track[a:b] += gain * clip[:b - a]


def duck(music: np.ndarray, voice: np.ndarray, depth_db: float = 18.0) -> np.ndarray:
    """Music down `depth_db` while the voice speaks: 150 ms down, 600 ms back up."""
    hop = int(0.01 * SR)
    frames = np.abs(voice[: len(voice) // hop * hop]).reshape(-1, hop).max(1)
    on = (frames > db(-40)).astype(float)
    # hold the duck through the breaths between sentences (gaps under 0.7 s), so the music does not pump in every pause
    k = np.ones(70)
    before = np.convolve(on, k)[: len(on)] > 0
    after = np.convolve(on[::-1], k)[: len(on)][::-1] > 0
    on = np.maximum(on, before & after).astype(float)
    g = np.empty_like(on)
    cur = 0.0
    for i, v in enumerate(on):
        cur += (v - cur) * (0.067 if v > cur else 0.0167)
        g[i] = cur
    gain = db(-depth_db * 1.0) ** g
    gain = np.repeat(gain, hop)
    out = music.copy()
    out[: len(gain)] *= gain
    return out


def write_wav(p: Path, x: np.ndarray) -> None:
    y = np.clip(x, -1, 1)
    st = (np.stack([y, y], 1) * 32767).astype(np.int16)
    with wave.open(str(p), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(st.tobytes())


if __name__ == "__main__":  # a self-check: the duck works and the bed is not silent
    v = np.zeros(SR * 4)
    v[SR:2 * SR] = 0.3
    m = np.ones(SR * 4) * 0.1
    d = duck(m, v)
    assert d[int(1.9 * SR)] < 0.1 * db(-15) and abs(d[int(3.9 * SR)] - 0.1) < 0.01
    b = bed(20, {"cold": 3, "reveal": 6, "pulse": (8, 16), "padonly": (16, 18), "close": 18})
    assert np.abs(b).max() > 0.1
    print("sound ok")

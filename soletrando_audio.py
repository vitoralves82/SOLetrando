"""Utilitarios de audio curtos usados pelo SOLetrando."""

from array import array
import io
import math
import sys
import wave


def build_tone_wav(frequency, duration_ms, sample_rate=22050):
    """Gera um WAV mono em memoria com ataque e queda suaves."""
    sample_count = max(1, int(sample_rate * duration_ms / 1000))
    edge = max(1, int(sample_rate * 0.01))
    samples = array("h")
    for index in range(sample_count):
        envelope = min(1.0, index / edge, (sample_count - index - 1) / edge)
        value = math.sin(2 * math.pi * frequency * index / sample_rate)
        samples.append(int(value * max(0.0, envelope) * 9000))
    if sys.byteorder != "little":
        samples.byteswap()

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(samples.tobytes())
    return buffer.getvalue()

import io
import unittest
import wave

from soletrando_audio import build_tone_wav


class AudioToolsTests(unittest.TestCase):
    def test_tone_is_a_valid_wav_with_expected_duration(self):
        data = build_tone_wav(800, 120)
        with wave.open(io.BytesIO(data), "rb") as wav:
            self.assertEqual(wav.getnchannels(), 1)
            self.assertEqual(wav.getsampwidth(), 2)
            self.assertEqual(wav.getframerate(), 22050)
            self.assertAlmostEqual(
                wav.getnframes() / wav.getframerate(), 0.12, places=2
            )

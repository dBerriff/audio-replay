# famous_trains
Code for Famous Trains model railway, Derby.

Play mp3 and wav files stored on an SD card. CircuitPython supports mono or stereo, at 22 KHz sample rate (or less) and 16-bit WAV format. See: https://learn.adafruit.com/circuitpython-essentials/circuitpython-audio-out

Audacity is recommended as an open-source audio editor.

### Files:

**audio_lib.py**: module. This module must be uploaded to the CircuitPython storage, without changing the name, before running either of the following scripts.

**play_audio.py**: script. This script outputs line-level, mono audio. It imports the required classes and functions from the module audio_lib.py. play_audio.py can be uploaded as the script main.py to run at power-up.

**play_audio_i2s.py**: script. This script outputs audio as an I2S stream. It is an alternative to play_audio.py and has the same requirements.

# famous_trains
Code for Famous Trains model railway, Derby.

Play mp3 and wav files stored on an SD card. CircuitPython supports mono or stereo, at 22 KHz sample rate (or less) and 16-bit WAV format. See: https://learn.adafruit.com/circuitpython-essentials/circuitpython-audio-out

Audacity is recommended as an open-source audio editor.

### Files:

**play_audio.py**: script. This script outputs line-level, mono audio. It imports the required classes and functions from the module *audio_lib.py* . Can be uploaded as the script *main.py* to run at power-up.

**settings.py**: script. Settings for play_audio.py

**command_handler_as.py**: script. asyncio version of command handler for DFPlayer Mini (DF1201S chip). controller_as.py will call this module but it is not yet complete.

# famous_trains
Code for Famous Trains model railway, Derby.

Play mp3 and wav files stored on an SD card. CircuitPython supports mono or stereo, at 22 KHz sample rate (or less) and 16-bit WAV format. See: https://learn.adafruit.com/circuitpython-essentials/circuitpython-audio-out .

Control DFPlayer Mini with commands over UART.

Audacity is recommended as an open-source audio editor.

### Files:

**play_audio.py**: CircuitPython script. This script outputs line-level, mono audio (to LM386 analogue board); or I2S digital audio to a MAX98357A board. It calls the module *settings.py* for pin and other settings. Can be uploaded as the script *main.py* to run at power-up.

**settings.py**: CircuitPython script. Settings for *play_audio.py*

**command_handler_as.py**: MicroPython script. *asyncio* version of command handler for DFPlayer Mini. DFPlayer documentation has errors so this is work-in-progress. *controller_as.py* will call this module but is not yet complete.

**command_handler.py**: MicroPython script. *Non-asyncio* version. Uses RP2040 second core to poll for UART input. Also work-in-progress.

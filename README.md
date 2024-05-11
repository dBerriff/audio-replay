# famous_trains
Play mp3 and wav files stored on an SD card. CircuitPython supports mono or stereo, at 22 KHz sample rate (or less) and 16-bit WAV format. See: https://learn.adafruit.com/circuitpython-essentials/circuitpython-audio-out .

Control DFPlayer Mini with commands over UART.

## Files:

### Analogue / I2S Audio

**play_audio.py**: CircuitPython script. This script outputs line-level, mono audio (to LM386 analogue board); or I2S digital audio to a MAX98357A board. It calls the module *settings.py* for pin and other settings. Can be uploaded as the script *main.py* to run at power-up.

**settings.py**: CircuitPython script. Settings for *play_audio.py*

### DFPlayer Mini

**dfp_control.py**: MicroPython script. Controls replay of audio tracks from a DFPlayer Mini (DFP). Requires c_h_as.py, uart_os_as.py and hex_fns.py to be loaded into the microprocessor storage.
See: https://www.flyrontech.com/en/product/fn-m16p-mp3-module.html for DFP documentation. Not all features are implemented on all versions of the DFP 16P. Version tested is: MP3-TF-16P V3.0

**c_h_as.py**: MicroPython script. *asyncio* version of command handler for DFPlayer Mini.

**uart_os_as**: MicroPython script. *asyncio* version. Includes Queue and StreamTR classes

**hex_fns**: MicroPython script. Functions for print-formatting hex values and processing 16-bit register MSB and LSB values.

**text.txt**: Text file. Commands for dfp_control.py. 'rpt' is run as a task so must be the final command if used. Further commands can be issued if 'rpt' is stopped - see the test code in main().

Notes:

- the only 'play' command now used is track(track-number). All other 'play' commands are processed in dfp_control and sent as a series of track() commands.
- dfp_control: 'rpt' is controlled by repeat_flag; initialised as False so must be set True for track-sequence repeats.
- folders have not been used.

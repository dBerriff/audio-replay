# audio-replay
Play mp3 and wav files stored on an SD card from DfPlayer device.

Control DFPlayer Mini with commands over UART.

## Files:

### dfp_mini.py

Code for the FN-M16P Embedded MP3 Audio Module with onboard micro SD-card, referred to as a
DfPlayer Mini. Implements a minimal subset of the documented commands (hexadecimal codes).
The full set of commands included non-functional codes for the particular board tested.

### df_player.py

Abstract code for the DFP player family, initially to support the FN-M16P chip.

Implements replay commands in software to use a minimal set of hardware-player commands.

The code is written using asyncio and Events control the interaction between tasks.

### dfp_support.py

Support methods for the df_player.

### hex_fns.py

Support methods for hexadecimal encoding and printing. Required for dfp_mini.py

### playlist_player.py

Play micro SD-card tracks from a DFP player under push-button control.

### script_player.py

Play micro SD-card tracks from a DFP player under the control a text script.

### data_link.py

Implement a UART data-link between an RP2040-based board and a DFP player.

### buttons.py

Push-button methods for playlist_player.py
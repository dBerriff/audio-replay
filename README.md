# famous_trains
Code for Famous Trains model railway, Derby.
Files:
audio_lib.py: this file can be imported as a module for play_audio.py and play_audio_i2s.py. For this usage, upload the file to the CircuitPython storage without changing the name.
audio_lib.py: this file can also be run as a standalone script. To run this script at power-up, upload the file to the CircuitPython storage with the name: main.py
play_audio.py: this file outputs line-level, mono audio. It imports the required classes and functions from the module audio_lib.py. audio_lib.py must be loaded into the CircuitPython storage with no name change. play_audio.py can be loaded as main.py to run at power-up.
play_audio_i2s.py: this file outputs audio as an I2S stream. It is an alternative to play_audio.py and has the same requriements.

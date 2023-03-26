# SPDX-FileCopyrightText: 2020 Jeff Epler for Adafruit Industries
#
# SPDX-License-Identifier: MIT

# audio_lib.py

"""
    CircuitPython Essentials Audio Out: plays MP3 and WAV files
    See: https://learn.adafruit.com/circuitpython-essentials/
                 circuitpython-audio-out
    Adapted by David Jones for Famous Trains, Derby. 2023
    
    Module of classes and functions for:
    - play_audio.py
    - play_audio_i2s.py
    
    - plays .mp3 and .wav files from a micro SD card
    - line-level or I2S output:
        -- passed as audio_out to play_audio()
    - CircuitPython supports mono or stereo, at 22 KHz sample rate
        (or less) and 16-bit WAV format (ref. above)
    - class inheritance is not used (V 7.3.3 bug)
"""

# hardware
from digitalio import DigitalInOut, Direction, Pull

# audio
from audiomp3 import MP3Decoder
from audiocore import WaveFile
    
# SD storage
import busio
import sdcardio
import storage
import os

# other
from random import randint
import gc  # garbage collection for RAM


def shuffle(tuple_) -> tuple:
    """ return a shuffled tuple of a tuple (or list)
        - Durstenfeld / Fisher-Yates shuffle algorithm """
    n = len(tuple_)
    if n < 2:
        return tuple_
    s_list = list(tuple_)
    limit = n - 1
    for i in range(limit):  # exclusive range
        j = randint(i, limit)  # inclusive range
        if j != i:
            s_list[i], s_list[j] = s_list[j], s_list[i]
    return tuple(s_list)


def file_ext(name_) -> str:
    """ return lower-case file extension """
    if name_.rfind('.', 1) > 0:
        ext_ = name_.rsplit('.', 1)[1].lower()
    else:
        ext_ = ''
    return ext_


def get_audio_filenames(dir_, ext_list=('mp3', 'wav')) -> tuple:
    """ from folder, return a list of type in ext_list
        - CircuitPython libraries replay .mp3 or .wav files
        - skip system files with first char == '.' """
    return tuple([f for f in os.listdir(dir_)
                  if f[0] != '.' and file_ext(f) in ext_list])
    

class SdReader:
    """ sd card reader, SPI protocol """

    def __init__(self, clock, mosi, miso, cs, sd_dir='/sd'):
        self.dir = sd_dir + '/'

        spi = busio.SPI(clock, MOSI=mosi, MISO=miso)
        sd_card = sdcardio.SDCard(spi, cs)
        vfs = storage.VfsFat(sd_card)
        storage.mount(vfs, sd_dir)


class Button:
    """ input button, pull-up logic """

    def __init__(self, pin_):
        self._pin_in = DigitalInOut(pin_)
        self._pin_in.direction = Direction.INPUT
        self._pin_in.pull = Pull.UP

    @property
    def is_off(self) -> bool:
        """ pull-up logic for button not pressed """
        return self._pin_in.value

    @property
    def is_on(self) -> bool:
        """ pull-up logic for button pressed """
        return not self._pin_in.value


class PinOut:
    """ output pin """
    
    def __init__(self, pin_):
        self._pin_out = DigitalInOut(pin_)
        self._pin_out.direction = Direction.OUTPUT
        self.state = False
        
    @property
    def state(self) -> bool:
        """ pin state """
        return self._pin_out.value
    
    @state.setter
    def state(self, value):
        self._pin_out.value = value


def play_audio(media_dir, files, audio_out,
               play_buttons, skip_btn, wait_led):
    """ play mp3 and wav files under button control """
    
    # helper functions
    
    def get_decoder(m_dir, files_):
        """ return decoder if required else None """
        decoder_ = None
        for filename_ in files_:
            if file_ext(filename_) == 'mp3':
                # decoder instantiation requires a file
                audio_file = open(m_dir + filename_, 'rb')
                decoder_ = MP3Decoder(audio_file)
                break  # instantiate once only
        return decoder_
    
    def play_file(m_dir, filename_, decoder_, audio_out_):
        """ play wav or mp3 file """
        audio_file = open(m_dir + filename_, 'rb')
        ext = file_ext(filename_)
        if ext == 'mp3':
            decoder_.file = audio_file
            audio_out_.play(decoder_)
        elif ext == 'wav':
            wave = WaveFile(audio_file)
            audio_out_.play(wave)
        print(f'playing: {filename}')

    def wait_audio_finish(audio_out_, skip_btn_):
        """ wait for audio to complete or skip_button pressed """
        while audio_out_.playing:
            if skip_btn_.is_on:
                audio_out_.stop()
    
    def wait_button_press(play_buttons_):
        """ wait for a button to be pressed """
        print('Waiting for button press ...')
        wait = True
        while wait:
            for button in play_buttons_:
                if button.is_on:
                    wait = False

    # play_audio function

    off = False
    on = True

    # instantiate MP3 decoder (None if not required)
    decoder = get_decoder(media_dir, files)
    wait_led.state = off    
    list_len = len(files)
    list_index = 0
    while True:
        filename = files[list_index]
        play_file(media_dir, filename, decoder, audio_out)
        wait_audio_finish(audio_out, skip_btn)

        gc.collect()  # free up memory between plays
        wait_led.state = on
        wait_button_press(play_buttons)
        wait_led.state = off
        # set index for next file
        list_index = (list_index + 1) % list_len


def main():
    """ test: play audio files under button control
        - pins for Cytron Maker Pi Pico board """
    
    import board

    # AudioOut - line-level audio on a single GP pin
    # module is board-dependent:
    try:
        from audioio import AudioOut
    except ImportError:
        from audiopwmio import PWMAudioOut as AudioOut

    # === USER parameters ===
    
    audio_folder = 'audio/'

    # button pins
    play_pin_1 = board.GP20  # public
    play_pin_2 = board.GP21  # operator
    skip_pin = board.GP22  # useful for testing

    # audio-out pin (mono)
    audio_pin = board.GP18  # Cytron jack socket
    
    # LED: waiting for Play button push
    # onboard LED pin is: GP25 on standard Pico
    led_pin = PinOut(board.GP25)

    # === end USER parameters ===
    
    # set up the GP pins
    # buttons
    play_buttons = (Button(play_pin_1), Button(play_pin_2))
    skip_btn = Button(skip_pin)
    # sd card
    clock = board.GP10
    mosi = board.GP11
    miso = board.GP12
    cs = board.GP15

    # instantiate card reader; default mount is '/sd'
    # default .dir is: '/sd/'
    sd_card = SdReader(clock, mosi, miso, cs)
    audio_folder = sd_card.dir + audio_folder
    print(f'audio folder is: {audio_folder}')

    music_filenames = get_audio_filenames(audio_folder)
    music_filenames = shuffle(music_filenames)  # optional
    
    # play music
    play_audio(audio_folder, music_filenames,
               AudioOut(audio_pin), play_buttons, skip_btn, led_pin)


if __name__ == '__main__':
    main()

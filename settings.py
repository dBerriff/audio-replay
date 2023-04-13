# settings.py
""" consolidate user and device settings """

# import all Pico pin objects to simplify user settings
from board import GP0, GP1, GP2, GP3, GP4, GP5, GP6, GP7, GP8, GP9, \
    GP10, GP11, GP12, GP13, GP14, GP15, GP16, GP17, GP18, GP19, \
    GP20, GP21, GP22, GP23, GP24, GP25, GP26, GP27, LED

# dictionary of available audio folders
audio_source = {'SD': '/sd/audio/', 'pico': '/audio/'}


# === SETTINGS

folder = audio_source['SD']  # "SD" or "pico"

shuffle = 1  # 0 or 1

play_pins = GP20, GP21
skip_pin = GP22
led_pin = LED

button_control = 1  # 0 or 1

i2s_out = 0  # 0 or 1

# audio

# line-level out
audio_pin = GP18

# I2S out
bit_clock = GP16
word_select = GP17  # bit_clock pin + 1
data = GP18

# SD card reader
# pins for Cytron Maker Pi Pico
clock = GP10
mosi = GP11
miso = GP12
cs = GP15
sd_dir = '/sd'  # no trailing /


def main():
    """"""
    print('settings file for play_audio.py')


if __name__ == '__main__':
    main()

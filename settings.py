# settings.py
""" consolidate user and device settings """

# import all Pico pin objects to simplify user settings
from board import GP0, GP1, GP2, GP3, GP4, GP5, GP6, GP7, GP8, GP9, \
    GP10, GP11, GP12, GP13, GP14, GP15, GP16, GP17, GP18, GP19, \
    GP20, GP21, GP22, GP23, GP24, GP25, GP26, GP27, LED

# dictionary of available audio folders
audio_source = {'SD': '/sd/', 'pico': '/audio/'}


# === SETTINGS

folder = audio_source['SD']  # 'SD': SD-card; 'pico: flash RAM

shuffle = 1  # 0 or 1

# set to None if control buttons not required
play_pins = GP20, GP21  
skip_pin = GP22
# set to None for board LED
led_pin = None

button_control = True
diagnose = True

i2s_out = False

# audio pins - can set to None if not used

# line-level pin out
audio_pin = GP18

# I2S pins out
bit_clock = GP16
word_select = GP17  # bit_clock pin + 1
data = GP18

# SD card reader pins
# pins for Cytron Maker Pi Pico
clock = GP10
mosi = GP11
miso = GP12
cs = GP15
sd_dir = '/sd'  # no trailing '/'

# === End of SETTINGS


def main():
    """"""
    print('settings file for play_audio.py')


if __name__ == '__main__':
    main()

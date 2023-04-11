import board
from board import GP0, GP1, GP2, GP3, GP4, GP5, GP6, GP7, GP8, GP9, \
     GP10, GP11, GP12, GP13, GP14, GP15, GP16, GP17, GP18, GP19, \
     GP20, GP21, GP22, GP23, GP24, GP25, GP26, GP27, GP23, LED


# "SD" or "pico"
folder = "SD"

play_pins = GP20, GP27
skip_pin = GP22
led_pin = LED

audio_pin = GP18

# false or true
button_control = 1

# SD card reader
# pins for Cytron Maker Pi Pico
clock = GP10
mosi = GP11
miso = GP12
cs = GP15
sd_dir = '/sd'  # no trailing /

from machine import UART, Pin
from time import sleep
import _thread as thread

"""
    DFPlayer
    Communication format:

    00: start byte       0x7e
    01: version          0xff
    02: bytes following  0x06
    03: command
    04: command feedback 0x01
    05: parameter        msb
    06: parameter        lsb
    07: checksum         msb
    08: checksum         lsb
    09: end byte         0xef
"""
hex_str = ('0', '1', '2', '3', '4', '5', '6', '7', '8', '9',
           'a', 'b', 'c', 'd', 'e', 'f')


uart0 = UART(0, baudrate=9600, tx=Pin(0), rx=Pin(1))
uart1 = UART(1, baudrate=9600, tx=Pin(4), rx=Pin(5))
tx_values = [0x7E, 0xFF, 0x06, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0xEF]
tx_template = bytearray(tx_values)
command = 3
ack = 4
param_h = 5
param_l = 6

cmd = {
    'next': 0x01,
    'prev': 0x02,
    'track': 0x03,  # 0-2999
    'vol_up': 0x04,
    'vol_down': 0x05,
    'vol_set': 0x06,  # 0-30
    'eq_set': 0x07,  # normal/pop/rock/jazz/classic/base
    'play_mode': 0x08,  # repeat/folder-repeat/single-repeat/random
    'play_source': 0x09,  # u/tf/aux/sleep/flash
    'standby': 0x0a,
    'normal': 0x0b,
    'reset': 0x0c,
    'playback': 0x0d,
    'pause': 0x0e,
    'folder': 0x0f,  # 1-10
    'vol_adj': 0x10,  # msb: enable: 1; lsb: gain: 0-31
    'play_repeat': 0x11  # 0: stop; 1: start
    }


def byte_str(b):
    """ return str(hex value) of an 8-bit byte """
    lsh = b & 0xf
    msh = b >> 4
    return hex_str[msh] + hex_str[lsh]


def reg16_str(r):
    """ return str(hex value) of a 16-bit register """
    lsb = r & 0xff
    msb = r >> 8
    return byte_str(msb) + byte_str(lsb)


def byte_array_str(ba):
    """ return str(hex value) of a bytearray """
    ba_str = ''
    for b in ba:
        ba_str += 'x' + byte_str(b) + '\\'
    return ba_str[:-1]


def checksum(byte_array_):
    """ return the 2's complement checksum """
    b_sum = sum(byte_array_) & 0xffff
    checksum_ = -b_sum & 0xffff
    return checksum_


def check_checksum(byte_array_, cs_msb, cs_lsb):
    """ returns 0 for consistent checksum """
    b_sum = sum(byte_array_) & 0xffff
    checksum_ = cs_msb << 8
    checksum_ += cs_lsb
    return (b_sum + checksum_) & 0xffff


def slice_reg16(value):
    """"""
    lsb = value & 0xff
    msb = value >> 8 & 0xff
    return msb, lsb    
    

def build_tx_data(template, cmd_, feedback_, value_):
    """ build tx data including checksum specific to DFPlayer
        - template is fixed part of message with 0x00 for data
        - data is dictionary of data settings by index
        - checksum is 2's complement sum of bytes 1 to 6 inclusive """
    tx_ = template
    tx_[3] = cmd_
    tx_[4] = feedback_
    msb, lsb = slice_reg16(value_)
    tx_[5] = msb
    tx_[6] = lsb
    # get checksum bytes
    msb, lsb = slice_reg16(checksum(tx_[1:7]))
    tx_[7] = msb
    tx_[8] = lsb
    return tx_


def consume_rx_data(uart_):
    """"""
    rx_data = bytearray()
    while uart_.any() > 0:
        rx_data += uart_.read(1)
    return rx_data


def main():
    """"""

    fb = 1
    init_list = (
        [cmd['reset'], fb, 0],
        [cmd['vol_set'], fb, 10],
        [cmd['playback'], fb, 0],
        )
    play_list = (
        # [cmd['track'], fb, 0x00, 0x01],
        [cmd['next'], fb, 0],
        [cmd['next'], fb, 0],
        [cmd['next'], fb, 0],
        [cmd['next'], fb, 0],
        [cmd['next'], fb, 0],
        [cmd['reset'], fb, 0]
        )
    end_list = (
        [cmd['reset'], fb, 0]
        )
    for data in init_list:
        tx_data = build_tx_data(tx_template, *data)
        print('Tx: ', byte_array_str(tx_data))
        if check_checksum(tx_data[1:7], tx_data[7], tx_data[8]):
            print('Error in checksum')  # should return 0
        uart0.write(tx_data)
        sleep(1.0)
        # feedback = consume_rx_data(uart0)
    sleep(600)
    for data in play_list:
        tx_data = build_tx_data(tx_template, *data)
        print('Tx: ', tx_data)
        uart0.write(tx_data)
        sleep(60.0)
        # feedback = consume_rx_data(uart0)
        # print('Rx: ', feedback)
    for data in end_list:
        tx_data = build_tx_data(tx_template, *data)
        print('Tx: ', tx_data)
        uart0.write(tx_data)
        sleep(0.1)
        # feedback = consume_rx_data(uart0)


if __name__ == '__main__':
    main()

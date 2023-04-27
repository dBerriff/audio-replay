from machine import UART, Pin
from time import sleep

"""
    DFPlayer
    Communication format:
    00: start byte       0x7e
    01: version          0xff
    02: bytes following  0x06
    03: command
    04: command feedback 0x00 or 0x01
    05: parameter        msb
    06: parameter        lsb
    07: checksum         msb
    08: checksum         lsb
    09: end byte         0xef
"""

hex_str = ('0', '1', '2', '3', '4', '5', '6', '7', '8', '9',
           'a', 'b', 'c', 'd', 'e', 'f')


def byte_str(b):
    """ return str(hex value) of 8-bit byte """
    lsh = b & 0xf
    msh = b >> 4
    return '0x' + hex_str[msh] + hex_str[lsh]


def reg16_str(r):
    """ return str(hex value) of 16-bit register """
    lsb = r & 0xff
    msb = r >> 8
    return byte_str(msb) + byte_str(lsb)


def byte_array_str(ba):
    """ return str(hex value) of a bytearray """
    ba_str = ''
    for b in ba:
        ba_str += byte_str(b) + '\\'
    return ba_str[:-1]


def slice_reg16(value):
    """ slice 16-bit register into msb and lsb bytes """
    lsb = value & 0xff
    msb = value >> 8 & 0xff
    return msb, lsb    
    

class DFPController:
    """ control a DFPlayer over UART
        - byte/register/bytearray functions are called """

    baud_rate = 9600
    message_template = bytearray([0x7E, 0xFF, 0x06, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0xEF])
    # byte indices
    CMD = 3
    ACK = 4
    P_H = 5
    P_L = 6
    C_H = 7
    C_L = 8

    cmd_dict = {
        'next': 0x01,
        'prev': 0x02,
        'track': 0x03,  # 0-2999
        'vol_inc': 0x04,
        'vol_dec': 0x05,
        'vol_set': 0x06,  # 0-30
        'eq_set': 0x07,  # normal/pop/rock/jazz/classic/base
        'play_mode': 0x08,  # repeat/folder-repeat/single-repeat/random
        'play_src': 0x09,  # u/tf/aux/sleep/flash
        'standby': 0x0a,
        'normal': 0x0b,
        'reset': 0x0c,
        'playback': 0x0d,
        'pause': 0x0e,
        'folder': 0x0f,  # 1-10
        'vol_adj': 0x10,  # msb: enable: 1; lsb: gain: 0-31
        'repeat_play': 0x11  # 0: stop; 1: start
        }
    
    query_dict = {
        'send_init': 0x3f,
        're_tx': 0x40,
        'reply': 0x41,
        'status': 0x42,
        'vol': 0x43,
        'eq': 0x44,
        'mode': 0x45,
        'version': 0x46,
        'tf_files': 0x47,
        'ud_files': 0x48,
        'fl_files': 0x49,
        'keep_on': 0x4a,
        'tf_track': 0x4b,
        'ud_track': 0x4c,
        'fl_track': 0x4d
    }

    eq_dict = {
        'normal': 0,
        'pop': 1,
        'rock': 2,
        'jazz': 3,
        'classic': 4,
        'base': 5
    }

    mode_dict = {
        'repeat': 0,
        'folder_repeat': 1,
        'single_repeat': 2,
        'random': 3
    }

    source_dict = {
        'u': 1,
        'tf': 2,
        'aux': 3,
        'sleep': 4,
        'flash': 5
    }

    inv_query_dict = {
        0x3c: 'stay',
        0x3d: 'stay',
        0x3e: 'stay',
        0x3f: 'send_init',  # 0 - 0x0f: each bit: one device of low-4 bits???
        0x40: 're_tx',  # returns error; request re-Tx
        0x41: 'reply',
        0x42: 'status',
        0x43: 'vol',
        0x44: 'eq',
        0x45: 'pb_mode',
        0x46: 'sw_version',
        0x47: 'tf_files',
        0x48: 'ud_files',
        0x49: 'fl_files',
        0x4a: 'keep_on',
        0x4b: 'tf_track',
        0x4c: 'ud_track',
        0x4d: 'fl_track'
        }

    def __init__(self, pin_t: int, pin_r: int, fb: int = 1):
        self.uart = UART(0, baudrate=self.baud_rate, tx=Pin(pin_t), rx=Pin(pin_r))
        self.tx_array = bytearray(self.message_template)
        self.tx_array[self.ACK] = fb
        self.rx_tuple = None
        self._n_tracks = 11
        self.cmd = ''
        self.parameter = 0

    def build_tx_array(self):
        """ build tx data including checksum specific to DFPlayer
            - template is fixed part of message with 0x00 for data
            - data is dictionary of data settings by index
            - checksum is 2's complement sum of bytes 1 to 6 inclusive """
        if self.cmd in self.cmd_dict:
            self.tx_array[self.CMD] = self.cmd_dict[self.cmd]
        elif self.cmd in self.query_dict:
            self.tx_array[self.CMD] = self.query_dict[self.cmd]
        msb, lsb = slice_reg16(self.parameter)
        self.tx_array[self.P_H] = msb
        self.tx_array[self.P_L] = lsb
        self.set_checksum()

    def send_message(self, cmd: str, parameter: int):
        """ send UART control message """
        self.cmd = cmd
        self.parameter = parameter
        self.build_tx_array()
        self.uart.write(self.tx_array)

    def set_checksum(self):
        """ return the 2's complement checksum """
        c_sum = sum(self.tx_array[1:7])
        c_sum = -c_sum
        msb, lsb = slice_reg16(c_sum)
        self.tx_array[self.C_H] = msb
        self.tx_array[self.C_L] = lsb

    def alt_checksum(self):
        """ return the 2's complement checksum
            - alternative computation using byte inversion """
        c_sum = sum(self.tx_array[1:7])
        c_sum = ~c_sum + 1
        msb, lsb = slice_reg16(c_sum)
        self.tx_array[self.C_H] = msb
        self.tx_array[self.C_L] = lsb

    @staticmethod
    def check_checksum(ba):
        """ returns 0 for consistent checksum """
        b_sum = sum(ba[1:7])
        checksum_ = ba[7] << 8
        checksum_ += ba[8]
        return (b_sum + checksum_) & 0xffff

    def consume_rx_data(self):
        """"""
        sleep(1.0)
        rx_data = bytearray()
        while self.uart.any() > 0:
            rx_data += self.uart.read(1)
        # more than one Rx array? after init
        if len(rx_data) > 10: 
            rx1 = rx_data[:10]
            if rx1[3] == 0x41:  # reset gets extra 0x00 byte
                rx2 = rx_data[11:]
            else:
                rx2 = rx_data[10:]
        else:
            rx1 = rx_data
            rx2 = None
        if rx2:
            self.rx_tuple = (rx1, rx2)
        else:
            self.rx_tuple = (rx1,)
        self.print_rx_data()

    def dfp_init(self):
        """ """
        self.send_message('reset', 0)
        self.print_tx_data()
        self.consume_rx_data()

    def set_filecount(self):
        """ """
        self._n_tracks = 0

    @property
    def track_count(self):
        """"""
        return self._n_tracks
    
    def set_volume(self, level):
        """ """
        level = max(0, level)
        level = min(30, level)
        self.send_message('vol_set', level)
        self.consume_rx_data()
    
    def inc_volume(self):
        """ """
        self.send_message('vol_inc', 0)
        self.consume_rx_data()
    
    def dec_volume(self):
        """ """
        self.send_message('vol_dec', 0)
        self.consume_rx_data()
    
    def set_repeat_mode(self, mode):
        """ """
        
        self.consume_rx_data()
    
    def play_track(self, track_number):
        """"""
        track_number = max(0, track_number)
        track_number = track_number % self.track_count + 1
        self.send_message('track', track_number)
        self.print_tx_data()
        self.consume_rx_data()

    def print_tx_data(self):
        """ print transmitted bytearray """
        def friendly_string(ba_):
            """ print f description and parameters """
            f = self.cmd
            p = (ba_[5] << 8) + ba_[6]
            return f'{f}: {p}'

        # print('Tx:', byte_array_str(self.tx_array))
        print('Tx:', friendly_string(self.tx_array))

    def print_rx_data(self):
        """ print received bytearrays """
        
        def friendly_string(ba_):
            """ print f description and parameters """
            f = self.inv_query_dict[ba_[3]]
            p = (ba_[5] << 8) + ba_[6]
            return f'{f}: {p}'

        for ba in self.rx_tuple:
            # print('Rx:', byte_array_str(ba))
            if ba:
                print('Rx:', friendly_string(ba))


def main():
    """ test DFPlayer control """

    init_list = (
        ['vol_set', 5],
        ['ud_files', 0],
        ['repeat_play', 0]
        )
    end_list = (
        ['status', 0],
        ['reset', 0]
        )

    controller = DFPController(0, 1)
    sleep(1.5)
    controller.dfp_init()

    for data in init_list:
        controller.send_message(data[0], data[1])
        controller.print_tx_data()
        sleep(1.0)
        controller.consume_rx_data()
        controller.print_rx_data()
        print()
    sleep(3.0)

    for track in range(20):
        controller.play_track(track)
        sleep(2.0)
        print()

    for data in end_list:
        controller.send_message(*data)
        controller.print_tx_data()
        sleep(1.0)
        controller.consume_rx_data()
        controller.print_rx_data()
        print()


if __name__ == '__main__':
    main()

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


def set_reg16(msb, lsb):
    """ combine msb and lsb for 16-bit value """
    value = msb << 8
    value += lsb
    return value


class Flag:
    """ simple False/True flag """

    def __init__(self):
        self._set = False

    @property
    def is_set(self):
        return self._set

    @property
    def is_clear(self):
        return not self._set

    def set_on(self):
        """ set flag """
        self._set = True

    def set_off(self):
        """ clear flag """
        self._set = False
    

class DFPController:
    """ control a DFPlayer over UART
        - byte/register/bytearray functions are called """

    baud_rate = 9600
    message_template = bytearray([0x7E, 0xFF, 0x06, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0xEF])
    null_return = bytearray([0x00])
    # byte indices
    CMD = 3
    ACK = 4
    P_H = 5
    P_L = 6
    C_H = 7
    C_L = 8

    hex_cmd = {
        0x01: 'next',
        0x02: 'prev',
        0x03: 'track',  # 0-2999
        0x04: 'vol_inc',
        0x05: 'vol_dec',
        0x06: 'vol_set',  # 0-30
        0x07: 'eq_set',  # normal/pop/rock/jazz/classic/bass
        0x08: 'play_mode',  # repeat/folder-repeat/single-repeat/random
        0x09: 'play_src',  # u/tf/aux/sleep/flash
        0x0a: 'standby',
        0x0b: 'normal',
        0x0c: 'reset',
        0x0d: 'playback',
        0x0e: 'pause',
        0x0f: 'folder',  # 1-10
        0x10: 'vol_adj',  # msb: enable: 1; lsb: gain: 0-31
        0x11: 'repeat_play',  # 0: stop; 1: start
        0x3c: 'ud_finish',  # playback
        0x3d: 'tf_finish',  # playback
        0x3e: 'fl_finish',  # playback
        # init <param>: 01: U-disk, 02: TF-card, 04: PC, 08: Flash
        0x3f: 'q_init',
        0x40: 're_tx',
        0x41: 'reply',
        0x42: 'q_status',
        0x43: 'q_vol',
        0x44: 'q_eq',
        0x45: 'q_mode',
        0x46: 'q_version',
        0x47: 'q_tf_files',
        0x48: 'q_ud_files',
        0x49: 'q_fl_files',
        0x4a: 'keep_on',  # not understood
        0x4b: 'q_tf_track',
        0x4c: 'q_ud_track',
        0x4d: 'q_fl_track'
        }
    
    # inverse dictionary mapping
    cmd_hex = {value: key for key, value in hex_cmd.items()}

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

    def __init__(self, tx_pin: int, rx_pin: int, feedback: int = 1):
        self.uart = UART(0, baudrate=self.baud_rate, tx=Pin(tx_pin), rx=Pin(rx_pin))
        self.tx_array = bytearray(self.message_template)
        self.tx_array[self.ACK] = feedback
        self.rx_tuple = None
        self.cmd = ''
        self.cmd_param = 0
        self.init_param = 0
        self._n_tracks = 0
        self._current_track = 0
        self.play_flag = Flag()
        self.re_tx_flag = Flag()

    def __str__(self):
        string = f'DFPlayer: init param: {self.init_param}; '
        string += f'tracks: {self.track_count}; '
        string += f'current: {self.current_track}'
        return string

    def build_tx_array(self):
        """ build tx bytearray including checksum specific to DFPlayer
            - template includes unchanging bytes
            - checksum is 2's complement sum of bytes 1 to 6 inclusive """
        self.tx_array[self.CMD] = self.cmd
        msb, lsb = slice_reg16(self.cmd_param)
        self.tx_array[self.P_H] = msb
        self.tx_array[self.P_L] = lsb
        self.set_checksum()

    def send_message(self, cmd: int, parameter: int = 0, verbose: bool = True):
        """ send UART control message """
        self.cmd = cmd
        self.cmd_param = parameter
        self.build_tx_array()
        self.uart.write(self.tx_array)
        if verbose:
            self.print_tx_data()
        sleep(0.2)

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
    def check_checksum(ba: bytearray):
        """ returns 0 for consistent checksum """
        b_sum = sum(ba[1:7])
        checksum_ = ba[7] << 8  # msb
        checksum_ += ba[8]  # lsb
        return (b_sum + checksum_) & 0xffff

    @property
    def track_count(self):
        """"""
        return self._n_tracks

    @track_count.setter
    def track_count(self, n: int):
        self._n_tracks = n

    @property
    def current_track(self):
        return self._current_track

    @current_track.setter
    def current_track(self, n: int):
        self._current_track = n

    def play_next(self):
        """ play next track """
        self.send_message(0x01)
        self.play_flag.set_on()

    def play_prev(self):
        """ play next track """
        self.send_message(0x02)
        self.play_flag.set_on()

    def play_track(self, track_number: int):
        """ play track by number; 1-2999 (docs show 0-2999) """
        track_number = max(1, track_number)
        track_number = track_number % self.track_count + 1
        self.send_message(0x03, track_number)
        self.play_flag.set_on()

    def inc_volume(self):
        """ increase volume by one unit """
        self.send_message(0x04)
    
    def dec_volume(self):
        """ decrease volume by one unit """
        self.send_message(0x05)

    def set_volume(self, level: int):
        """ set volume in range 0-30  """
        level = max(0, level)
        level = min(30, level)
        self.send_message(0x06, level)

    def set_eq(self, mode: int):
        """ set eq type in range 0-5
            - normal, pop, rock, jazz, classic, bass """
        mode = max(0, mode)
        mode = min(5, mode)
        self.send_message(0x07, mode)

    def set_pb_mode(self, mode: int):
        """ set playback mode in range 0-3
            - repeat, folder_repeat, single_repeat, random """
        mode = max(0, mode)
        mode = min(3, mode)
        self.send_message(0x08, mode)

    def set_pb_source(self, source: int):
        """ set playback mode in range 0-4
            - U, TF, aux, sleep, flash """
        source = max(0, source)
        source = min(4, source)
        self.send_message(0x09, source)

    def standby(self):
        """ set to low-power standby """
        self.send_message(0x0a)
        self.play_flag.set_off()

    def normal(self):
        """ set to normal operation """
        self.send_message(0x0b)

    def reset(self):
        """ reset device
            - power-on requires 1.5 to 3.0 s
              so play safe """
        self.send_message(0x0c)
        self.current_track = 0
        sleep(3.0)

    def playback(self):
        """ start/resume playback """
        self.send_message(0x0d)
        self.play_flag.set_on()

    def pause(self):
        """ pause playback """
        self.send_message(0x0e)
        # self.play_flag.set_off()

    def set_folder(self, folder: int):
        """ set playback folder in range 1-10 """
        folder = max(1, folder)
        folder = min(10, folder)
        self.send_message(0x0f, folder)

    def vol_adjust_set(self, setting: int):
        """ set playback volume
            - not understood how different from 0x06!:
            - msb: 1 to open volume adjust
            - lsb: volume gain 0-31 """
        self.send_message(0x10, setting)

    def repeat_play(self, start: int):
        """ control repeat play
            - 0: stop; 1: start """
        self.send_message(0x11, start)
        if start == 1:
            self.play_flag.set_on()
        else:
            self.play_flag.set_off()

    def send_query(self, query: int, parameter=0):
        """ send query to device and pause for reply """
        sleep(0.5)
        self.send_message(query, parameter)
        sleep(0.5)

    def consume_rx_data(self):
        """ reads and prints received data """

        def print_rx_data():
            """ print received bytearrays """
            
            def friendly_string(ba_):
                """ print f description and parameters """
                f = self.hex_cmd[ba_[3]]
                p = (ba_[5] << 8) + ba_[6]
                return f'{f}: {p}'

            for ba in self.rx_tuple:
                # print('Rx:', byte_array_str(ba))
                if ba:
                    print('Rx:', friendly_string(ba))

        def parse_rx_data():
            """ parse incoming message parameters and
                set controller attributes
                - partial implementation for known requirements """
            for data in self.rx_tuple:
                if data[self.CMD] in (0x3c, 0x3d, 0x3e):
                    # finished playback of track <parameter>: see 3.3.2
                    self.play_flag.set_off()
                elif data[self.CMD] == 0x3f:
                    self.init_param = set_reg16(data[5], data[6])
                elif data[self.CMD] == 0x40:
                    # error; request retransmission
                    self.re_tx_flag.set_on()  # not currently checked
                elif data[self.CMD] == 0x48:
                    self.track_count = set_reg16(data[5], data[6])
                elif data[self.CMD] == 0x4c:
                    self.current_track = set_reg16(data[5], data[6])

        while True:
            sleep(0.1)
            rx_data = bytearray()
            while self.uart.any() > 0:
                rx_data += self.uart.read(1)
                sleep(0.002)  # approx for 9600 baud rate
            if rx_data and rx_data != self.null_return:
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
                parse_rx_data()
                print_rx_data()

    def print_tx_data(self):
        """ print transmitted bytearray """

        def friendly_string(ba_):
            """ print f description and parameters """
            f = self.hex_cmd[ba_[3]]
            p = (ba_[5] << 8) + ba_[6]
            return f'{f}: {p}'

        # print('Tx:', byte_array_str(self.tx_array))
        print('Tx:', friendly_string(self.tx_array))


def main():
    """ test DFPlayer control """

    # start up
    controller = DFPController(tx_pin=0, rx_pin=1, feedback=0)
    thread.start_new_thread(controller.consume_rx_data, ())
    controller.reset()
    controller.set_volume(5)
    # get (and set) number of U-Disk files
    controller.send_query(controller.cmd_hex['q_ud_files'])
    # start playback
    controller.playback()
    controller.send_query(controller.cmd_hex['q_ud_track'])
    print(controller)
    while controller.play_flag.is_set:
        sleep(1.0)
    controller.play_next()
    controller.send_query(controller.cmd_hex['q_ud_track'])
    print(controller)
    while controller.play_flag.is_set:
        sleep(1.0)
    # reset to close down
    controller.reset()
    sleep(2.0)
    print(controller)


if __name__ == '__main__':
    main()

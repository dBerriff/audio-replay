from machine import UART, Pin
from time import sleep, sleep_ms
import _thread as thread
import hex_fns as hex_f

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
    
    Player logic is at 3.3V
    Arduino requires 1k resistor -> player Rx
    
    hex_fns are mostly for print out of hex values
    without character substitutions

    See: https://github.com/jonnieZG/DFPlayerMini
    ref: ZG
    For Arduino but useful data acknowledged.
    Recommendation for gap-less play is that:
    - folders are not used
    - WAV files are used
    - copy files in required numbering order
    - remove WAV metadata
    - following formats work well:
      - MP3 44100 Hz, Mono, 32-bit float, VBR
      - WAV 44100 Hz, Mono, 16-bit
    Also, useful reference for timings
"""


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
        0x03: 'track',  # 0-2999 (? 1-2999)
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
        'bass': 5
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
        self.rx_b_array = None
        self.cmd = ''
        self.cmd_param = 0
        self.init_param = 0  # set at init; normally 2
        self._n_tracks = 0
        self._current_track = 0
        self.play_flag = Flag()
        self.re_tx_flag = Flag()  # re-Tx requested; not currently checked

    def __str__(self):
        string = f'DFPlayer: init param: {self.init_param}; '
        string += f'tracks: {self.track_count}; '
        string += f'current: {self.current_track}'
        return string

    def friendly_string(self, ba_: bytearray):
        """ return function name as str with parameters """
        f = self.hex_cmd[ba_[3]]
        p = (ba_[5] << 8) + ba_[6]
        return f'{f}: {p}'

    def set_m_parameter(self):
        """ set parameter msb and lsb bytes """
        msb, lsb = hex_f.slice_reg16(self.cmd_param)
        self.tx_array[self.P_H] = msb
        self.tx_array[self.P_L] = lsb

    def set_checksum(self):
        """ return the 2's complement checksum
            - bytes 1 to 6 """
        c_sum = sum(self.tx_array[1:7])
        c_sum = -c_sum
        # c_sum = ~c_sum + 1  # alternative calculation
        msb, lsb = hex_f.slice_reg16(c_sum)
        self.tx_array[self.C_H] = msb
        self.tx_array[self.C_L] = lsb

    def build_tx_array(self):
        """ insert tx bytearray attributes """
        self.tx_array[self.CMD] = self.cmd
        self.set_m_parameter()
        self.set_checksum()

    def send_message(self, cmd: int, parameter: int = 0, verbose: bool = False):
        """ send UART control message """
        self.cmd = cmd
        self.cmd_param = parameter
        self.build_tx_array()
        self.uart.write(self.tx_array)
        self.print_tx_data(verbose)
        sleep_ms(100)  # ZG min delay between commands

    def check_checksum(self, ba: bytearray):
        """ returns 0 for consistent checksum """
        b_sum = sum(ba[1:self.C_H])
        checksum_ = ba[self.C_H] << 8  # msb
        checksum_ += ba[self.C_L]  # lsb
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

    # DFPlayer commands

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
        sleep_ms(3000)  # ZG

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
        """ parses and prints received data
            - runs forever; intention: on RP2040 second core
            - uses polling as UART interrupts not supported (?)
        """

        def print_rx_data(verbose=False):
            """ print bytearray """
            if verbose:
                print('Rx:', hex_f.byte_array_str(self.rx_b_array))
                print(f'Rx: check checksum: {self.check_checksum(self.rx_b_array)}')
            print('Rx:', self.friendly_string(self.rx_b_array))

        def parse_rx_data():
            """ parse incoming message parameters and set controller attributes
                - partial implementation for known requirements """
            data = self.rx_b_array
            if data[self.CMD] in (0x3c, 0x3d, 0x3e):
                # playback of ud/tf/fl device track finished
                # parameter is track number: see doc 3.3.2
                self.play_flag.set_off()
            elif data[self.CMD] == 0x3f:  # q_init
                self.init_param = hex_f.set_reg16(data[5], data[6])
            elif data[self.CMD] == 0x40:  # re_tx
                self.re_tx_flag.set_on()  # not currently checked
            elif data[self.CMD] == 0x48:  # q_ud_files
                self.track_count = hex_f.set_reg16(data[5], data[6])
            elif data[self.CMD] == 0x4c:  # q_ud_track
                self.current_track = hex_f.set_reg16(data[5], data[6])

        while True:
            sleep_ms(20)  # wait for DFP response?
            rx_data = bytearray()
            if self.uart.any() > 0:
                rx_data += self.uart.read(10)
            if rx_data and rx_data != self.null_return:
                self.rx_b_array = rx_data
                parse_rx_data()
                print_rx_data()

    def print_tx_data(self, verbose=False):
        """ print transmitted bytearray """

        def friendly_string(ba_):
            """ print f description and parameters """
            f = self.hex_cmd[ba_[3]]
            p = (ba_[5] << 8) + ba_[6]
            return f'{f}: {p}'

        if verbose:
            print('Tx:', hex_f.byte_array_str(self.tx_array))
            print(f'Tx: check checksum: {self.check_checksum(self.tx_array)}')
        print('Tx:', friendly_string(self.tx_array))


def main():
    """ test DFPlayer control """
    
    """
        For continuous play see Doc 3.3.2 3.
        - this does not work as documented - just use next()!
    """

    # start up
    controller = DFPController(tx_pin=0, rx_pin=1, feedback=0)
    thread.start_new_thread(controller.consume_rx_data, ())
    controller.reset()
    controller.set_volume(5)
    # get (and set) number of U-Disk files
    controller.send_query(controller.cmd_hex['q_ud_files'])
    # start playback
    print(controller)
    controller.playback()
    controller.send_query(controller.cmd_hex['q_ud_track'])
    for i in range(12):
        while controller.play_flag.is_set:
            sleep_ms(100)
        sleep_ms(100)
        controller.play_next()
        controller.send_query(controller.cmd_hex['q_ud_track'])
    # reset to close down
    controller.reset()
    sleep(2.0)
    print(controller)


if __name__ == '__main__':
    main()

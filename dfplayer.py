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
    
    Player logic is 3.3V
    Arduino requires series 1k resistor -> player Rx
    
    hex functions include print out of hex values
    without character substitutions:
    - might not be necessary with hex in MP V1.20

    See: https://github.com/jonnieZG/DFPlayerMini
    ref: ZG
    For Arduino, but useful data acknowledged, especially for timings
    Recommendation for gap-less play is that:
    - folders are not used
    - WAV files are used
    - files are added to the SD card in required order
    - WAV metadata is removed
    - following formats are reported work well:
      - MP3 44100 Hz, Mono, 32-bit float, VBR
      - WAV 44100 Hz, Mono, 16-bit
"""


class DFPController:
    """ control a DFPlayer mini over UART """

    baud_rate = 9600  # no info on how to change player rate
    
    message_template = bytearray([0x7E, 0xFF, 0x06, 0x00, 0x00,
                                  0x00, 0x00, 0x00, 0x00, 0xEF])
    
    null_return = bytearray([0x00])
    
    # byte indices
    CMD = const(3)
    FBK = const(4)
    P_H = const(5)  # parameter
    P_L = const(6)
    C_H = const(7)  # checksum
    C_L = const(8)

    # DFPlayer commands: hex-to-text-name dictionary
    # names are for diagnostic printout
    hex_cmd = {
        0x01: 'next',
        0x02: 'prev',
        0x03: 'track',  # 0-2999 (? 1-2999)
        0x04: 'vol_inc',
        0x05: 'vol_dec',
        0x06: 'vol_set',  # 0-30
        0x07: 'eq_set',  # normal/pop/rock/jazz/classic/bass
        0x08: 'play_mode',  # repeat/folder-repeat/single-repeat/random
        0x09: 'play_src',  # u/tf/aux/sleep/flash 1/2/3/4/5
        0x0a: 'standby',
        0x0b: 'normal',
        0x0c: 'reset',
        0x0d: 'playback',
        0x0e: 'pause',
        0x0f: 'folder',  # 1-10
        0x10: 'vol_adj',  # msb: enable: 1; lsb: gain: 0-31
        0x11: 'repeat_play',  # 0: stop; 1: start
        0x3c: 'ud_finish',  # playback complete
        0x3d: 'tf_finish',
        0x3e: 'fl_finish',
        0x3f: 'q_init',  # 01: U-disk, 02: TF-card, 04: PC, 08: Flash
        0x40: 're_tx',
        0x41: 'reply',
        0x42: 'q_status',
        0x43: 'q_vol',
        0x44: 'q_eq',
        0x45: 'q_mode',
        0x46: 'q_version',
        0x47: 'q_ud_files',  # TF in doc!
        0x48: 'q_tf_files',  # UD in doc!
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

    def __init__(self, tx_pin: int, rx_pin: int, feedback: int = 1, verbose=False):
        self.uart = UART(0, baudrate=self.baud_rate, tx=Pin(tx_pin), rx=Pin(rx_pin))
        self.tx_array = bytearray(self.message_template)
        self.tx_array[self.FBK] = feedback
        self.verbose = verbose
        self.rx_b_array = None
        self.cmd = ''
        self.cmd_param = 0
        self.init_param = 0  # returned at player init; normally 2
        self.track_count = 0
        self.prev_track = 0
        self.play_flag = False
        self.re_tx_flag = False  # re-Tx requested; not currently checked

    def __str__(self):
        string = f'DFPlayer on: {self.uart} init param: {self.init_param}; '
        string += f'tracks: {self.track_count}'
        return string

    def hex_fn_string(self, ba_: bytearray):
        """ given player function as hex:
            - return str function name with parameter """
        f = self.hex_cmd[ba_[3]]
        p = (ba_[5] << 8) + ba_[6]
        return f'{f}: {p}'

    def set_parameter_reg16(self):
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
        self.set_parameter_reg16()
        self.set_checksum()

    def send_message(self, cmd: int, parameter: int = 0):
        """ send UART control message """
        self.cmd = cmd
        self.cmd_param = parameter
        self.build_tx_array()
        self.uart.write(self.tx_array)
        self.print_tx_data()
        sleep_ms(100)  # ZG min delay between commands

    def check_checksum(self, ba: bytearray):
        """ returns 0 for consistent checksum """
        b_sum = sum(ba[1:self.C_H])
        checksum_ = ba[self.C_H] << 8  # msb
        checksum_ += ba[self.C_L]  # lsb
        return (b_sum + checksum_) & 0xffff

    # DFPlayer commands

    def play_next(self):
        """ play next track """
        self.send_message(0x01)
        self.play_flag = True

    def play_prev(self):
        """ play next track """
        self.send_message(0x02)
        self.play_flag = True

    def play_track(self, track_number: int):
        """ play track by number; 1-2999 (docs show 0-2999) """
        track_number = max(1, track_number)
        track_number = track_number % self.track_count + 1
        self.send_message(0x03, track_number)
        self.play_flag = True

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
        self.play_flag = False

    def normal(self):
        """ set to normal operation """
        self.send_message(0x0b)

    def reset(self):
        """ reset device
            - power-on requires 1.5 to 3.0 s
              so play safe """
        self.send_message(0x0c)
        self.prev_track = 0
        sleep_ms(3000)  # ZG

    def playback(self):
        """ start/resume playback """
        self.send_message(0x0d)
        self.play_flag = True

    def pause(self):
        """ pause playback """
        self.send_message(0x0e)
        # self.play_flag.set_off()

    def set_folder(self, folder: int):
        """ set playback folder in range 1-10
            - for efficient playback do not use """
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
            self.play_flag = True
        else:
            self.play_flag = False

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

        def print_rx_message(message):
            """ print bytearray """
            if self.verbose:
                print('Rx:', hex_f.byte_array_str(message))
                checksum = self.check_checksum(message)
                if checksum:
                    print(f'Rx: checksum: {checksum}')
            print('Rx:', self.hex_fn_string(message))

        def parse_rx_message(message):
            """ parse incoming message parameters and set controller attributes
                - partial implementation for known requirements """
            if message[self.CMD] == 0x3d:
                # playback of TF track finished; see doc 3.3.2
                self.prev_track = hex_f.set_reg16(message[5], message[6])
                self.play_flag = False
            elif message[self.CMD] == 0x3f:  # q_init
                self.init_param = hex_f.set_reg16(message[5], message[6])
            elif message[self.CMD] == 0x40:  # re_tx
                self.re_tx_flag = True  # not currently checked
            elif message[self.CMD] == 0x43:  # re_tx
                self.volume = hex_f.set_reg16(message[5], message[6])
            elif message[self.CMD] == 0x48:  # q_ud_files
                self.track_count = hex_f.set_reg16(message[5], message[6])
            elif message[self.CMD] == 0x4c:  # q_ud_track
                self.current_track = hex_f.set_reg16(message[5], message[6])

        while True:
            # modify to use fixed bytearray and read into...
            sleep_ms(20)  # wait for DFP response?
            self.rx_b_array = bytearray()
            rx_data = self.rx_b_array
            if self.uart.any() > 0:
                rx_data += self.uart.read(10)
            if rx_data and rx_data != self.null_return:
                parse_rx_message(rx_data)
                print_rx_message(rx_data)

    def print_tx_data(self):
        """ print transmitted bytearray """

        def friendly_string(ba_):
            """ given hex command:
                - print text name and parameter """
            f = self.hex_cmd[ba_[3]]
            p = (ba_[5] << 8) + ba_[6]
            return f'{f}: {p}'

        message = self.tx_array
        if self.verbose:
            print('Tx:', hex_f.byte_array_str(message))
        print('Tx:', friendly_string(message))

    def dfp_init(self, vol):
        """ initialisation commands """
        self.reset()
        self.set_volume(vol)
        self.send_query(self.cmd_hex['q_tf_files'])


def main():
    """ test DFPlayer control """
    
    """
        Doc 3.3.2 3. does not work if 0x0d: 'playback' called.
        - different play mode required?
        - just use next() for now!
    """

    # start up
    controller = DFPController(tx_pin=0, rx_pin=1,
                               feedback=1, verbose=False)
    thread.start_new_thread(controller.consume_rx_data, ())
    controller.dfp_init(vol=10)
    print(controller)
    track = 1
    controller.playback()
    # play track 1
    while controller.play_flag:
        sleep_ms(10)
    sleep_ms(100)
    while track < controller.track_count:
        # play remaining tracks
        track += 1
        controller.play_next()
        while controller.play_flag:
            sleep_ms(10)
        sleep_ms(100)
    # reset before close down
    controller.reset()
    sleep(3.0)
    print(controller)


if __name__ == '__main__':
    main()

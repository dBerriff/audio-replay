from machine import UART, Pin
from time import sleep_ms
import _thread as thread
import hex_fns as hex_f


class UartTxRx(UART):
    """ UART transmit and receive through fixed-size buffers
        - UART0 maps to pins 0/1, 12/13, 16/17
        - UART1 maps to pins 4/5, 8/9
    """

    # buffer size and indices

    baud_rate = const(9600)
    
    def __init__(self, uart, tx_pin, rx_pin, buf_size):
        super().__init__(uart, self.baud_rate)
        self.init(tx=Pin(tx_pin), rx=Pin(rx_pin))
        self.buf_size = buf_size
        self.tx_buf = bytearray(buf_size)
        self.rx_buf = bytearray(buf_size)
        self.rx_flag = False

    def write_tx_data(self):
        """ write the Tx buffer to UART """
        self.write(self.tx_buf)

    def read_rx_data(self):
        """ read received data into Rx buffer """
        rx_bytes = self.readinto(self.rx_buf, self.buf_size)
        if rx_bytes == self.buf_size:
            self.rx_flag = True


class CommandHandler:
    """ formats, sends and receives command and query messages """

    BUF_SIZE = const(10)
    # data-byte indices
    CMD = const(3)
    P_H = const(5)  # parameter
    P_L = const(6)
    C_H = const(7)  # checksum
    C_L = const(8)

    R_FB = const(0)  # require player feedback? 0 or 1

    data_template = {0: 0x7E, 1: 0xFF, 2: 0x06, 4: R_FB, 9: 0xEF}
    
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
        # 0x3c: 'ud_finish',  # playback complete
        0x3d: 'tf_finish',
        # 0x3e: 'fl_finish',
        0x3f: 'q_init',  # 01: U-disk, 02: TF-card, 04: PC, 08: Flash
        0x40: 're_tx',
        0x41: 'reply',
        0x42: 'q_status',
        0x43: 'q_vol',
        0x44: 'q_eq',
        0x45: 'q_mode',
        0x46: 'q_version',
        # 0x47: 'q_ud_files',
        0x48: 'q_tf_files',
        # 0x49: 'q_fl_files',
        0x4a: 'keep_on',  # not understood
        # 0x4b: 'q_ud_track',
        0x4c: 'q_tf_track',
        # 0x4d: 'q_fl_track'
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
        # tf appears to be only valid source
        'u': 1,
        'tf': 2,
        'aux': 3,
        'sleep': 4,
        'flash': 5
    }

    def __init__(self, uart, tx_pin, rx_pin):
        self.uart_tr = UartTxRx(uart=uart, tx_pin=tx_pin, rx_pin=rx_pin,
                                buf_size=10)
        # pre-load template fixed values
        for key in self.data_template:
            self.uart_tr.tx_buf[key] = self.data_template[key]
        self.rx_fn = ''
        self.track_count = 0
        self.current_track = 0
        self.play_flag = False
        self.verbose = False
        self.tf_online = False

    def print_tx_message(self):
        """ print bytearray """
        message = self.uart_tr.tx_buf
        if self.verbose:
            print('Tx:', hex_f.byte_array_str(message))
        print('Tx:', self.hex_cmd[message[self.CMD]],
              hex_f.byte_str(message[self.P_H]),
              hex_f.byte_str(message[self.P_L]))

    def get_checksum(self):
        """ return the 2's complement checksum of:
            - bytes 1 to 6 """
        return hex_f.slice_reg16(-sum(self.uart_tr.tx_buf[1:7]))

    def check_checksum(self, buf_):
        """ returns 0 for consistent checksum """
        byte_sum = sum(buf_[1:self.C_H])
        checksum_ = buf_[self.C_H] << 8  # msb
        checksum_ += buf_[self.C_L]  # lsb
        return (byte_sum + checksum_) & 0xffff

    def send_command(self, cmd: str, param=0):
        """ set tx bytearray values and send """
        self.uart_tr.tx_buf[self.CMD] = self.cmd_hex[cmd]
        msb, lsb = hex_f.slice_reg16(param)
        self.uart_tr.tx_buf[self.P_H] = msb
        self.uart_tr.tx_buf[self.P_L] = lsb
        msb, lsb = self.get_checksum()
        self.uart_tr.tx_buf[self.C_H] = msb
        self.uart_tr.tx_buf[self.C_L] = lsb
        self.uart_tr.write_tx_data()
        self.print_tx_message()

    def send_query(self, query: str, parameter=0):
        """ send query to device and pause for reply """
        sleep_ms(500)
        self.send_command(query, parameter)
        sleep_ms(500)

    def consume_rx_data(self):
        """ parses and prints received data """

        def print_rx_message(message_):
            """ print bytearray """
            if self.verbose:
                print('Rx:', hex_f.byte_array_str(message_))
            print('Rx:', self.hex_cmd[message_[self.CMD]],
                  hex_f.byte_str(message_[self.P_H]),
                  hex_f.byte_str(message_[self.P_L]))

        def parse_rx_message(message_):
            """ parse incoming message parameters and set controller attributes
                - partial implementation for known requirements """
            rx_fn = self.hex_cmd[message_[self.CMD]]
            self.rx_fn = rx_fn

            if rx_fn == 'tf_finish':
                self.prev_track = hex_f.set_reg16(message_[self.P_H], message_[self.P_L])
                self.play_flag = False
            elif rx_fn == 'q_init':
                self.init_param = hex_f.set_reg16(message_[self.P_H], message_[self.P_L])
                self.tf_online = bool(self.init_param & 0x02)
            elif rx_fn == 're_tx':
                self.re_tx_flag = True  # not currently checked
            elif rx_fn == 'q_vol':
                self.volume = hex_f.set_reg16(message_[self.P_H], message_[self.P_L])
            elif rx_fn == 'q_tf_files':
                self.track_count = hex_f.set_reg16(message_[self.P_H], message_[self.P_L])
            elif rx_fn == 'q_tf_track':
                self.current_track = hex_f.set_reg16(message_[self.P_H], message_[self.P_L])

        while True:
            sleep_ms(200)
            self.uart_tr.read_rx_data()
            if self.uart_tr.rx_flag:
                self.uart_tr.rx_flag = False
                message = self.uart_tr.rx_buf
                parse_rx_message(message)
                print_rx_message(message)


class Controller:
    """ control DFPlayer"""

    def __init__(self, uart, tx_pin, rx_pin):
        self.cmd_handler = CommandHandler(uart=uart, tx_pin=tx_pin, rx_pin=rx_pin)
        self.track_count = 0
        self.prev_track = 0

    # DFPlayer commands

    def play_next(self):
        """ play next track """
        self.cmd_handler.send_command('next')
        self.cmd_handler.play_flag = True

    def play_prev(self):
        """ play next track """
        self.cmd_handler.send_command('prev')
        self.cmd_handler.play_flag = True

    def play_track(self, track_number: int):
        """ play track by number; 1-2999 (docs show 0-2999) """
        track_number = max(1, track_number)
        track_number = track_number % self.track_count + 1
        self.cmd_handler.send_command('track', track_number)
        self.cmd_handler.play_flag = True

    def inc_volume(self):
        """ increase volume by one unit """
        self.cmd_handler.send_command('vol_inc')
    
    def dec_volume(self):
        """ decrease volume by one unit """
        self.cmd_handler.send_command('vol_dec')

    def set_volume(self, level: int):
        """ set volume in range 0-30  """
        level = max(0, level)
        level = min(30, level)
        self.cmd_handler.send_command('vol_set', level)

    def set_eq(self, mode: int):
        """ set eq type in range 0-5
            - normal, pop, rock, jazz, classic, bass """
        mode = max(0, mode)
        mode = min(5, mode)
        self.cmd_handler.send_command('eq_set', mode)

    def set_pb_mode(self, mode: int):
        """ set playback mode in range 0-3
            - repeat, folder_repeat, single_repeat, random """
        mode = max(0, mode)
        mode = min(3, mode)
        self.cmd_handler.send_command('play_mode', mode)

    def set_pb_source(self, source: int):
        """ ignored?
            set playback mode in range 0-4
            - U, TF, aux, sleep, flash """
        source = max(0, source)
        source = min(4, source)
        self.cmd_handler.send_command('play_src', source)

    def standby(self):
        """ set to low-power standby """
        self.cmd_handler.send_command('standby')
        self.cmd_handler.play_flag = False

    def normal(self):
        """ set to normal operation (from standby?) """
        self.cmd_handler.send_command('normal')
        self.cmd_handler.play_flag = True

    def reset(self):
        """ reset device
            - power-on requires 1.5 to 3.0 s
              so play safe """
        self.cmd_handler.send_command('reset')
        self.prev_track = 0
        sleep_ms(3000)  # ZG

    def playback(self):
        """ start/resume playback """
        self.cmd_handler.send_command('playback')
        self.cmd_handler.play_flag = True

    def pause(self):
        """ pause playback """
        self.cmd_handler.send_command('pause')
        # self.play_flag.set_off()

    def set_folder(self, folder: int):
        """ set playback folder in range 1-10
            - for efficient playback do not use """
        folder = max(1, folder)
        folder = min(10, folder)
        self.cmd_handler.send_command('folder', folder)

    def vol_adjust_set(self, setting: int):
        """ set playback volume
            - not understood how different from 0x06!:
            - msb: 1 to open volume adjust
            - lsb: volume gain 0-31 """
        self.cmd_handler.send_command('vol_adj', setting)

    def repeat_play(self, start: int):
        """ control repeat play
            - 0: stop; 1: start """
        self.cmd_handler.send_command('repeat_play', start)
        if start == 1:
            self.cmd_handler.play_flag = True
        else:
            self.cmd_handler.play_flag = False

    # support methods
    
    def wait(self):
        """ wait for current track to complete """
        while self.cmd_handler.play_flag:
            sleep_ms(200)

    def dfp_init(self, vol):
        """ initialisation commands """
        self.reset()
        self.set_volume(vol)
        self.cmd_handler.send_query('q_tf_files')
        print(f'Track count: {self.cmd_handler.track_count}')
        sleep_ms(3000)


def main():
    """ test Controller, CommandHandler and UartTxRx """

    controller = Controller(uart=0, tx_pin=0, rx_pin=1)
    # run cmd_handler Rx on second core
    thread.start_new_thread(controller.cmd_handler.consume_rx_data, ())
    
    controller.dfp_init(vol=15)
    controller.playback()
    controller.wait()
    for i in range(controller.cmd_handler.track_count * 2):
        controller.play_next()
        controller.wait()
    
    thread.exit()


if __name__ == '__main__':
    main()

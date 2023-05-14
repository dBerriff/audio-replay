from machine import UART, Pin
from time import sleep_ms
import _thread as thread
import hex_fns as hex_f
from command_handler import UartTxRx, CommandHandler


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

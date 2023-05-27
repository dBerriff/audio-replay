from machine import UART, Pin
from time import sleep_ms
import _thread as thread
from command_handler import CommandHandler


class Controller:
    """ control DFPlayer"""

    def __init__(self, uart):
        self.cmd_handler = CommandHandler(uart)

    # DFPlayer commands

    def play_next(self):
        """ play next track """
        self.cmd_handler.send_command('next')
        self.cmd_handler.play_flag = True
        self.wait()

    def play_prev(self):
        """ play next track """
        self.cmd_handler.send_command('prev')
        self.cmd_handler.play_flag = True
        self.wait()

    def play_track(self, track_number: int):
        """ play track by number; 1-2999 (docs show 0-2999) """
        track_number = max(1, track_number)
        self.cmd_handler.send_command('track', track_number)
        self.cmd_handler.play_flag = True
        self.wait()

    def inc_volume(self):
        """ increase volume by one unit """
        self.cmd_handler.send_command('vol_inc')
        sleep_ms(200)
    
    def dec_volume(self):
        """ decrease volume by one unit """
        self.cmd_handler.send_command('vol_dec')
        sleep_ms(200)

    def set_volume(self, level: int):
        """ set volume in range 0-30  """
        level = max(0, level)
        level = min(30, level)
        self.cmd_handler.send_command('vol_set', level)
        sleep_ms(200)

    def set_eq(self, mode: int):
        """ set eq type in range 0-5
            - normal, pop, rock, jazz, classic, bass """
        mode = max(0, mode)
        mode = min(5, mode)
        self.cmd_handler.send_command('eq_set', mode)
        sleep_ms(200)

    def set_pb_mode(self, mode: int):
        """ set playback mode in range 0-3: errors?
            - called by repeat_play
            - ?repeat, folder_repeat, single_repeat, random?
            - 0: repeat tracks
            - 1: repeat tracks (in folder?)
        """
        mode = max(0, mode)
        mode = min(3, mode)
        self.cmd_handler.send_command('playback_mode', mode)
        sleep_ms(200)

    def standby(self):
        """ set to low-power standby """
        self.cmd_handler.send_command('standby')
        self.cmd_handler.play_flag = False
        sleep_ms(200)

    def normal(self):
        """ set to normal operation (from standby?) """
        self.cmd_handler.send_command('normal')
        self.cmd_handler.play_flag = True
        sleep_ms(200)

    def reset(self):
        """ reset device
            - power-on requires 1.5 to 3.0 s
              so play safe """
        self.cmd_handler.send_command('reset')
        self.cmd_handler.play_flag = False
        sleep_ms(3000)  # ZG

    def playback(self):
        """ start/resume playback """
        self.cmd_handler.send_command('playback')
        self.cmd_handler.play_flag = True
        self.wait()

    def pause(self):
        """ pause playback """
        self.cmd_handler.send_command('pause')
        sleep_ms(200)

    def set_folder(self, folder: int):
        """ set playback folder in range 1-10
            - for efficient playback do not use """
        folder = max(1, folder)
        folder = min(10, folder)
        self.cmd_handler.send_command('folder', folder)
        sleep_ms(200)

    def repeat_play(self):
        """ control repeat play:
            - start=0: stop - does not work!
            - start=1: starts repeat play
        """
        start = 1
        self.set_pb_mode(0)  # repeats root directory
        self.cmd_handler.send_command('repeat_play', start)
        self.cmd_handler.play_flag = True
        sleep_ms(200)

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
    
    uart = UART(0, 9600)
    uart.init(tx=Pin(0), rx=Pin(1))

    controller = Controller(uart)
    # run cmd_handler Rx on second core
    thread.start_new_thread(controller.cmd_handler.consume_rx_data, ())
    
    controller.dfp_init(vol=15)
    controller.set_eq(5)
    # controller.repeat_play()
    controller.playback()
    controller.wait()
    for i in range(5):
        controller.play_next()
        controller.wait()
    controller.pause()


if __name__ == '__main__':
    main()

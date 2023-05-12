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
        """ reads received data into Rx buffer
            - uses polling as UART interrupts not supported (?)
        """
        rx_data = self.rx_buf
        n_bytes = self.buf_size
        while True:
            sleep_ms(20)
            rx_bytes = self.readinto(rx_data, n_bytes)
            if rx_bytes == n_bytes:
                self.rx_flag = True


class CommandHandler:
    """ formats, sends and receives command messages """

    BUF_SIZE = const(10)
    CMD = const(3)
    FBK = const(4)
    P_H = const(5)  # parameter
    P_L = const(6)
    C_H = const(7)  # checksum
    C_L = const(8)
    feedback = 1

    message_template = bytearray([0x7E, 0xFF, 0x06, 0x00, 0x00,
                                  0x00, 0x00, 0x00, 0x00, 0xEF])

    def __init__(self, uart_tr):
        # UART0 maps to pins 0/1, 12/13, 16/17
        # UART1 maps to pins 4/5, 8/9
        self.uart_tr = uart_tr
        for i in range(len(self.message_template)):
            self.uart_tr.tx_buf[i] = self.message_template[i]

    def print_rx_buf(self):
        """ print bytearray """
        print('Rx:', hex_f.byte_array_str(self.uart_tr.rx_buf))

    def print_tx_buf(self):
        """ print bytearray """
        print('Tx:', hex_f.byte_array_str(self.uart_tr.tx_buf))

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

    def send_command(self, cmd, param=0):
        """ set tx bytearray values and send """
        self.uart_tr.tx_buf[self.CMD] = cmd
        self.uart_tr.tx_buf[self.FBK] = self.feedback
        msb, lsb = hex_f.slice_reg16(param)
        self.uart_tr.tx_buf[self.P_H] = msb
        self.uart_tr.tx_buf[self.P_L] = lsb
        msb, lsb = self.get_checksum()
        self.uart_tr.tx_buf[self.C_H] = msb
        self.uart_tr.tx_buf[self.C_L] = lsb
        self.uart_tr.write_tx_data()


class DFPController:
    """
        Control a DFPlayer over UART

        DFPlayer
        Communication format:
        00: start byte       0x7e
        01: version          0xff
        02: bytes following  0x06
        03: command
        04: feedback         0x00 or 0x01
        05: parameter        msb
        06: parameter        lsb
        07: checksum         msb
        08: checksum         lsb
        09: end byte         0xef

        Player logic is 3.3V
        Arduino requires series 1k resistor -> player Rx

        hex functions include printout of hex values
        without character substitutions:
        - might not be necessary with hex in MP V1.20

        See: https://github.com/jonnieZG/DFPlayerMini
        For gap-less play:
        - do not use folders
        - use WAV files
        - add files to the SD card in required order
        - remove WAV metadata
        - following formats are reported to work well:
          - MP3 44100 Hz, Mono, 32-bit float, VBR
          - WAV 44100 Hz, Mono, 16-bit
    """
    def __init__(self):
        pass


def main():
    """ test DFPlayer control """

    controller = CommandHandler(
        UartTxRx(uart=0, tx_pin=0, rx_pin=1, buf_size=10))

    # run UART Rx on second core
    thread.start_new_thread(controller.uart_tr.read_rx_data, ())

    
    for i in range(10):
        controller.send_command(i, i * 10)
        controller.print_tx_buf()
        sleep_ms(200)
        if controller.uart_tr.rx_flag:
            controller.print_rx_buf()
            controller.rx_flag = False
            print()
        sleep_ms(2000)
    
    thread.exit()


if __name__ == '__main__':
    main()

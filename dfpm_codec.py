# dfpm_codec.py

import struct


class MiniCmdPackUnpack:
    """ DFPlayer mini command pack/unpack: command values <-> message bytes
        - unsigned integers: B: 1 byte; H: 2 bytes
          command: start-B, ver-B, len-B, cmd-B, fb-B, param-H, csum-H, end-B
    """
    CMD_TEMPLATE = (0x7E, 0xFF, 0x06, 0x00, 0x01, 0x0000, 0x0000, 0xEF)
    CMD_FORMAT = const('>BBBBBHHB')  # > big-endian
    # command indices
    CMD_I = const(3)
    PRM_I = const(5)
    CSM_I = const(6)
    # message indices
    CSM_M = const(7)
    CSM_L = const(8)

    @classmethod
    def check_checksum(cls, bytes_):
        """ returns True if checksum is valid """
        checksum = sum(bytes_[1:cls.CSM_M])
        checksum += (bytes_[cls.CSM_M] << 8) + bytes_[cls.CSM_L]
        return checksum & 0xffff == 0

    def __init__(self):
        self.tx_message = list(MiniCmdPackUnpack.CMD_TEMPLATE)

    def pack_tx_ba(self, command, parameter):
        """ pack Tx DFPlayer mini command """
        self.tx_message[self.CMD_I] = command
        self.tx_message[self.PRM_I] = parameter
        bytes_ = struct.pack(self.CMD_FORMAT, *self.tx_message)
        # compute checksum
        self.tx_message[self.CSM_I] = -sum(bytes_[1:self.CSM_M]) & 0xffff
        return struct.pack(self.CMD_FORMAT, *self.tx_message)

    def unpack_rx_ba(self, bytes_):
        """ unpack Rx DFPlayer mini command """
        if self.check_checksum(bytes_):
            rx_msg = struct.unpack(self.CMD_FORMAT, bytes_)
            cmd_ = rx_msg[self.CMD_I]
            param_ = rx_msg[self.PRM_I]
        else:
            print('Error in checksum')
            cmd_ = 0
            param_ = 0
        return cmd_, param_

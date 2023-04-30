# hex_fns.py
""" support-functions for processing and printing hexadecimal values
	- print hex values without character substitutions """

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
    return value & 0xffff

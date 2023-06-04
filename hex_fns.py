# hex_fns.py
""" support-functions for processing and printing hexadecimal values
    - print hex values without character substitutions """

hex_digit = ('0', '1', '2', '3', '4', '5', '6', '7', '8', '9',
             'a', 'b', 'c', 'd', 'e', 'f')


def byte_digits(b):
    """ return 8-bit value as hex str """
    lsh = b & 0xf
    msh = b >> 4 & 0xf
    return hex_digit[msh] + hex_digit[lsh]

def byte_str(b):
    """ returns 8-bit hex str preceded by '0x' """
    return '0x' + byte_digits(b)
    
def slice_reg16(value):
    """ slice 16-bit register into msb and lsb bytes """
    lsb = value & 0xff
    msb = value >> 8 & 0xff
    return msb, lsb

def reg16_str(r):
    """ return 16-bit value as hex str """
    msb, lsb = slice_reg16(r)
    return '0x' + byte_digits(msb) + byte_digits(lsb)

def m_l_reg16(msb, lsb):
    """ combine msb and lsb for 16-bit value """
    value = msb << 8
    value += lsb
    return value & 0xffff

def m_l_reg16_str(msb, lsb):
    return reg16_str(m_l_reg16(msb, lsb))

def byte_array_str(ba):
    """ return str(hex value) of a bytearray """
    ba_str = ''
    for b in ba:
        ba_str += byte_str(b) + '\\'
    return ba_str[:-1]


def main():
    """ test hex function """
    for i in range(1024):
        print(i, hex(i), byte_digits(i), byte_str(i), reg16_str(i))


if __name__ == '__main__':
    main()

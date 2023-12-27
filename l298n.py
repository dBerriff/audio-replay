# l298n.py
""" model L298N motor controller """

from machine import Pin, PWM
from micropython import const
from collections import namedtuple


class L298nChannel:
    """ L298N H-bridge channel
        - states: 'F': forward, 'R': reverse, 'S': stopped
        - frequency and duty cycle: no range checking
        - if using Pi Pico, 2 PWM "slice" channels share the same frequency
        -- slices are pins (0 and 1), (2 and 3), ...
    """

    U16 = const(0xffff)  # 16-bit-register control

    def __init__(self, pwm_pin, motor_pins_, frequency):
        self.enable = PWM(Pin(pwm_pin))  # L298N pins are labelled 'EN'
        self.sw_1 = Pin(motor_pins_[0], Pin.OUT)
        self.sw_2 = Pin(motor_pins_[1], Pin.OUT)
        self.set_freq(frequency)
        self.set_dc_u16(0)
        self.state = None
        self.set_state('S')

    def set_freq(self, frequency):
        """ set pulse frequency within limits """
        self.enable.freq(frequency)

    def set_dc_u16(self, dc_u16):
        """ set duty cycle by 16-bit integer """
        self.enable.duty_u16(dc_u16)

    def set_state(self, state):
        """ set H-bridge switch states """
        if state == 'F':
            self.state = 'F'
            self.sw_1.value(1)
            self.sw_2.value(0)
        elif state == 'R':
            self.state = 'R'
            self.sw_1.value(0)
            self.sw_2.value(1)
        elif state == 'S':
            self.state = 'S'
            self.sw_1.value(1)
            self.sw_2.value(1)

    def set_logic_off(self):
        """ set all logic output off """
        self.set_dc_u16(0)
        self.sw_1.value(0)
        self.sw_2.value(0)
        self.state = 'S'


class L298N:
    """ control a generic L298N H-bridge board
        - 2 channels labelled A and B
        - EN inputs (PWM) are labelled: ENA and ENB
        - bridge-switch setting inputs are labelled (IN1, IN2) and (IN3, IN4)
        - connections: Pico GPIO => L298N
        -- pwm_pins => (ENA, ENB)
        -- sw_pins  => (IN1, IN2, IN3, IN4)
    """

    Speed = namedtuple('Speed', ['f', 'r'])  # forward, reverse percentages


    def __init__(self, pwm_pins_, sw_pins_, f):
        # channel A: PWM input to ENA; bridge-switching inputs to IN1 and IN2
        self.channel_a = L298nChannel(
            pwm_pins_[0], (sw_pins_[0], sw_pins_[1]), f)
        # channel B: PWM input to ENB; bridge-switching inputs to IN3 and IN4
        self.channel_b = L298nChannel(
            pwm_pins_[1], (sw_pins_[2], sw_pins_[3]), f)
        print(f'L298N initialised: {pwm_pins_}; {sw_pins_}; {self.channel_a.enable.freq()}')
        self.channel_state = None

    async def run_channels(self):
        """ run channels between 2 states """
        motor_a_speed = Motor.Speed(f=75, r=50)
        motor_b_speed = Motor.Speed(f=75, r=50)

        if self.channel_state == 0:
            # A forward and B reverse
            self.channel_a.state = 'R'
            self.channel_b.state = 'F'
            await asyncio.gather(
                self.channel_a.accel(motor_a_speed.r),
                self.channel_b.accel(motor_b_speed.f))
            self.channel_state = 1
        else:
            self.channel_a.state = 'F'
            self.channel_b.state = 'R'
            await asyncio.gather(
                self.channel_a.accel(motor_a_speed.f),
                self.channel_b.accel(motor_b_speed.r))
            self.channel_state = 0

        # free-run period
        await asyncio.sleep_ms(10_000)
        await asyncio.gather(
            self.channel_a.decel(),
            self.channel_b.decel())
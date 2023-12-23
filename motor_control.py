# motor_control.py
""" run dc motor(s) under PWM control """
import asyncio
from machine import Pin, PWM   
from time import sleep


class L298nChannel:
    """ L298N H-bridge channel
        - states: 'F': forward, 'R': reverse, 'S': stop
    """

    def __init__(self, pwm_pin, motor_pins_, frequency, name=''):
        self.enable = PWM(Pin(pwm_pin))
        self.sw_1 = Pin(motor_pins_[0], Pin.OUT)
        self.sw_2 = Pin(motor_pins_[1], Pin.OUT)
        self.set_freq(frequency)
        self.name = name
        self.state = None
        self.dc_u16 = 0
        self.set_state('S')

    def set_freq(self, frequency):
        """ set pulse frequency """
        if 500 < frequency <= 1500:
            self.enable.freq(frequency)
        else:
            self.enable.freq(500)

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
        else:  # stop!
            self.state = 'S'
            self.sw_1.value(1)
            self.sw_2.value(1)

    def set_dc_percent(self, percent):
        """ set duty cycle by percent """
        percent = max(0, percent)
        percent = min(100, percent)
        self.dc_u16 = 0xffff * percent // 100
        self.enable.duty_u16(self.dc_u16)

    def set_logic_off(self):
        """ set all logic output off """
        self.set_dc_percent(0)
        self.sw_1.value(0)
        self.sw_2.value(0)
        self.state = 'S'


class L298N:
    """ control a generic L298N H-bridge board
    """

    def __init__(self, pwm_pins_, motor_pins_, frequency):
        print('Initialise L298N')
        print(f'Channel A pins: {pwm_pins_[0]}, ({motor_pins_[0]}, {motor_pins_[1]})')
        self.channel_a = L298nChannel(
            pwm_pins_[0], (motor_pins_[0], motor_pins_[1]), frequency, 'A')
        print(f'Channel B pins: {pwm_pins_[1]}, ({motor_pins_[2]}, {motor_pins_[3]})')
        self.channel_b = L298nChannel(
            pwm_pins_[1], (motor_pins_[2], motor_pins_[3]), frequency, 'B')

    
class Motor:
    """ control speed and direction of dc motor """
    
    def __init__(self, channel, name):
        self.channel = channel
        self.name = name

    def rotate(self, direction, percent):
        """ set to direction at percent duty cycle """
        self.channel.set_state(direction)
        self.channel.set_dc_percent(percent)

    def run(self, direction, percent):
        """ run the motor in the set direction at percent duty-cycle """
        print(f'Run motor {self.name} {direction} {percent}')
        # avoid instant change of direction
        if direction != self.channel.direction and self.channel.dc_pc > 0:
            self.rotate(self.channel.direction, 0)
            sleep(0.5)
        self.rotate(direction, percent)

    def stop(self):
        """ stop the motor """
        self.rotate('S', 0)

pwm_pins = (2, 3)
motor_pins = (4, 5, 6, 7)
f = 500
controller = L298N(pwm_pins, motor_pins, f)
motor_a = Motor(controller.channel_a, 'A')
motor_b = Motor(controller.channel_b, 'B')
sleep(2)
motor_a.run('F', 50)    
sleep(5)
motor_a.run('R', 25)  
sleep(5)
motor_a.stop()
motor_b.run('R', 50)  
sleep(5)
motor_b.run('F', 25)
sleep(5)
motor_b.stop()
motor_a.channel.set_logic_off()
motor_b.channel.set_logic_off()


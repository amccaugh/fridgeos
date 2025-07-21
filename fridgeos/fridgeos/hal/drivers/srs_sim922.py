import serial
import numpy as np

class SIM922:
    """Python class for SRS SIM922 quad thermometer inside a SIM900
    mainframe, written by Adam McCaughan"""
    def __init__(self, serial_address, sim900port, channel):
        self.serial = serial.Serial(serial_address, timeout = 1, baudrate = 115200)
        self.sim900port = sim900port
        self.channel = channel
        self.serial.send_break()

    def read(self):
        return self.serial.readline().strip().decode('utf-8')

    def write(self, string):
        write_string = string + '\r\n'
        self.serial.write(write_string.encode('utf-8'))

    def query(self, string):
        self.write(string)
        return self.read()

    def reset(self):
        self.write_simport('*RST')

    def identify(self):
        return self.query_simport('*IDN?')

    def close(self):
        return self.serial.close()

    def write_simport(self, message):
        self.write('CONN %d,"xyz"' % self.sim900port)
        self.write(message)
        self.write('xyz')

    def read_simport(self):
        self.write('CONN %d,"xyz"' % self.sim900port)
        data = self.read()
        self.write('xyz')
        return data

    def query_simport(self, message):
        self.write('CONN %d,"xyz"' % self.sim900port)
        reply = self.query(message)
        self.write('xyz')
        return reply

    def read_temperature(self):
        # In a string, %0.4e converts a number to scientific notation
        self.write('CONN %d,"xyz"' % self.sim900port)
        v = float(self.query('TVAL? %s' % self.channel))
        self.write('xyz')
        return v

# s = SIM922('/dev/ttyUSB0', 1)
# print(s.identify())
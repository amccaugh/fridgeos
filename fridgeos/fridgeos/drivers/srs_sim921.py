import serial
import numpy as np

class SIM921:
    """Python class for SRS SIM921 AC resistance bridge inside a SIM900
    mainframe, written by Adam McCaughan"""
    def __init__(self, serial_address, sim900port):
        self.serial = serial.Serial(serial_address, timeout = 1, baudrate = 115200)
        self.sim900port = sim900port
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

    def read_resistance(self):
        R = float(self.query_simport('RVAL?'))
        return R

    def read_temperature(self):
        T = float(self.query_simport('TVAL?'))
        return T

    def set_range(self, max_resistance = 200):
        range_code = np.ceil(np.log10(max_resistance/(20e-3)))
        range_code = int(range_code)
        self.write_simport('RANG %s' % range_code)

    def set_excitation(self, voltage = 10e-6):
        valid_voltages = [3e-6, 10e-6, 30e-6, 100e-6, 300e-6, 1e-3, 3e-3, 10e-3, 30e-3]
        if voltage not in valid_voltages:
            raise ValueError('Excitation voltage must be in [3e-6, 10e-6, 30e-6, 100e-6, 300e-6, 1e-3, 3e-3, 10e-3, 30e-3]')
        excitation_code = np.where(voltage == np.array(valid_voltages))[0][0]
        self.write_simport('EXCI %s' % excitation_code)

    def set_time_constant(self, time_constant = 1):
        valid_tc = [0.3, 1, 3, 10, 30, 100, 300]
        if time_constant not in valid_tc:
            raise ValueError('Time constant must be in [0.3, 1, 3, 10, 30, 100, 300]')
        time_constant_code = np.where(time_constant == np.array(valid_tc))[0][0]
        self.write_simport('TCON %s' % time_constant_code)

# s = SIM921('/dev/ttyUSB0', 2)
# print(s.identify())
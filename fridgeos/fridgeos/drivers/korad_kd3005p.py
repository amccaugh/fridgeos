import serial

class KD3005P(object):
    """Python class for KORAD KD3005P single channel programmable power supply.
    Rated for 30V @ 5A. """
    #Site: https://www.koradtechnology.com/product/84.html
    #Program Manual: https://www.sra-shops.com/pub/media/docs/srasolder/instructions/kd3005p-user-manual.pdf
    
    
    def __init__(self, serial_address):
        self.serial = serial.Serial(serial_address, timeout = 1, baudrate = 9600)

    def read(self):
        return self.serial.readline().strip().decode('utf-8')

    def write(self, string):
        write_string = string + '\n'
        self.serial.write(write_string.encode('utf-8'))

    def query(self, string):
        self.write(string)
        return self.read()

    def reset(self):
        self.write('*RST')

    def identify(self):
        return self.write('*IDN?')

    def close(self):
        return self.serial.close()
    

    def set_current(self, amps, channel = 1):
        #Sets output current. Input must be an int or a float
        msg = f'ISET{channel}:{amps}'
        self.write(msg)
            
    def set_voltage(self, volts, channel = 1):
        #Sets output voltage. Input must be an int or a float
        self.write(f'VSET{channel}:{volts}')
            
    def read_current_setting(self, channel = 1):
        #Returns the output current setting
        current = self.query(f'ISET{channel}?')
        return float(current)
    
    def read_voltage_setting(self, channel = 1):
        #Returns the output current setting
        voltage = self.query(f'VSET{channel}?')
        return float(voltage)
    
    def read_current(self, channel = 1):
        #Returns actual output current
        current = self.query(f'IOUT{channel}?')
        return float(current)

    def read_voltage(self, channel = 1):
        #Returns actual output voltage
        voltage = self.query(f'VOUT{channel}?')
        return float(voltage)


# p = KD3005P('/dev/ttyACM0')
# print(p.read_current())
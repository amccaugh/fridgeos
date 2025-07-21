import numpy as np
import time

class DummyHeater():
    def __init__(self, address):
        self.address = address
        self.voltage = 0

    def set_voltage(self, voltage):
        self.voltage = voltage
        print(f'Dummy heater at address {self.address} voltage now {voltage}')

    def get_voltage(self):
        return self.voltage

    def get_current(self):
        return round(time.time() % 10, 2)
    

class DummyThermometer():
    def __init__(self, address):
        self.address = address

    def read_temperature(self):
        return round(time.time() % 2, 2) + np.random.randn()*0.1
    
    
class DummyRelay():
    def __init__(self, address):
        self.address = address
        self.state = False

    def set_state(self, state):
        self.state = state
        print(f'Dummy relay at address {self.address} state now {state}')
    
    def get_state(self):
        return self.state
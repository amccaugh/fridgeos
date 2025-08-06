# All classes in this file are thin wrappers for the main driver classes in the other files
# that allow the HAL to interact with the classes in a consistent way.

# Each thermometer class must implement the following methods:
    # setup(...)
    # get_temperature()
# And each heater class must implement the following methods:
    # setup(...)
    # set_heater_value(value)
    # get_heater_value()
# If you add a new driver, make sure to add it to the hal_classes dictionary at the bottom of this file.

from fridgeos.drivers.korad_kd3005p import KD3005P
from fridgeos.drivers.srs_sim921 import SIM921
from fridgeos.drivers.srs_sim922 import SIM922
from fridgeos.drivers.swarm import SwarmLockin, SwarmDiode, SwarmHighPowerHeater, SwarmLowPowerHeater, WarmupHeater
from fridgeos.drivers.dummy import DummyThermometer, DummyHeater
import random
import time

### HEATERS

class HAL_KD3005P():
    def setup(self, address):
        self.heater = KD3005P(address)
    
    def set_heater_value(self, value):
        self.heater.set_voltage(value)
    
    def get_heater_value(self):
        return self.heater.read_voltage()
    
class HAL_SwarmHighPowerHeater():
    def setup(self, address, mux_name = None):
        self.heater = SwarmHighPowerHeater(address, mux_name)

    def set_heater_value(self, value):
        self.heater.set_pump_current(value)

    def get_heater_value(self):
        return self.heater.get_pump_measurement().get('v')
    
class HAL_SwarmLowPowerHeater():
    def setup(self, address, mux_name):
        self.heater = SwarmLowPowerHeater(address, mux_name)

    def set_heater_value(self, value):
        self.heater.set_heat_switch_voltage(value)

    def set_heater_enable(self, enable):
        self.heater.set_heat_switch_enable(enable)

    def get_heater_enable(self):
        return self.heater.get_heat_switch_enable()
    
    def get_heater_value(self):
        return self.heater.get_heat_switch_voltage()

class HAL_DummyHeater():
    def setup(self, address):
        self.heater = DummyHeater(address)
    
    def set_heater_value(self, value):
        self.heater.set_voltage(value)
    
    def get_heater_value(self):
        return self.heater.get_voltage()


class HAL_FaultyDummyHeater():
    def setup(self, address):
        self.heater = DummyHeater(address)
    
    def set_heater_value(self, value):
        if random.random() < 0.1:
            raise Exception("Faulty heater")
        self.heater.set_voltage(value)
    
    def get_heater_value(self):
        return self.heater.get_voltage()


### THERMOMETERS 

class HAL_SIM921():
    def setup(self, address, slot):
        self.thermometer = SIM921(address, sim900port=slot)
    
    def get_temperature(self):
        return self.thermometer.read_temperature()
    
class HAL_SIM922():
    def setup(self, address, slot, channel):
        self.thermometer = SIM922(address, sim900port=slot, channel=channel)
    
    def get_temperature(self):
        return self.thermometer.read_temperature()
    
class HAL_SwarmLockin():
    def setup(self, address, calibration_file = None, mux_name = None, mux = False):
        self.thermometer = SwarmLockin(address, calibration_file, mux_name, mux)

    def get_temperature(self):
        return self.thermometer.read_temp()
    
class HAL_SwarmDiode():
    def setup(self, address, calibration_file = None, mux_name = None):
        self.thermometer = SwarmDiode(address, calibration_file, mux_name)

    def get_temperature(self):
        return self.thermometer.read_temp()

class HAL_DummyThermometer():
    def setup(self, address):
        self.thermometer = DummyThermometer(address)
    
    def get_temperature(self):
        return self.thermometer.read_temperature()

class HAL_FaultyDummyThermometer():
    def setup(self, address):
        self.thermometer = DummyThermometer(address)
    
    def get_temperature(self):
        if random.random() < 0.1:
            raise Exception("Faulty thermometer")
        else:
            return 5 + random.random()*0.1



class HAL_LaggyDummyThermometer():
    def setup(self, address):
        self.thermometer = DummyThermometer(address)
    
    def get_temperature(self):
        time.sleep(7)
        return 7 + random.random()*0.1

hal_classes = {
    'korad-kd3005p': HAL_KD3005P,
    'srs-sim921': HAL_SIM921,
    'srs-sim922': HAL_SIM922,
    'swarm_lockin': HAL_SwarmLockin,
    'swarm_diode': HAL_SwarmDiode,
    'swarm_hph': HAL_SwarmHighPowerHeater,
    'swarm_lph': HAL_SwarmLowPowerHeater,
    'DummyThermometer': HAL_DummyThermometer,
    'DummyHeater': HAL_DummyHeater,
    'FaultyDummyHeater': HAL_FaultyDummyHeater,
    'FaultyDummyThermometer': HAL_FaultyDummyThermometer,
    'LaggyDummyThermometer': HAL_LaggyDummyThermometer,
}
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

from fridgeos.hal.drivers.korad_kd3005p import KD3005P
from fridgeos.hal.drivers.srs_sim921 import SIM921
from fridgeos.hal.drivers.srs_sim922 import SIM922
from fridgeos.hal.drivers.swarm import Lockin, Diode, PumpHeater, HeatSwitch, WarmupHeater

### HEATERS

class HAL_KD3005P():
    def setup(self, address):
        self.heater = KD3005P(address)
    
    def set_heater_value(self, value):
        self.heater.set_voltage(value)
    
    def get_heater_value(self):
        return self.heater.read_voltage()
    
class SWARM_HPH():
    def setup(self, address, mux_name = None):
        self.heater = PumpHeater(address, mux_name)

    def set_heater_value(self, value):
        self.heater.set_pump_current(value)

    def get_heater_value(self):
        return self.heater.get_pump_measurement()
    
class SWARM_LPH():
    def setup(self, address, mux_name):
        self.heater = HeatSwitch(address, mux_name)

    def set_heater_value(self, value):
        self.heater.set_heat_switch_voltage(value)

    def set_heater_enable(self, enable):
        self.heater.set_heat_switch_enable(enable)

    def get_heater_enable(self):
        return self.heater.get_heat_switch_enable()
    
    def get_heater_value(self):
        return self.heater.get_heat_switch_voltage()


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
    
class SWARM_LOCKIN():
    def setup(self, address, calibration_file = None, mux_name = None, mux = False):
        self.thermometer = Lockin(address, calibration_file, mux_name, mux)

    def get_temperature(self):
        return self.thermometer.read_temp()
    
class SWARM_DIODE():
    def setup(self, address, calibration_file = None, mux_name = None):
        self.thermometer = Diode(address, calibration_file, mux_name)

    def get_temperature(self):
        return self.thermometer.read_temp()


hal_classes = {
    'korad-kd3005p': HAL_KD3005P,
    'srs-sim921': HAL_SIM921,
    'srs-sim922': HAL_SIM922,
    'swarm_lockin': SWARM_LOCKIN,
    'swarm_diode': SWARM_DIODE,
    'swarm_hph': SWARM_HPH,
    'swarm_lph': SWARM_LPH
}
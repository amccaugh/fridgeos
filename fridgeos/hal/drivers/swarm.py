#%%
import numpy as np
from serial import Serial
import json

class Lockin():
    def __init__(self, address, calibration_file = None, name = None, mux = False):
        try:
            self.serial = Serial(address)
            self.serial.close()
        except Exception as e:
            print(e)
            pass
        if calibration_file != None:
            self.calibration_array = np.loadtxt(calibration_file, delimiter =',')
        else:
            self.calibration_array = None
        self.name = name
        self.mux = mux
    def read(self):
        with self.serial as port:
            return json.loads(port.read_until())
    def write(self, string):
        with self.serial as port:
            return port.write(str.encode(string+'\r\n'))
    def query(self, string):
        with self.serial as port:
            port.write(str.encode(string+'\r\n'))
            reply = port.read_until()
            if reply == b'':
                return None
            else:   
                return json.loads(reply)

    def reset(self):
        return self.query('RESET')
    def enable(self):
        return self.query('ENABLE')
    def disable(self):
        return self.query('DISABLE')
    #-----------------------------------#
    # Gets lockin current reading. Will try 5 times to read the UART mux line. If it fails, the lockin may require resetting if there is no no hardware Errors. Also Check for 5V on UART Mux (JST 2 Pin Connector)
    # Command is 'read param param'
    def mux_check(self, mux_true_command, mux_false_command):
        response = None
        if self.mux == True: 
            response = self.query(mux_true_command)
        else:
            response = self.query(mux_false_command)
        return response
    def temp_conversion(self, input_data):
        if type(input_data) == dict:
            return input_data
        if type(self.calibration_array) != None:
            # Expecting a message in the followin format: [32925, 1738841083, 2043.482]
            return round(np.interp(input_data, self.calibration_array[:,1], self.calibration_array[:,0]), 5)
        else:
            return input_data

    def read_temp(self):
        # mux_address cam be mux # or name of sensor
        command = 'R?'
        response = self.mux_check(mux_true_command= f'{command} {self.name}', mux_false_command = f'{command}')
        return self.temp_conversion(response)
    
    #-----------------------------------#
    def read_last_temp(self):
        command = 'LAST?'
        response = self.mux_check(mux_true_command= f'{command} {self.name}', mux_false_command = f'{command}')
        return self.temp_conversion(response)
    
    def read_running_average_temp(self):
        command = 'RA?'
        response = self.mux_check(mux_true_command= f'{command} {self.name}', mux_false_command = f'{command}')
        return self.temp_conversion(response)
    
    def set_bias(self, bias_int):
        command = 'BIAS'
        response = self.mux_check(mux_true_command= f'{command} {self.name} {bias_int}', mux_false_command = f'{command} {bias_int}')
        return response     
    
    def read_bias(self):
        command = 'BIAS?'
        response = self.mux_check(mux_true_command= f'{command} {self.name}', mux_false_command = f'{command}')
        return response  
    
    def set_rate(self):
        command = 'RATE'
        response = self.mux_check(mux_true_command= f'{command} {self.name}', mux_false_command = f'{command}')
        return response  
class Diode(object):
    def __init__(self, address, calibration_file = None, name = None):
        try:
            self.serial = Serial(address, timeout=5)
            self.serial.close()
        except Exception as e:
            print(e)
            pass
        if calibration_file != None:
            self.calibration_array = np.loadtxt(calibration_file, delimiter =',')
        else:
            self.calibration_array = None
        self.name = name
    def read(self):
        with self.serial as port:
            return json.loads(port.read_until())
    def write(self, string):
        with self.serial as port:
            return port.write(str.encode(string+'\r\n'))
    def query(self, string):
        with self.serial as port:
            port.write(str.encode(string+'\n'))
            reply = port.read_until()
            if reply == b'':
                return None
            else:   
                return json.loads(reply)
    def name_check(self, name_true_command, name_false_command):
        if type(self.name) != None: 
            response = self.query(name_true_command)
        elif type(self.name) == None:
            response = self.query(name_false_command)
        return response    
    
    def read_temp(self):
        # mux_address cam be mux # or name of sensor
        command = 'V?'
        response =  self.name_check(name_true_command = f'{command} {self.name}' , name_false_command = f'{command}')
        # Comment out dict reply. Should just reply a voltage now
        if response == None:
            return None
        else:
            for key in response:
                value = response[key]
                if type(value) == None:
                    response[key] = None
                else:
                    response[key] = self.temp_conversion(value)

            #return response
            return response[key]
    def temp_conversion(self, input_data):
        if  type(self.calibration_array) == None:
            return input_data
        else:
            return np.interp(input_data, self.calibration_array[:,1], self.calibration_array[:,0])
class PumpHeater(object):
    def __init__(self, address, name = None):
        try:
            self.serial = Serial(address,timeout=5)
            self.serial.close()
        except Exception as e:
            print(e)
            pass
        self.name = name
        self.been_set_enabled = False
    def read(self):
        with self.serial as port:
            return json.loads(port.read_until())
    def write(self, string):
        with self.serial as port:
            return port.write(str.encode(string+'\r\n'))
    def query(self, string):
        with self.serial as port:
            port.write(str.encode(string+'\n'))
            reply = port.read_until()
            if reply == b'':
                return None
            else:   
                return json.loads(reply)
            
    def name_check(self, name_true_command, name_false_command):
        if type(self.name) != None: 
            response = self.query(name_true_command)
        elif type(self.name) == None:
            response = self.query(name_false_command)
        return response    
    
    # Channel can be an int or a string
    #-----------------------------------#
    # Gets High power heater set dac value
    # Command is 'HPH_I? param'
    def get_pump_current_int(self):
         command = 'HPH_I?'
         return self.name_check(name_true_command = f'{command} {self.name}' , name_false_command = f'{command}')
    #-----------------------------------#
    # Gets High power heater measured voltage and current
    # Command is 'HPH_MON? param'
    def get_pump_measurement(self):
        command = 'HPH_MON?'
        reply = self.name_check(name_true_command = f'{command} {self.name}' , name_false_command = f'{command}')
        return reply[self.name]
    #-----------------------------------#
    # Gets High power heater enable/disable state
    # Command is 'HPH_EN? param'
    def get_enable(self):
        command = 'HPH_EN?'
        return self.name_check(name_true_command = f'{command} {self.name}' , name_false_command = f'{command}')
    #-----------------------------------#   
    # Sets High power heater dac value
    # Command is 'HPH_I param param'
    def set_pump_current(self, current):
        if type(current) == str:
            current = float(current)
        command = 'HPH_I'
        current = int(round(current, 0))
        print(current)
        self.name_check(name_true_command = f'{command} {self.name} {current}' , name_false_command = f'{command} {current}')
        if current != 0:
            if not self.been_set_enabled:
                print('enabled pump')
                self.set_pump_enable(1)
                self.been_set_enabled = True
        elif current == 0:
            self.set_pump_enable(0)
            self.been_set_enabled = False
    #-----------------------------------#   
    # Sets High power heater enable/disable state
    # Command is 'HPH_EN param param'
    def set_pump_enable(self, enabled):
        command = 'HPH_EN'
        return self.name_check(name_true_command = f'{command} {self.name} {enabled}' , name_false_command = f'{command} {enabled}')

class HeatSwitch(object):
    def __init__(self, address,name):
        try:
            self.serial = Serial(address)
            self.serial.close()
        except Exception as e:
            print(e)
            pass
        self.name = name
    def read(self):
        with self.serial as port:
            return json.loads(port.read_until())
    def write(self, string):
        with self.serial as port:
            return port.write(str.encode(string+'\r\n'))
    def query(self, string):
        with self.serial as port:
            port.write(str.encode(string+'\n'))
            reply = port.read_until()

            if reply == b'':
                return None
            else:   
                return json.loads(reply)
        
    # Channel can be an int or a string
    #-----------------------------------#
    # Gets Low Power Heater Voltage in mV
    # Commands is 'LPH_I? param'
    def get_heat_switch_voltage(self):
        reply = self.query(f'LPH_I? {self.name}')
        return reply[self.name]/1e3
    #-----------------------------------#
    # Sets Low Power Heater voltage Outlpg_put in mV
    # Command is 'LPH_I param param'
    # Forcing enable or disable output based on voltage value!
    def set_heat_switch_voltage(self, voltage = 0):
        command = 'LPH_I'
        # function require mV so converting V to mV
        if type(voltage) == str:
            voltage = float(voltage)
        voltage = voltage*1e3
        if voltage != 0:
            self.query(f'{command} {self.name} {voltage}')
            self.set_heat_switch_enable(1)
        elif voltage == 0:
            self.query(f'{command} {self.name} 0')
            self.set_heat_switch_enable(0)
    #-----------------------------------#
    # Gets Low power Heater Channel enable/disable state
    # Command is 'LPH_EN? param'
    def get_heat_switch_enable(self):
        return self.query(f'LPH_EN? {self.name}')
    #-----------------------------------#
    # Sets Low Power Heater enable/disable state
    # Command is 'LPH_EN param param'
    def set_heat_switch_enable(self, enabled):
        return self.query(f'LPH_EN {self.name} {enabled}')
    
    #-----------------------------------#

class WarmupHeater(object):
    def __init__(self, address, calibration_file = None, name = None):
        try:
            self.serial = Serial(address)
            self.serial.close()

        except Exception as e:
            print(e)
            pass
        self.name = name
    def read(self):
        with self.serial as port:
            return json.loads(port.read_until())
    def write(self, string):
        with self.serial as port:
            return port.write(str.encode(string+'/r/n'))
    def query(self, string):
        with self.serial as port:
            port.write(str.encode(string+'/r/n'))
            return json.loads(port.read_until())
        # Channel can be an int or a string
    #-----------------------------------#
    # Gets current measurement of warmup heater in mA
    # Command is 'I? param'
    def get_current(self, channel = 1):
            return self.query(f'I? {channel}')
    #-----------------------------------#
    # Sets ctrl pwm % decimal, see current_list files for what current to expect
    # Command is 'I param param'
    def set_current(self, current, channel = 1):
        return self.query(f'I {channel} {current}')
    #-----------------------------------#
    # Gets CTRL PWM value
    # Command is 'I_PWM? param'
    def get_current_pwm(self, channel = 1):
        return self.query(f'I_PWM? {channel}')
    #-----------------------------------#
    # Sets CTRL PWM value
    # Command is 'I_PWM param param'
    def set_current_pwm(self, pwm, channel = 1):
        return self.query(f'I_PWM {channel} {pwm}')
    #-----------------------------------#
    # Gets PWM value
    # Command is 'PWM? param'
    def get_pwm(self, channel = 1):
        return self.query(f'PWM? {channel}')
    #-----------------------------------#
    # Sets PWM value
    # Command is 'PWM param param'
    def set_pwm(self, pwm, channel = 1):
        return self.query(f'PWM {channel} {pwm}')
    #-----------------------------------#
    # Gets enable/disable state
    # Command is 'EN? param'
    def get_enable(self, channel = 1):
        return self.query(f'EN? {channel}')
    #-----------------------------------#
    # Sets enable/disable state
    # Command is 'EN param param'
    def set_enable(self, enabled, channel = 1):
        return self.query(f'EN {channel} {enabled}')
    def configure(self, current = None, pwm = None, enabled = None):
        current = None
        pwm = None
        enabled = None
        if current != None:
            current = self.set_current(current)
        if pwm != None:
            pwm = self.set_pwm(pwm)
        if enabled != None:
            enabled = self.set_enable(enabled)
        return current, pwm, enabled
    




# %%

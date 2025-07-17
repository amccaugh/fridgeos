#%%
import json
import tomllib
import time
import numpy as np
import logging
import sys
import fridgeos.zmqhelper as zmqhelper
import os

# Device driver imports
from .drivers.haldrivers import hal_classes
from fridgeos.logger import FridgeLogger

# TODO: Make 1 worker per communication address (e.g. 1 for COM5, 1 for COM6, 1 for /dev/usb321)
# TODO: Add configuration-file checking (e.g. for max_heater_value) and error reporting

class HALServer(zmqhelper.Server):

    def __init__(self, port, hardware_toml_path, log_path, debug = False, n_workers = 1):
        self.hardware = {}
        self.hardware['thermometers'] = {}
        self.hardware['heaters'] = {}
        self.logger = FridgeLogger(log_path, logger_name='HAL', debug = debug).logger
        self.load_hardware(hardware_toml_path)
        self.logger.info(f"HAL Server initialized with {len(self.hardware['thermometers'])} thermometers and {len(self.hardware['heaters'])} heaters")
        super().__init__(port, n_workers)
        print('HAL Server started')
    
    def get_hardware(self, name, hardware_type):
        """ Checks that a device with the given name exists
         then returns its python object for use """
        if name not in self.hardware[hardware_type]:
            self.logger.error(f'Device name "{name}" not found for hardware type {hardware_type}, available options are {self.hardware[hardware_type].keys()}')
            raise ValueError(f'Device name "{name}" not found for hardware type {hardware_type}')
        else:
            return self.hardware[hardware_type][name]['python_object']

    def handle(self, message):
        message_dict = json.loads(message)
        command = message_dict['cmd'].lower()
        self.logger.debug(f"Received command: {command}")
        
        try:
            if command == 'get_temperature':
                name = message_dict['name']
                output = self.get_temperature(name)
            elif command == 'get_temperatures':
                output = self.get_temperatures()
            elif command == 'set_heater_value':
                self.logger.debug(f"Setting heater {message_dict['name']} to {message_dict['value']}")
                name = message_dict['name']
                value = message_dict['value']
                output = self.set_heater_value(name, value)
            elif command == 'get_heater_value':
                name = message_dict['name']
                output = self.get_heater_value(name)
            elif command == 'get_heater_values':
                output = self.get_heater_values()
            elif command == 'get_heater_max_values':
                output = self.get_heater_max_values()
            else:
                self.logger.error(f'Unrecognized command "{command}"')
        # Catch errors, log them, and return an empty dictionary
        except Exception as e:
            self.logger.error(f'Error handling command "{command}": {e}')
            output = {}

        message_out = json.dumps(output)
        self.logger.debug(f"Sending response: '{message_out}'")
        return message_out               

    def load_hardware(self, hardware_toml_path):
        self.logger.info(f"Loading hardware configuration from: {hardware_toml_path}")
        
        # Load the TOML file
        with open(hardware_toml_path, "rb") as f:
            all_hardware = tomllib.load(f)
        # For each type of hardware (e.g heater/thermometer), go through each
        # device in the hardware_list, create a Python object, and set it up
        for hardware_type, hardware_list in all_hardware.items():
            self.logger.info(f"Loading {len(hardware_list)} {hardware_type}")
            # Check for duplicate names
            names = [h['name'] for h in hardware_list]
            if len(names) != len(set(names)):
                duplicates = {name for name in names if names.count(name) > 1}
                raise ValueError(f'Duplicate names found in configuration file, {hardware_type} section: {duplicates}')
            # Set up each individual device
            for hw in hardware_list:
                hw_name = hw['hardware']
                if hw_name not in hal_classes:
                    raise ValueError(f'Unrecognized/no driver for {hardware_type} named "{hw_name}"')
                # Create the device as a python object
                hal_class = hal_classes[hw_name]
                python_object = hal_class()
                print(f'Attempting to setup {hw_name} hardware with setup arguments {hw}["setup"]')
                # Configure the device
                print(hw)
                if 'setup' not in hw:
                    hw['setup'] = {}
                python_object.setup(**hw['setup'])
                print(f'Added {hw["hardware"]} thermometer successfully')
                # Add the thermometer object to self.thermometers dictionary
                hw['python_object'] = python_object
                name = hw.pop('name')
                self.hardware[hardware_type][name] = hw
                self.logger.debug(f"Loaded {hardware_type}: {name}")

    def get_temperature(self, name):
        """ Get the temperature of a single thermometer """
        hw = self.get_hardware(name = name, hardware_type = 'thermometers')
        return {name : hw.get_temperature()}
    
    def get_heater_value(self, name):
        """ Get the value of a single heater """
        hw = self.get_hardware(name = name, hardware_type = 'heaters')
        return {name : hw.get_heater_value()}
    
    def set_heater_value(self, name, value):
        """ Set the value of a single heater """
        hw = self.get_hardware(name = name, hardware_type = 'heaters')
        return {name : hw.set_heater_value(value)}

    def get_temperatures(self):
        temperatures = {}
        for name in self.hardware['thermometers'].keys():
            temperatures.update(self.get_temperature(name))
        return temperatures
    
    def get_heater_values(self):
        """ Get the values of all heaters, returns a dictionary of the
        form {name1 : value1, name2 : value2, ...} """
        values = {}
        for name in self.hardware['heaters'].keys():
            values.update(self.get_heater_value(name))
        return values
    
    def get_heater_max_values(self):
        values = {}
        for name in self.hardware['heaters'].keys():
            values[name] = self.hardware['heaters'][name]['max_value']
        return values
    

    # def find_unique_addresses(self,toml_file_path):
    #     # Load the TOML file
    #     data = tomllib.load(toml_file_path)
    #     # Initialize a set to store unique addresses
    #     unique_addresses = set()
    #     # Look for "address" keys in all thermometer, heater, and relay sections
    #     for section_name in list(data.keys()):
    #         if section_name in data:
    #             for item in data[section_name]:
    #                 if "address" in item:
    #                     unique_addresses.add(item["address"])
    #     return unique_addresses


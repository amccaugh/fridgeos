#%%
import json
import tomllib
import time
import numpy as np
import logging
import sys
import os
import threading
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Path
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

# Device driver imports
from .drivers.haldrivers import hal_classes
from fridgeos.logger import FridgeLogger

# TODO: Make 1 worker per communication address (e.g. 1 for COM5, 1 for COM6, 1 for /dev/usb321)
# TODO: Add configuration-file checking (e.g. for max_heater_value) and error reporting

class HeaterValueRequest(BaseModel):
    value: float

class HALServer:
    def __init__(self, port: int, hardware_toml_path: str, log_path: str, debug: bool = False):
        self.app = FastAPI(title="HAL Server", version="1.0.0")
        self.port = port
        self.hardware = {}
        self.hardware['thermometers'] = {}
        self.hardware['heaters'] = {}
        self.logger = FridgeLogger(log_path, logger_name='HAL', debug=debug).logger
        self.server_thread: Optional[threading.Thread] = None
        
        self.load_hardware(hardware_toml_path)
        self.logger.info(f"HAL Server initialized with {len(self.hardware['thermometers'])} thermometers and {len(self.hardware['heaters'])} heaters")
        
        self._setup_routes()
        print('HAL Server initialized')
    
    def _setup_routes(self):
        @self.app.get("/")
        async def root():
            try:
                return {
                    "service": "HAL Server",
                    "version": "1.0.0",
                    "temperatures": self.get_temperatures(),
                    "heater_values": self.get_heater_values(),
                    "heater_max_values": self.get_heater_max_values()
                }
            except Exception as e:
                self.logger.error(f'Error getting device values for root endpoint: {e}')
                # Return basic info if device reads fail
                return {
                    "service": "HAL Server",
                    "version": "1.0.0",
                    "error": f"Could not read device values: {str(e)}"
                }
        
        @self.app.get("/health")
        async def health_check():
            return {"status": "healthy", "timestamp": time.time()}
        
        @self.app.get("/temperatures")
        async def get_all_temperatures():
            try:
                return self.get_temperatures()
            except Exception as e:
                self.logger.error(f'Error getting all temperatures: {e}')
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/temperature/{name}")
        async def get_single_temperature(name: str = Path(..., description="Thermometer name")):
            try:
                return self.get_temperature(name)
            except ValueError as e:
                self.logger.error(f'Error getting temperature for {name}: {e}')
                raise HTTPException(status_code=404, detail=str(e))
            except Exception as e:
                self.logger.error(f'Error getting temperature for {name}: {e}')
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/heaters/values")
        async def get_all_heater_values():
            try:
                return self.get_heater_values()
            except Exception as e:
                self.logger.error(f'Error getting all heater values: {e}')
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/heater/{name}/value")
        async def get_single_heater_value(name: str = Path(..., description="Heater name")):
            try:
                return self.get_heater_value(name)
            except ValueError as e:
                self.logger.error(f'Error getting heater value for {name}: {e}')
                raise HTTPException(status_code=404, detail=str(e))
            except Exception as e:
                self.logger.error(f'Error getting heater value for {name}: {e}')
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.put("/heater/{name}/value")
        async def set_single_heater_value(
            name: str = Path(..., description="Heater name"),
            request: HeaterValueRequest = ...
        ):
            try:
                self.logger.debug(f"Setting heater {name} to {request.value}")
                return self.set_heater_value(name, request.value)
            except ValueError as e:
                self.logger.error(f'Error setting heater value for {name}: {e}')
                raise HTTPException(status_code=404, detail=str(e))
            except Exception as e:
                self.logger.error(f'Error setting heater value for {name}: {e}')
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/heaters/max_values")
        async def get_heater_max_values():
            try:
                return self.get_heater_max_values()
            except Exception as e:
                self.logger.error(f'Error getting heater max values: {e}')
                raise HTTPException(status_code=500, detail=str(e))
    
    def start_server(self):
        """Start the FastAPI server in a separate thread"""
        if self.server_thread is None or not self.server_thread.is_alive():
            self.server_thread = threading.Thread(
                target=lambda: uvicorn.run(
                    self.app, 
                    host="0.0.0.0", 
                    port=self.port, 
                    log_level="info"
                )
            )
            self.server_thread.daemon = True
            self.server_thread.start()
            print(f'HAL Server started on port {self.port}')
    
    def get_hardware(self, name, hardware_type):
        """ Checks that a device with the given name exists
         then returns its python object for use """
        if name not in self.hardware[hardware_type]:
            self.logger.error(f'Device name "{name}" not found for hardware type {hardware_type}, available options are {self.hardware[hardware_type].keys()}')
            raise ValueError(f'Device name "{name}" not found for hardware type {hardware_type}')
        else:
            return self.hardware[hardware_type][name]['python_object']

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
        hw = self.get_hardware(name=name, hardware_type='thermometers')
        return {name: hw.get_temperature()}
    
    def get_heater_value(self, name):
        """ Get the value of a single heater """
        hw = self.get_hardware(name=name, hardware_type='heaters')
        return {name: hw.get_heater_value()}
    
    def set_heater_value(self, name, value):
        """ Set the value of a single heater """
        hw = self.get_hardware(name=name, hardware_type='heaters')
        return {name: hw.set_heater_value(value)}

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


if __name__ == '__main__':
    import os
    
    # Default configuration
    port = 8000
    hardware_toml_path = os.path.join(os.path.dirname(__file__), "hal.toml")
    log_path = "./hal_logs"
    debug = True
    
    print("=== Starting HAL Server ===")
    print(f"Port: {port}")
    print(f"Hardware config: {hardware_toml_path}")
    print(f"Log path: {log_path}")
    print(f"Debug mode: {debug}")
    
    try:
        # Check if config file exists
        if not os.path.exists(hardware_toml_path):
            print(f"ERROR: Hardware configuration file not found: {hardware_toml_path}")
            sys.exit(1)
        
        # Create log directory if it doesn't exist
        os.makedirs(log_path, exist_ok=True)
        
        # Initialize and start the server
        server = HALServer(
            port=port,
            hardware_toml_path=hardware_toml_path,
            log_path=log_path,
            debug=debug
        )
        
        print(f"\nStarting FastAPI server on http://0.0.0.0:{port}")
        print("Available endpoints:")
        print("GET  /                     - Server info and available devices")
        print("GET  /health               - Health check")
        print("GET  /temperatures         - Get all temperatures")
        print("GET  /temperature/{name}   - Get single temperature")
        print("GET  /heaters/values       - Get all heater values")
        print("GET  /heater/{name}/value  - Get single heater value")
        print("PUT  /heater/{name}/value  - Set heater value")
        print("GET  /heaters/max_values   - Get max values for all heaters")
        print("\nPress Ctrl+C to stop the server")
        
        # Start the server (this will block)
        uvicorn.run(server.app, host="0.0.0.0", port=port, log_level="info")
        
    except FileNotFoundError as e:
        print(f"ERROR: Configuration file not found - {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Failed to start HAL Server - {e}")
        sys.exit(1)
import json
import tomllib
import time
import numpy as np
import logging
import sys
import os
import threading
import requests
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Path
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

# Device driver imports
from .drivers.haldrivers import hal_classes
from fridgeos.logger import FridgeLogger


class HeaterValueRequest(BaseModel):
    value: float


class HALClient:
    def __init__(self, ip: str, port: int):
        self.base_url = f"http://{ip}:{port}"
        self.session = requests.Session()
        self.session.headers.update({'Content-Type': 'application/json'})
    
    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """Make HTTP request to HAL server with error handling"""
        url = f"{self.base_url}{endpoint}"
        try:
            if method.upper() == 'GET':
                response = self.session.get(url)
            elif method.upper() == 'PUT':
                response = self.session.put(url, json=data)
            elif method.upper() == 'POST':
                response = self.session.post(url, json=data)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()  # Raises exception for HTTP error codes
            return response.json()
        
        except requests.exceptions.ConnectionError:
            raise ConnectionError(f"Could not connect to HAL server at {self.base_url}")
        except requests.exceptions.HTTPError as e:
            raise RuntimeError(f"HAL server returned error: {e.response.status_code} - {e.response.text}")
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Request failed: {str(e)}")
        except json.JSONDecodeError:
            raise RuntimeError("HAL server returned invalid JSON response")
    
    def get_temperatures(self) -> Dict[str, float]:
        """Get all temperature readings"""
        return self._make_request('GET', '/temperatures')
    
    def get_temperature(self, name: str) -> Dict[str, float]:
        """Get temperature reading for a specific thermometer"""
        return self._make_request('GET', f'/temperature/{name}')
    
    def set_heater_value(self, name: str, value: float) -> Dict[str, float]:
        """Set heater value for a specific heater"""
        return self._make_request('PUT', f'/heater/{name}/value', {'value': value})
    
    def get_heater_values(self) -> Dict[str, float]:
        """Get all heater values"""
        return self._make_request('GET', '/heaters/values')
    
    def get_heater_value(self, name: str) -> Dict[str, float]:
        """Get heater value for a specific heater"""
        return self._make_request('GET', f'/heater/{name}/value')
    
    def get_heater_max_values(self) -> Dict[str, float]:
        """Get maximum values for all heaters"""
        return self._make_request('GET', '/heaters/max_values')
    
    def get_server_info(self) -> Dict[str, Any]:
        """Get server information and all current values"""
        return self._make_request('GET', '/')
    
    def health_check(self) -> Dict[str, Any]:
        """Check if HAL server is healthy"""
        return self._make_request('GET', '/health')


class HALServer:
    def __init__(self, port: int, hardware_toml_path: str, log_path: str, debug: bool = True):
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
        self.logger.info('HAL Server initialized')
    
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
                result = self.get_temperature(name)
                temp = result.get(name)
                if temp is None:
                    self.logger.error(f'Unprocessable thermometer reading for {name}')
                    raise HTTPException(status_code=422, detail=f"Unprocessable thermometer reading for {name}")
                return result
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
            self.logger.info(f'HAL Server started on port {self.port}')
    
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
                self.logger.debug(f'Attempting to setup {hw_name} hardware with setup arguments {hw.get("setup", {})}')
                # Configure the device
                self.logger.debug(f'Hardware config: {hw}')
                if 'setup' not in hw:
                    hw['setup'] = {}
                python_object.setup(**hw['setup'])
                self.logger.info(f'Added {hw["hardware"]} successfully')
                # Add the thermometer object to self.thermometers dictionary
                hw['python_object'] = python_object
                name = hw.pop('name')
                self.hardware[hardware_type][name] = hw
                self.logger.debug(f"Loaded {hardware_type}: {name}")

    def get_temperature(self, name):
        """ Get the temperature of a single thermometer, with error handling for faulty readings """
        self.logger.debug(f"Getting temperature for {name}")
        hw = self.get_hardware(name=name, hardware_type='thermometers')
        try:
            temp = hw.get_temperature()
        except Exception as e:
            self.logger.error(f"Error reading temperature from {name}: {e}")
            temp = None  # or float('nan') if you prefer NaN
        return {name: temp}
    
    def get_heater_value(self, name):
        """ Get the value of a single heater """
        self.logger.debug(f"Getting heater value for {name}")
        hw = self.get_hardware(name=name, hardware_type='heaters')
        return {name: hw.get_heater_value()}
    
    def set_heater_value(self, name, value):
        """ Set the value of a single heater """
        self.logger.debug(f"Setting heater {name} to {value}")
        if value > self.get_heater_max_values()[name]:
            value = self.get_heater_max_values()[name]
            self.logger.warning(f"Heater {name} value {value} is greater than max value {self.get_heater_max_values()[name]}, setting to max value")
        hw = self.get_hardware(name=name, hardware_type='heaters')
        return {name: hw.set_heater_value(value)}

    def get_temperatures(self):
        self.logger.debug(f"Getting temperatures for {self.hardware['thermometers'].keys()}")
        temperatures = {}
        for name in self.hardware['thermometers'].keys():
            result = self.get_temperature(name)
            temperatures.update(result)
        return temperatures
    
    def get_heater_values(self):
        """ Get the values of all heaters, returns a dictionary of the
        form {name1 : value1, name2 : value2, ...} """
        self.logger.debug(f"Getting heater values for {self.hardware['heaters'].keys()}")
        values = {}
        for name in self.hardware['heaters'].keys():
            values.update(self.get_heater_value(name))
        return values
    
    def get_heater_max_values(self):
        self.logger.debug(f"Getting heater max values for {self.hardware['heaters'].keys()}")
        values = {}
        for name in self.hardware['heaters'].keys():
            values[name] = self.hardware['heaters'][name]['max_value']
        return values


def example_usage():
    """Example script showing how to use the HTTP-based HALClient"""
    print("=== HTTP HALClient Example Usage ===")
    
    try:
        # Connect to HAL server
        client = HALClient(ip='127.0.0.1', port=8001)
        
        print("1. Health check:")
        health = client.health_check()
        print(f"   Status: {health['status']}")
        
        print("\n2. Server info:")
        info = client.get_server_info()
        print(f"   Service: {info['service']}")
        print(f"   Current temperatures: {info['temperatures']}")
        print(f"   Current heater values: {info['heater_values']}")
        
        print("\n3. Get all temperatures:")
        temps = client.get_temperatures()
        print(f"   {temps}")
        
        print("\n4. Get single temperature:")
        temp = client.get_temperature('4K')
        print(f"   4K temperature: {temp}")
        
        print("\n5. Get all heater values:")
        heaters = client.get_heater_values()
        print(f"   {heaters}")
        
        print("\n6. Set heater value:")
        result = client.set_heater_value('PUMPHEATER', 5.0)
        print(f"   Set PUMPHEATER to 5.0: {result}")
        
        print("\n7. Get heater max values:")
        max_values = client.get_heater_max_values()
        print(f"   Max values: {max_values}")
        
    except Exception as e:
        print(f"Error: {e}")


if __name__ == '__main__':
    import os
    
    # Default configuration
    port = 8001
    hardware_toml_path = os.path.join(os.path.dirname(__file__), "statemachine/config/hal.toml")
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
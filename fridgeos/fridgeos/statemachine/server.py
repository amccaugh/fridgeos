#%%
import tomllib
import os
from datetime import datetime
import time
import threading
import operator
from typing import Dict, Any, Optional
from simple_pid import PID
import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fridgeos.logger import FridgeLogger
import uvicorn

class StateChangeRequest(BaseModel):
    state: str


class DummyHalClient:
    def __init__(self):
        self.values = {}

    def set_heater_value(self, name, value):
        print(f'[HAL] setting heater {name} to {value}')

    def get_temperatures(self):
        return {'pump': 1.23, '4K': 4.56, '1K': 1.1, '1K-main-plate': 1.05}

class StateMachineServer:
    def __init__(self, config_path, log_path, hal_client, polling_interval = 5, debug=True, http_port=8001):
        self.app = FastAPI(title="State Machine Server", version="1.0.0")
        self.port = http_port
        self.server_thread: Optional[threading.Thread] = None
        
        self.logger = FridgeLogger(log_path=log_path, debug=debug, logger_name="StateMachine").logger
        self.logger.info(f"Initializing State Machine with config: {config_path}")
        
        # Load constants and settings
        self.constants = self._load_constants(config_path)
        self.settings = self._load_settings(config_path)
        
        self.criteria, self.state_timeouts = self._load_transitions(config_path)
        self.heaters = self._load_heaters(config_path)
        self.states = self._load_states(config_path)
        
        # Use polling_interval from [settings] section if available, otherwise use parameter default
        self.logger.info(f'Using polling interval: {polling_interval}')
        self.polling_interval = self.settings.get('polling_interval', polling_interval)
        self.hal_client = hal_client
        
        # Set the first state as the initial state
        self.current_state = list(self.states.keys())[0]    
        self.state_entry_time = time.time()
        self.current_temperatures = {}
        self.current_heater_values = {}
        self.last_temperature_update = time.time()
        self.last_temperature_update_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.state_machine_thread: Optional[threading.Thread] = None
        
        self.logger.info(f"State Machine initialized. Initial state: {self.current_state}")
        self.logger.debug(f"Loaded {len(self.criteria)} transitions, {len(self.heaters)} heaters, {len(self.states)} states")
        
        self._setup_routes()
        self._start_state_machine_loop()
    
    def _load_constants(self, config_path):
        """Load constants from the [constants] section of the TOML file."""
        self.logger.debug(f"Loading constants from {config_path}")
        with open(config_path, "rb") as f:
            config = tomllib.load(f)
        
        constants = config.get('constants', {})
        self.logger.debug(f"Loaded constants: {constants}")
        return constants
    
    def _load_settings(self, config_path):
        """Load settings from the [settings] section of the TOML file."""
        self.logger.debug(f"Loading settings from {config_path}")
        with open(config_path, "rb") as f:
            config = tomllib.load(f)
        
        settings = config.get('settings', {})
        self.logger.debug(f"Loaded settings: {settings}")
        return settings
    
    def _start_state_machine_loop(self):
        if self.state_machine_thread is None or not self.state_machine_thread.is_alive():
            self.state_machine_thread = threading.Thread(target=self.run, daemon=True)
            self.state_machine_thread.start()
            self.logger.info('State machine started automatically')
    
    def _setup_routes(self):
        @self.app.get("/")
        async def root():
            try:
                return {
                    "service": "FridgeOS State Machine Server",
                    "version": "1.0.0",
                    "current_state": self.current_state,
                    "available_states": list(self.states.keys()),
                    "state_entry_time": self.state_entry_time,
                    "time_in_current_state": round(time.time() - self.state_entry_time, 1),
                    "current_temperatures": self.current_temperatures,
                    "current_heater_values": self.current_heater_values,
                    "current_state_target_temperatures": self.states[self.current_state],
                    "last_temperature_update": round(time.time() - self.last_temperature_update, 1),
                    "last_temperature_update_datetime": self.last_temperature_update_datetime
                }
            except Exception as e:
                self.logger.error(f'Error getting state info: {e}')
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/health")
        async def health_check():
            return {"status": "healthy", "timestamp": time.time()}
        
        @self.app.get("/state")
        async def get_current_state():
            return {
                "current_state": self.current_state,
                "state_entry_time": self.state_entry_time,
                "time_in_current_state": round(time.time() - self.state_entry_time, 1)
            }
        
        @self.app.put("/state")
        async def set_state(request: StateChangeRequest):
            try:
                result = self.make_transition(request.state)
                if result:
                    return {
                        "success": True,
                        "message": f"State changed to {request.state}",
                        "new_state": self.current_state,
                        "state_entry_time": round(self.state_entry_time, 1)
                    }
                else:
                    raise HTTPException(
                        status_code=400, 
                        detail=f"Invalid state: {request.state}. Valid states: {list(self.states.keys())}"
                    )
            except Exception as e:
                self.logger.error(f'Error changing state to {request.state}: {e}')
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/statelist")
        async def get_available_states():
            return {
                "available_states": list(self.states.keys()),
                "state_configurations": self.states
            }

        @self.app.get("/temperatures")
        async def get_temperatures():
            """
            Returns the current temperature readings as reported by the state machine.
            """
            try:
                return self.current_temperatures
            except Exception as e:
                self.logger.error(f'Error getting temperatures: {e}')
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
            print(f'State Machine Server started on port {self.port}')
    
    def _parse_criterion(self, crit, constants=None):
        """
        Parse a single criterion string into a dict with sensor, operator function, and value.
        """
        if constants is None:
            constants = {}
            
        parts = crit.strip().split()
        if len(parts) == 3:
            sensor, op, value_str = parts
            
            # Check if value is a constant reference
            if value_str in constants:
                value = constants[value_str]
            else:
                value = float(value_str)
            
            # Map op string to function
            if op == '<':  op_func = operator.lt
            elif op == '>': op_func = operator.gt
            else: raise ValueError(f"Invalid operator: {crit}")
            
            return {'sensor': sensor, 'op': op_func, 'value': value}
        else:
            raise ValueError(f"Invalid criterion format: {crit}")

    def _load_transitions(self, config_path):
        """
        Reads the TOML config file and parses the transition criteria.
        """
        self.logger.debug(f"Loading transitions from {config_path}")
        with open(config_path, "rb") as f:
            config = tomllib.load(f)
        
        # Use already loaded constants
        constants = self.constants
        
        transitions = config.get('transitions', [])
        parsed = []
        state_timeouts = {}
        for t in transitions:
            criteria_list = []
            for crit in t.get('criteria', []):
                # Parse criterion with constants support
                criteria_list.append(self._parse_criterion(crit, constants))
            parsed.append({
                'from': t['from'],
                'to': t['to'],
                'criteria': criteria_list
            })
            if t.get('max_seconds') is not None:
                state_timeouts[(t['from'], t['to'])] = t['max_seconds']
                self.logger.debug(f"Added timeout for {t['from']} -> {t['to']}: {t['max_seconds']}s")
        
        self.logger.info(f"Loaded {len(parsed)} transitions")
        return parsed, state_timeouts

    def _load_heaters(self, config_path):
        """
        Load heater configurations from the TOML file.
        Supports both PID-controlled heaters and direct-value heaters.
        """
        self.logger.debug(f"Loading heaters from {config_path}")
        with open(config_path, "rb") as f:
            config = tomllib.load(f)
        
        heaters = config.get('heaters', {})
        parsed_heaters = {}
        
        for heater_name, heater_config in heaters.items():
            self.logger.debug(f"Loading heater {heater_name}: {heater_config}")
            # Check if this is a PID heater by looking for pid_coefficients
            pid_coefficients = heater_config.get('pid_coefficients')
            
            if pid_coefficients:
                # PID-controlled heater
                corresponding_thermometer = heater_config['corresponding_thermometer']
                max_value = pid_coefficients['max_value']
                self.logger.debug(f"Creating PID heater {heater_name}: P={pid_coefficients.get('P', 0)}, I={pid_coefficients.get('I', 0)}, D={pid_coefficients.get('D', 0)}, max_value={max_value}")
                
                pid_controller = PID(
                    Kp=pid_coefficients.get('P', 0),
                    Ki=pid_coefficients.get('I', 0),
                    Kd=pid_coefficients.get('D', 0),
                    sample_time=None,
                    output_limits=(0, max_value)
                )
                
                parsed_heaters[heater_name] = {
                    'pid': True,
                    'corresponding_thermometer': corresponding_thermometer,
                    'pid_controller': pid_controller
                }
                self.logger.debug(f"Configured PID heater {heater_name} -> {corresponding_thermometer}")
                
            else:
                # Direct-value heater (no max_value for non-PID heaters)
                self.logger.debug(f"Creating non-PID heater {heater_name}")
                
                parsed_heaters[heater_name] = {
                    'pid': False
                }
                self.logger.debug(f"Configured non-PID heater {heater_name}")
        
        self.logger.info(f"Loaded {len(parsed_heaters)} heaters")
        return parsed_heaters

    def _load_states(self, config_path):
        """
        Load state configurations from the TOML file.
        Returns a dictionary of state configurations with their target values.
        Supports constants from the [constants] section.
        """
        self.logger.debug(f"Loading states from {config_path}")
        with open(config_path, "rb") as f:
            config = tomllib.load(f)
        
        # Use already loaded constants for resolving values
        constants = self.constants
        
        states = config.get('states', {})
        parsed_states = {}
        
        for state_name, state_config in states.items():
            parsed_state = {}
            for key, value in state_config.items():
                # Check if value is a constant reference
                if isinstance(value, str) and value in constants:
                    resolved_value = constants[value]
                    self.logger.debug(f"Resolved constant {value} -> {resolved_value} for {state_name}.{key}")
                else:
                    resolved_value = value
                parsed_state[key] = resolved_value
            parsed_states[state_name] = parsed_state
            self.logger.debug(f"Loaded state {state_name}: {parsed_state}")
        
        self.logger.info(f"Loaded {len(parsed_states)} states")
        return parsed_states
        
    def update_heater_setpoints(self, new_state):
        self.logger.info(f"Updating heater setpoints for state: {new_state}")
        state_config = self.states[new_state]
        
        for heater_name, heater_config in self.heaters.items():
            if heater_config['pid']:
                # PID heaters need thermometer setpoints
                corresponding_thermometer = heater_config['corresponding_thermometer']
                if corresponding_thermometer in state_config:
                    value = state_config[corresponding_thermometer]
                    self.logger.debug(f'Setting {corresponding_thermometer} setpoint to {value} for PID heater {heater_name}')
                    pid_controller = heater_config['pid_controller']
                    pid_controller.setpoint = value
                    self.logger.debug(f'PID setpoint for {heater_name} -> {corresponding_thermometer} set to {value}')
                else:
                    self.logger.warning(f'No setpoint found for thermometer {corresponding_thermometer} in state {new_state}')
                    
            else:
                # Direct heaters get their value directly from the state config
                if heater_name in state_config:
                    value = state_config[heater_name]
                    self.logger.debug(f'Setting direct heater {heater_name} to {value}')
                    # Store the value for the update_heaters method to use
                    heater_config['current_value'] = value
                else:
                    self.logger.warning(f'No value found for direct heater {heater_name} in state {new_state}')

    def _check_criterion(self, criterion):
        # check if the temperature criterion is met
        current_temperatures = self.hal_client.get_temperatures()
        self.last_temperature_update = time.time()
        self.last_temperature_update_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if criterion['sensor'] not in current_temperatures:
            self.logger.error(f'No sensor named {criterion["sensor"]} in temperature listing: {current_temperatures}')
            return False
        if current_temperatures[criterion['sensor']] is None:
            self.logger.error(f'Sensor {criterion["sensor"]} returned None value')
            return False
        result = criterion['op'](
            current_temperatures[criterion['sensor']],
            criterion['value'])
        self.logger.debug(f'Criterion: {criterion["sensor"]} {criterion["op"]} {criterion["value"]} = {result}')
        return result

    def check_transitions(self):
        """ Check if any transition criteria are met or if any timeout is exceeded. """
        now = time.time()
        for t in self.criteria:
            if t['from'] == self.current_state:
                self.logger.debug(f'Checking transition: {self.current_state}->{t["to"]}')
                timeout = self.state_timeouts.get((t['from'], t['to']))
                # Check if all criteria are met
                if all(self._check_criterion(c) for c in t['criteria']):
                    self.logger.info(f'Transition criteria met for {t["from"]} to {t["to"]}')
                    return t
                # Check if timeout is exceeded
                if timeout is not None and now - self.state_entry_time > timeout:
                    self.logger.info(f'Transition timeout exceeded for {t["from"]} to {t["to"]} after {timeout}s')
                    return t
        return None

    def attempt_transition(self):
        """ Attempt to transition to the next state. """
        transition = self.check_transitions()
        if transition:
            new_state = transition['to']
            self.make_transition(new_state)
        return False

    def make_transition(self, new_state):
        """ Force a transition to the given state, only if it is a valid state. """
        if new_state not in self.states:
            self.logger.error(f"Attempted to transition to invalid state: '{new_state}'. Valid states: {list(self.states.keys())}")
            return False
        self.logger.info(f'Transitioning from {self.current_state} to {new_state}')
        self.current_state = new_state
        self.state_entry_time = time.time()
        self.update_heater_setpoints(new_state)
        return True

    def update_heaters(self):
        # Get temperatures from HAL Client
        self.current_temperatures = self.hal_client.get_temperatures()
        self.last_temperature_update = time.time()
        self.logger.debug(f"Current temperatures: {self.current_temperatures}")
        
        # Update each heater based on its type
        for heater_name, heater_config in self.heaters.items():
            if heater_config['pid']:
                # PID-controlled heater
                thermometer_name = heater_config['corresponding_thermometer']
                
                if thermometer_name not in self.current_temperatures:
                    self.logger.error(f'No temperature entry for {thermometer_name} (heater {heater_name})')
                    continue
                    
                T = self.current_temperatures[thermometer_name]
                if T is None:
                    self.logger.error(f'Invalid temperature reading received for {thermometer_name} (heater {heater_name})')
                    continue
                    
                self.logger.debug(f'Updating PID heater {heater_name} based on thermometer {thermometer_name} = {T}')
                pid_controller = heater_config['pid_controller']
                new_value = pid_controller(T)
                self.logger.debug(f'Setting PID heater {heater_name} to {new_value} (PID output for {thermometer_name}={T})')
                self.hal_client.set_heater_value(heater_name, new_value)
                # Store the current heater value
                self.current_heater_values[heater_name] = new_value
                
            else:
                # Direct-value heater
                if 'current_value' in heater_config:
                    new_value = heater_config['current_value']
                    
                    self.logger.debug(f'Setting direct heater {heater_name} to {new_value}')
                    self.hal_client.set_heater_value(heater_name, new_value)
                    # Store the current heater value
                    self.current_heater_values[heater_name] = new_value
                else:
                    self.logger.warning(f'No current_value set for direct heater {heater_name}')

    def run(self):
        self.logger.info('Starting state machine loop')
        while True:
            try:
                self.attempt_transition()
                self.update_heaters()
            except Exception as e:
                self.logger.error(f'Exception in state machine loop: {e}', exc_info=True)
            time.sleep(self.polling_interval)


def example_usage():
    """Example script showing how to use the FastAPI StateMachineServer"""
    print("=== FastAPI StateMachineServer Example Usage ===")
    
    print("Example REST API endpoints:")
    print("GET  /                     - Server info and current state")
    print("GET  /health               - Health check")
    print("GET  /state                - Get current state info")
    print("PUT  /state                - Change state (JSON body: {'state': 'warm'})")
    print("GET  /states               - Get available states")
    print("\nExample curl commands:")
    print("curl http://localhost:8001/")
    print("curl http://localhost:8001/state")
    print("curl -X PUT http://localhost:8001/state -H 'Content-Type: application/json' -d '{\"state\": \"warm\"}'")


if __name__ == '__main__':
    server = StateMachineServer(
        config_path = './config/statemachine.toml',
        log_path='./logs/',
        hal_client=DummyHalClient(),
        debug = True,
        http_port=8001,
    )
    
    # Start the FastAPI server
    print(f"Starting FastAPI server on http://0.0.0.0:{server.port}")
    uvicorn.run(server.app, host="0.0.0.0", port=server.port, log_level="info")
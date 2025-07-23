#%%
import tomllib
import os
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

class StateMachineServer:
    def __init__(self, config_path, log_path, hal_client, debug=True, http_port=8001):
        self.app = FastAPI(title="State Machine Server", version="1.0.0")
        self.port = http_port
        self.server_thread: Optional[threading.Thread] = None
        
        self.logger = FridgeLogger(log_path=log_path, debug=debug, logger_name="StateMachine").logger
        self.logger.info(f"Initializing State Machine with config: {config_path}")
        
        self.criteria, self.state_timeouts = self._load_transitions(config_path)
        self.thermometers = self._load_thermometers(config_path)
        self.states = self._load_states(config_path)
        self.hal_client = hal_client
        
        # Set the first state as the initial state
        self.current_state = list(self.states.keys())[0]    
        self.state_entry_time = time.time()
        self.current_temperatures = {}
        self.state_machine_thread: Optional[threading.Thread] = None
        
        self.logger.info(f"State Machine initialized. Initial state: {self.current_state}")
        self.logger.debug(f"Loaded {len(self.criteria)} transitions, {len(self.thermometers)} thermometers, {len(self.states)} states")
        
        self._setup_routes()
        self._start_state_machine_loop()
    
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
                    "service": "State Machine Server",
                    "version": "1.0.0",
                    "current_state": self.current_state,
                    "available_states": list(self.states.keys()),
                    "state_entry_time": self.state_entry_time,
                    "time_in_current_state": time.time() - self.state_entry_time,
                    "current_temperatures": self.current_temperatures
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
                "time_in_current_state": time.time() - self.state_entry_time
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
                        "state_entry_time": self.state_entry_time
                    }
                else:
                    raise HTTPException(
                        status_code=400, 
                        detail=f"Invalid state: {request.state}. Valid states: {list(self.states.keys())}"
                    )
            except Exception as e:
                self.logger.error(f'Error changing state to {request.state}: {e}')
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/states")
        async def get_available_states():
            return {
                "available_states": list(self.states.keys()),
                "state_configurations": self.states
            }
    
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
        
        # Get constants from the [constants] section
        constants = config.get('constants', {})
        self.logger.debug(f"Loaded constants: {constants}")
        
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

    def _load_thermometers(self, config_path):
        """
        Load thermometer configurations from the TOML file.
        """
        self.logger.debug(f"Loading thermometers from {config_path}")
        with open(config_path, "rb") as f:
            config = tomllib.load(f)
        
        thermometers = config.get('thermometers', {})
        parsed_thermometers = {}
        
        for thermometer_name, thermometer_config in thermometers.items():
            # Extract the corresponding heater
            corresponding_heater = thermometer_config.get('corresponding_heater')
            
            # Create PID controller for this thermometer
            coefficients = thermometer_config.get('coefficients', {})
            self.logger.debug(f"Creating PID for {thermometer_name}: P={coefficients.get('P', 0)}, I={coefficients.get('I', 0)}, D={coefficients.get('D', 0)}, max_value={coefficients.get('max_value', 100)}")
            
            pid_controller = PID(
                Kp=coefficients.get('P', 0),
                Ki=coefficients.get('I', 0),
                Kd=coefficients.get('D', 0),
                sample_time=None,
                output_limits=(0, coefficients['max_value'])
            )
            
            parsed_thermometers[thermometer_name] = {
                'corresponding_heater': corresponding_heater,
                'pid_controller': pid_controller
            }
            self.logger.debug(f"Configured {thermometer_name} -> {corresponding_heater}")
        
        self.logger.info(f"Loaded {len(parsed_thermometers)} thermometers")
        return parsed_thermometers

    def _load_states(self, config_path):
        """
        Load state configurations from the TOML file.
        Returns a dictionary of state configurations with their target values.
        Supports constants from the [constants] section.
        """
        self.logger.debug(f"Loading states from {config_path}")
        with open(config_path, "rb") as f:
            config = tomllib.load(f)
        
        # Get constants for resolving values
        constants = config.get('constants', {})
        
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
        thermometer_config = self.states[new_state]
        for thermometer, value in thermometer_config.items():
            if thermometer in self.thermometers:
                self.logger.debug(f'Setting {thermometer} setpoint to {value}')
                heater_name = self.thermometers[thermometer]['corresponding_heater']
                pid_controller = self.thermometers[thermometer]['pid_controller']
                pid_controller.setpoint = value
                self.logger.debug(f'PID setpoint for {thermometer} -> {heater_name} set to {value}')

    def _check_criterion(self, criterion):
        # check if the temperature criterion is met
        current_temperatures = self.hal_client.get_temperatures()
        if criterion['sensor'] not in current_temperatures:
            self.logger.error(f'No sensor named {criterion["sensor"]} in temperature listing: {current_temperatures}')
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
                self.logger.debug(f'Checking transition from {self.current_state} to {t["to"]}')
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
        self.logger.debug(f"Current temperatures: {self.current_temperatures}")
        # For each thermometer listed in the HAL
        for thermometer_name, T in self.current_temperatures.items():
            # If the thermometer is listed in the thermometers section of the config,
            # set the corresponding heater to the value
            if thermometer_name in self.thermometers:
                heater_name = self.thermometers[thermometer_name].get('corresponding_heater')
                if heater_name:
                    pid_controller = self.thermometers[thermometer_name]['pid_controller']
                    new_value = pid_controller(T)
                    self.logger.debug(f'Setting heater {heater_name} to {new_value} (PID output for {thermometer_name}={T})')
                    self.hal_client.set_heater_value(heater_name, new_value)

    def run(self):
        self.logger.info('Starting state machine loop')
        while True:
            try:
                self.update_heaters()
                self.attempt_transition()
                time.sleep(1)
            except Exception as e:
                self.logger.error(f'Exception in state machine loop: {e}', exc_info=True)
                time.sleep(1)
        self.logger.info('State machine loop ended')


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
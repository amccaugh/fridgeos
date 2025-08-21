import tomllib
import os
from datetime import datetime
import time
import threading
import operator
from typing import Dict, Any, Optional
from simple_pid import PID
import json
from fastapi import FastAPI, HTTPException, Form
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from fridgeos.logger import FridgeLogger
import uvicorn
import requests

class StateChangeRequest(BaseModel):
    state: str
    password: Optional[str] = None


class DummyHalClient:
    def __init__(self):
        self.values = {}

    def set_heater_value(self, name, value):
        print(f'[HAL] setting heater {name} to {value}')

    def get_temperatures(self):
        return {'pump': 1.23, '4K': 4.56, '1K': 1.1, '1K-main-plate': 1.05}

class StateMachineServer:
    def __init__(self, config_path, log_path, hal_client, polling_interval = 5, debug=True, http_port=8000):
        self.app = FastAPI(title="State Machine Server", version="1.0.0")
        self.port = http_port
        self.server_thread: Optional[threading.Thread] = None
        
        self.logger = FridgeLogger(log_path=log_path, debug=debug, logger_name="StateMachine").logger
        self.logger.info(f"Initializing State Machine with config: {config_path}")
        
        # Load constants and settings
        self.constants = self._load_constants(config_path)
        self.settings = self._load_settings(config_path)
        
        # Load password from settings if configured
        self.required_password = self.settings.get('state_change_password')
        
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
        self.update_num = 0  # Counter for HAL updates
        self.state_machine_thread: Optional[threading.Thread] = None
        
        self.logger.info(f"State Machine initialized. Initial state: {self.current_state}")
        self.logger.debug(f"Loaded {len(self.criteria)} transitions, {len(self.heaters)} heaters, {len(self.states)} states")
        
        # Set heater setpoints for the initial state
        self.update_heater_setpoints(self.current_state)
        
        self.logger.info(f"Starting up server")
        try:
            self._setup_routes()
            self._start_state_machine_loop()
        except Exception as e:
            self.logger.error(f"Error starting up server: {e}")
            raise e
    
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
    
    def _validate_password(self, provided_password: Optional[str]) -> bool:
        """Validate the provided password against the configured password."""
        if self.required_password is None:
            # No password required
            return True
        if provided_password is None:
            # Password required but not provided
            return False
        return provided_password == self.required_password
    
    def _setup_routes(self):
        @self.app.get("/", response_class=HTMLResponse)
        async def root():
            fridge_name = self.settings.get('fridge_name', 'FridgeOS')
            return f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>{fridge_name} FridgeOS State Machine</title>
            </head>
            <body>
                <h2>FridgeOS State Machine Server</h2>
                <p>Fridge name: {fridge_name}</p>
                <ul>
                    <li>Information
                        <ul>
                            <li><a href="/info">Server Info</a> - Detailed status and configuration</li>
                            <li><a href="/temperatures">Temperatures</a> - Current temperature readings</li>
                            <li><a href="/heaters">Heaters</a> - Current heater values</li>
                            <li><a href="/state">Current State</a> - Current state info only</li>
                            <li><a href="/statelist">Available States</a> - List of all possible states</li>
                            <li><a href="/health">Health Check</a> - Simple health status</li>
                        </ul>
                    </li>
                    <li>Control
                        <ul>
                            <li><a href="/control">State Control</a> - Change system state</li>
                            <li><a href="/heater/set">Heater Control</a> - Change heater values</li>
                        </ul>
                    </li>
                </ul>
                <p><a href="https://github.com/amccaugh/fridgeos" target="_blank">FridgeOS GitHub Repository</a></p>
            </body>
            </html>
            """

        @self.app.get("/info")
        async def info():
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
                    "last_temperature_update_datetime": self.last_temperature_update_datetime,
                    "update_num": self.update_num
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
                # Validate password if required
                if not self._validate_password(request.password):
                    self.logger.warning(f"Invalid password provided for state change to {request.state}")
                    raise HTTPException(
                        status_code=401, 
                        detail="Invalid or missing password required for state changes"
                    )
                
                result = self.make_transition(request.state)
                if result:
                    self.logger.info(f"State changed to {request.state} via API")
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
            except HTTPException:
                raise
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

        @self.app.get("/heaters")
        async def get_heaters():
            """
            Returns the current heater values as reported by the state machine.
            """
            try:
                return self.current_heater_values
            except Exception as e:
                self.logger.error(f'Error getting heater values: {e}')
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/pause")
        async def pause_system_endpoint():
            """
            Pause the system by transitioning to PAUSED state.
            """
            try:
                result = self.pause_system()
                if result:
                    return {
                        "success": True,
                        "message": "System paused successfully",
                        "current_state": self.current_state
                    }
                else:
                    raise HTTPException(status_code=400, detail="Failed to pause system")
            except Exception as e:
                self.logger.error(f'Error pausing system: {e}')
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/resume")
        async def resume_system_endpoint(request: dict):
            """
            Resume the system from PAUSED state to a target state.
            """
            try:
                target_state = request.get('target_state')
                result = self.resume_system(target_state)
                if result:
                    return {
                        "success": True,
                        "message": f"System resumed to {self.current_state}",
                        "current_state": self.current_state
                    }
                else:
                    raise HTTPException(status_code=400, detail="Failed to resume system")
            except Exception as e:
                self.logger.error(f'Error resuming system: {e}')
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/heater/set")
        async def set_heater_value_endpoint(heater_name: str = Form(...), value: str = Form(...)):
            """
            Set a heater to a specific value directly.
            """
            try:
                if heater_name is None or value is None:
                    raise HTTPException(status_code=400, detail="Missing heater_name or value")
                
                try:
                    value_float = float(value)
                except ValueError:
                    raise HTTPException(status_code=400, detail="Value must be a number")
                
                result = self.set_heater_value(heater_name, value_float)
                if result:
                    return HTMLResponse(f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <title>Heater Set Successfully</title>
                    </head>
                    <body>
                        <p>Heater {heater_name} set to {value_float}</p>
                        <p><a href="/heater/set">← Back to Heater Control</a> | <a href="/">← Back to Main Page</a></p>
                    </body>
                    </html>
                    """)
                else:
                    raise HTTPException(status_code=400, detail=f"Failed to set heater {heater_name}")
            except HTTPException:
                raise
            except Exception as e:
                self.logger.error(f'Error setting heater value: {e}')
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/heater/set", response_class=HTMLResponse)
        async def heater_control_page():
            """
            Web interface for setting heater values.
            """
            fridge_name = self.settings.get('fridge_name', 'FridgeOS')
            
            # Create form for each heater
            heater_forms = ""
            for heater_name in self.heaters.keys():
                current_value = self.current_heater_values.get(heater_name, 0)
                heater_forms += f"""
                <p><strong>Heater: {heater_name}</strong></p>
                <p>Current value: {current_value}</p>
                <form action="/heater/set" method="post">
                    <input type="hidden" name="heater_name" value="{heater_name}">
                    <label for="value_{heater_name}">New Value:</label>
                    <input type="number" step="0.1" name="value" id="value_{heater_name}" required>
                    <input type="submit" value="Set Value">
                </form>
                <br>
                """
            
            return f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>{fridge_name} Heater Control</title>
            </head>
            <body>
                <h3>Heater Control</h3>
                <p><a href="/">← Back to main page</a></p>
                <p>Set individual heater values directly:</p>
                {heater_forms}
            </body>
            </html>
            """

        @self.app.get("/control", response_class=HTMLResponse)
        async def control_page():
            fridge_name = self.settings.get('fridge_name', 'FridgeOS')
            
            if self.required_password:
                # Show form-based control when password is required
                state_options = "".join([
                    f'<option value="{state}">{state}</option>' 
                    for state in self.states.keys()
                ])
                return f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>{fridge_name} FridgeOS State Machine</title>
                </head>
                <body>
                    <h3>FridgeOS State Control</h3>
                    <p>Current state: <strong>{self.current_state}</strong></p>
                    <p>Password required for state changes.</p>
                    <form action="/control/set" method="post">
                        <label for="state">New State:</label>
                        <select name="state" id="state" required>
                            {state_options}
                        </select><br><br>
                        <label for="password">Password:</label>
                        <input type="password" name="password" id="password" required><br><br>
                        <input type="submit" value="Change State">
                    </form>
                </body>
                </html>
                """
            else:
                # Show link-based control when no password is required
                state_links = "".join([
                    f'<li><a href="/control/{state}">{state}</a></li>' 
                    for state in self.states.keys()
                ])
                return f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>{fridge_name} FridgeOS State Machine</title>
                </head>
                <body>
                    <h3>FridgeOS State Control</h3>
                    <p>Current state: <strong>{self.current_state}</strong></p>
                    <p>Available states (click to change to new state):</p>
                    <ul>
                        {state_links}
                    </ul>
                </body>
                </html>
                """

        @self.app.post("/control/set")
        async def set_state_form(state: str = Form(...), password: str = Form(...)):
            fridge_name = self.settings.get('fridge_name', 'FridgeOS')
            
            # Validate password if required
            if not self._validate_password(password):
                self.logger.warning(f"Invalid password provided for state change to {state} via web form")
                return HTMLResponse(f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>{fridge_name} FridgeOS State Machine</title>
                </head>
                <body>
                    <p>Error: Invalid password</p>
                    <p><a href="/control">← Back to control page</a></p>
                </body>
                </html>
                """, status_code=401)
            
            result = self.make_transition(state)
            if result:
                self.logger.info(f"State changed to {state} via web form")
                return HTMLResponse(f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>{fridge_name} FridgeOS State Machine</title>
                </head>
                <body>
                    <p>State changed to <strong>{state}</strong></p>
                    <p><a href="/control">← Back to control page</a> | <a href="/">← Back to main page</a></p>
                </body>
                </html>
                """)
            else:
                return HTMLResponse(f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>{fridge_name} FridgeOS State Machine</title>
                </head>
                <body>
                    <p>Error: Invalid state <strong>{state}</strong></p>
                    <p><a href="/control">← Back to control page</a></p>
                </body>
                </html>
                """, status_code=400)

        @self.app.get("/control/{state}")
        async def set_state_link(state: str):
            fridge_name = self.settings.get('fridge_name', 'FridgeOS')
            
            # If password is required, don't allow direct link access
            if self.required_password:
                return HTMLResponse(f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>{fridge_name} FridgeOS State Machine</title>
                </head>
                <body>
                    <p>Error: Password required for state changes. Please use the <a href="/control">control form</a>.</p>
                </body>
                </html>
                """, status_code=401)
            
            result = self.make_transition(state)
            if result:
                self.logger.info(f"State changed to {state} via web link")
                return HTMLResponse(f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>{fridge_name} FridgeOS State Machine</title>
                </head>
                <body>
                    <p>State changed to <strong>{state}</strong></p>
                    <p><a href="/control">← Back to control page</a> | <a href="/">← Back to main page</a></p>
                </body>
                </html>
                """)
            else:
                return HTMLResponse(f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>{fridge_name} FridgeOS State Machine</title>
                </head>
                <body>
                    <p>Error: Invalid state <strong>{state}</strong></p>
                    <p><a href="/control">← Back to control page</a></p>
                </body>
                </html>
                """, status_code=400)
    
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
            
            # Handle both single string and list of "from" states
            from_states = t['from']
            if isinstance(from_states, str):
                from_states = [from_states]  # Convert single string to list
            
            parsed.append({
                'from': from_states,
                'to': t['to'],
                'criteria': criteria_list
            })
            
            # Handle timeouts for multiple from states
            if t.get('max_seconds') is not None:
                for from_state in from_states:
                    state_timeouts[(from_state, t['to'])] = t['max_seconds']
                    self.logger.debug(f"Added timeout for {from_state} -> {t['to']}: {t['max_seconds']}s")
        
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
        
        # Automatically add PAUSED state that prevents heaters from being activated
        parsed_states['PAUSED'] = {}
        self.logger.info(f"Automatically added PAUSED state")
        
        self.logger.info(f"Loaded {len(parsed_states)} states (including automatic PAUSED state)")
        return parsed_states
        
    def update_heater_setpoints(self, new_state):
        self.logger.info(f"Updating heater setpoints for state: {new_state}")
        state_config = self.states[new_state]
        
        # Special handling for PAUSED state - don't update heater setpoints
        if new_state == 'PAUSED':
            self.logger.info('PAUSED state activated - heaters will not be updated')
            return
        
        # Normal state processing
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
        
        # Special handling for PAUSED state - only allow manual transitions
        if self.current_state == 'PAUSED':
            self.logger.debug('PAUSED state - no automatic transitions allowed')
            return None
        
        for t in self.criteria:
            if self.current_state in t['from']:
                self.logger.debug(f'Checking transition: {self.current_state}->{t["to"]}')
                timeout = self.state_timeouts.get((self.current_state, t['to']))
                # Check if all criteria are met
                if all(self._check_criterion(c) for c in t['criteria']):
                    self.logger.info(f'Transition criteria met for {self.current_state} to {t["to"]}')
                    return t
                # Check if timeout is exceeded
                if timeout is not None and now - self.state_entry_time > timeout:
                    self.logger.info(f'Transition timeout exceeded for {self.current_state} to {t["to"]} after {timeout}s')
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
    
    def pause_system(self):
        """ Pause the system by transitioning to PAUSED state. """
        if self.current_state == 'PAUSED':
            self.logger.info('System is already paused')
            return True
        self.logger.info('Pausing system - transitioning to PAUSED state')
        return self.make_transition('PAUSED')
    
    def resume_system(self, target_state=None):
        """ Resume the system from PAUSED state to a target state or the previous state. """
        if self.current_state != 'PAUSED':
            self.logger.info('System is not paused')
            return False
        
        if target_state is None:
            # If no target state specified, try to resume to a safe default
            # Look for a state that's not PAUSED and has reasonable heater values
            safe_states = [state for state in self.states.keys() if state != 'PAUSED']
            if safe_states:
                target_state = safe_states[0]  # Use first available state as default
                self.logger.info(f'No target state specified, resuming to default: {target_state}')
            else:
                self.logger.error('No safe states available to resume to')
                return False
        
        if target_state not in self.states:
            self.logger.error(f"Invalid target state for resume: '{target_state}'. Valid states: {list(self.states.keys())}")
            return False
        
        self.logger.info(f'Resuming system from PAUSED to {target_state}')
        return self.make_transition(target_state)
    
    def set_heater_value(self, heater_name: str, value: float):
        """ Set a heater to a specific value directly. """
        if heater_name not in self.heaters:
            self.logger.error(f"Heater '{heater_name}' not found")
            return False
        
        heater_config = self.heaters[heater_name]
        
        # Set the value directly via HAL
        try:
            self.hal_client.set_heater_value(heater_name, value)
            self.current_heater_values[heater_name] = value
            self.logger.info(f"Set heater '{heater_name}' to {value}")
            return True
        except Exception as e:
            self.logger.error(f"Error setting heater '{heater_name}' to {value}: {e}")
            return False

    def update_heaters(self):
        # Get temperatures from HAL Client
        self.current_temperatures = self.hal_client.get_temperatures()
        self.last_temperature_update = time.time()
        self.last_temperature_update_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.logger.debug(f"Current temperatures: {self.current_temperatures}")
        
        # Get current heater values from HAL Client
        try:
            hal_heater_values = self.hal_client.get_heater_values()
            self.logger.debug(f"Current heater values from HAL: {hal_heater_values}")
            # Update our stored values with actual HAL values
            self.current_heater_values.update(hal_heater_values)
        except Exception as e:
            self.logger.error(f"Error getting heater values from HAL: {e}")
        
        # Increment update counter after successful HAL communication
        self.update_num += 1
        
        # Skip heater updates if system is paused
        if self.current_state == 'PAUSED':
            self.logger.debug('PAUSED state - skipping heater updates')
            return
        
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
                
            else:
                # Direct-value heater
                if 'current_value' in heater_config:
                    new_value = heater_config['current_value']
                    
                    self.logger.debug(f'Setting direct heater {heater_name} to {new_value}')
                    self.hal_client.set_heater_value(heater_name, new_value)
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



class StateMachineClient:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url.rstrip("/")

    def get_state(self):
        """Get the current state from the server (just the state string)."""
        resp = requests.get(f"{self.base_url}/state")
        resp.raise_for_status()
        data = resp.json()
        return data["current_state"]

    def set_state(self, state, password=None):
        """Set the state on the server. Returns None if successful, raises an error if not."""
        request_data = {"state": state}
        if password is not None:
            request_data["password"] = password
            
        resp = requests.put(
            f"{self.base_url}/state",
            json=request_data,
            headers={"Content-Type": "application/json"}
        )
        try:
            resp.raise_for_status()
        except requests.HTTPError as e:
            # Try to extract the error message from the response
            try:
                error_detail = resp.json().get("detail", str(e))
            except Exception:
                error_detail = str(e)
            raise RuntimeError(f"Failed to set state: {error_detail}") from e
        return None

    def get_temperatures(self):
        """Get all temperature readings from the server."""
        resp = requests.get(f"{self.base_url}/temperatures")
        resp.raise_for_status()
        return resp.json()

    def get_root(self):
        """Get all data from the root endpoint of the server."""
        resp = requests.get(f"{self.base_url}/")
        resp.raise_for_status()
        return resp.json()

    def get_heaters(self):
        """Get all heater values from the server."""
        resp = requests.get(f"{self.base_url}/heaters")
        resp.raise_for_status()
        return resp.json()

    def get_info(self):
        """Get all info data from the server."""
        resp = requests.get(f"{self.base_url}/info")
        resp.raise_for_status()
        return resp.json()


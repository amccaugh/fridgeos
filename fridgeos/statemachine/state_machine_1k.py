#%%
from fridgeos.monitor.server import MetricsServer
from fridgeos.monitor.client import MonitorClient
import tomllib
import os
import time
import operator
from simple_pid import PID
import fridgeos.zmqhelper as zmqhelper
import json
from fridgeos.logger import FridgeLogger

class DummyMonitorClient:
    def __init__(self):
        self.metrics = {}
    
    def get_temperatures(self):
        return self.metrics
    
    def set_metric(self, name, value):
        self.metrics[name] = value 


class DummyHalClient:
    def __init__(self):
        self.values = {}

    def set_heater_value(self, name, value):
        print(f'[HAL] setting heater {name} to {value}')



class Fridge(zmqhelper.Server):
    def __init__(self, config_path, monitor_client, hal_client):
        self.criteria, self.state_timeouts = self._load_transitions(config_path)
        self.thermometers = self._load_thermometers(config_path)
        self.states = self._load_states(config_path)
        self.monitor_client = monitor_client
        self.hal_client = hal_client
        # Set the first state as the initial state
        self.current_state = list(self.states.keys())[0]    
        self.state_entry_time = time.time()
        self.logger = FridgeLogger(log_path="logs", debug=True, logger_name="StateMachine").logger
        super().__init__(port=5556, n_workers=1)

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
        with open(config_path, "rb") as f:
            config = tomllib.load(f)
        
        # Get constants from the [constants] section
        constants = config.get('constants', {})
        
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
        return parsed, state_timeouts

    def _load_thermometers(self, config_path):
        """
        Load thermometer configurations from the TOML file.
        """
        with open(config_path, "rb") as f:
            config = tomllib.load(f)
        
        thermometers = config.get('thermometers', {})
        parsed_thermometers = {}
        
        for thermometer_name, thermometer_config in thermometers.items():
            # Extract the corresponding heater
            corresponding_heater = thermometer_config.get('corresponding_heater')
            
            # Create PID controller for this thermometer
            coefficients = thermometer_config.get('coefficients', {})
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
        
        return parsed_thermometers

    def _load_states(self, config_path):
        """
        Load state configurations from the TOML file.
        Returns a dictionary of state configurations with their target values.
        Supports constants from the [constants] section.
        """
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
                else:
                    resolved_value = value
                parsed_state[key] = resolved_value
            parsed_states[state_name] = parsed_state
        
        return parsed_states

        
    def handle(self, message):
        """ ZMQ helper method to handle messages from the client. """
        message_dict = json.loads(message)
        command = message_dict['cmd'].lower()
        self.logger.debug(f"Message received: '{message}'")
        
        try:
            if command == 'get_state':
                output = self.current_state
            if command == 'set_state':
                new_state = message_dict['state']
                self.make_transition(new_state)
            else:
                self.logger.error(f'Unrecognized command "{command}"')
        # Catch errors, log them, and return an empty dictionary
        except Exception as e:
            self.logger.error('Python error:', exc_info=e)
            output = {}

        message_out = json.dumps(output)
        self.logger.debug(f"Sending message: '{message_out}'")
        return message_out               

    def update_heater_setpoints(self, new_state):
        thermometer_config = self.states[new_state]
        for thermometer, value in thermometer_config.items():
            print(f'Setting {thermometer} to {value}')
            heater_name = self.thermometers[thermometer]['corresponding_heater']
            pid_controller = self.thermometers[thermometer]['pid_controller']
            pid_controller.setpoint = value

    def _check_criterion(self, criterion):
        # check if the temperature criterion is met
        current_temperatures = self.monitor_client.get_temperatures()
        if "sensor" not in criterion:
            print(f'No sensor named {criterion["sensor"]} in temperature listing: {current_temperatures}')
            return False
        result = criterion['op'](
            current_temperatures[criterion['sensor']],
            criterion['value'])
        print(f'Criterion: {criterion["sensor"]} {criterion["op"]} {criterion["value"]} = {result}')
        return result

    def check_transitions(self):
        """ Check if any transition criteria are met or if any timeout is exceeded. """
        now = time.time()
        for t in self.criteria:
            if t['from'] == self.current_state:
                print(f'Checking transition from {self.current_state} to {t["to"]}')
                timeout = self.state_timeouts.get((t['from'], t['to']))
                # Check if all criteria are met
                if all(self._check_criterion(c) for c in t['criteria']):
                    print(f'Transition criteria met for {t["from"]} to {t["to"]}')
                    return t
                # Check if timeout is exceeded
                if timeout is not None and now - self.state_entry_time > timeout:
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
        """ Force a transition to the given state. """
        print(f'Transitioning from {self.current_state} to {new_state}')
        self.current_state = new_state
        self.state_entry_time = time.time()
        self.update_heater_setpoints(new_state)
        return True

    def update_heaters(self):
        # Get temperatures from MonitorClient
        self.current_temperatures = self.monitor_client.get_temperatures()
        # For each thermometer listed in the monitor
        for thermometer_name, T in self.current_temperatures.items():
            # If the thermometer is listed in the thermometers section of the config,
            # set the corresponding heater to the value
            if thermometer_name in self.thermometers:
                heater_name = self.thermometers[thermometer_name].get('corresponding_heater')
                if heater_name:
                    pid_controller = self.thermometers[thermometer_name]['pid_controller']
                    new_value = pid_controller(T)
                    print(f'Setting heater {heater_name} to {new_value}')
                    self.hal_client.set_heater(heater_name, new_value)

    def run(self):
        self.logger.info('Starting state machine')
        while True:
            self.update_heaters()
            self.attempt_transition()
            time.sleep(1)


monitor_client = DummyMonitorClient()
monitor_client.set_metric('1K', 300)
monitor_client.set_metric('1K-main-plate', 300)
monitor_client.set_metric('4K', 300)
monitor_client.set_metric('40K', 300)
monitor_client.set_metric('pump', 300)
monitor_client.set_metric('heat_switch', 300)
print(monitor_client.get_temperatures())

hal_client = DummyHalClient()
fridge = Fridge(config_path = 'state_machine_1k.toml', 

    monitor_client = monitor_client,
    hal_client = hal_client)


print(f'Fridge state: {fridge.current_state}')
fridge.attempt_transition()
#%%
monitor_client.set_metric('1K', 4.5)
monitor_client.set_metric('1K-main-plate', 4.5)
monitor_client.set_metric('4K', 4.5)
monitor_client.set_metric('40K', 40)
monitor_client.set_metric('pump', 50)
monitor_client.set_metric('heat_switch', 1)
print(f'Current state: {fridge.current_state}')
fridge.attempt_transition()




# %%

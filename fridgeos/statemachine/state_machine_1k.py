#%%
from fridgeos.monitor.server import MetricsServer
from fridgeos.monitor.client import MonitorClient
import tomllib
import os
import time
import operator
from simple_pid import PID


class Fridge:
    def __init__(self, config_path):
        self.criteria, self.state_timeouts = self._load_transitions(config_path)
        self.thermometers = self._load_thermometers(config_path)
        self.states = self._load_states(config_path)
        self.current_temperatures = {
            'heat_switch': 0,
            'pump': 0,
        }
        self.current_state = 'warm'
        self.state_entry_time = time.time()
        

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
                output_limits=(0, 100)  # Default limits, can be made configurable
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

    def update_heater_setpoints(self, new_state):
        thermometer_config = self.states[new_state]
        for thermometer, value in thermometer_config.items():
            print(f'Setting {thermometer} to {value}')
            heater_name = self.thermometers[thermometer]['corresponding_heater']
            pid_controller = self.thermometers[thermometer]['pid_controller']
            pid_controller.setpoint = value

    def _check_criterion(self, criterion):
        # check if the temperature criterion is met
        return criterion['op'](
            self.current_temperatures[criterion['sensor']],
            criterion['value'])

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
            print(f'Transitioning from {self.current_state} to {new_state}')
            self.current_state = new_state
            self.state_entry_time = time.time()
            self.update_heater_setpoints(new_state)
            return True
        return False

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





fridge = Fridge(config_path = 'state_machine_1k.toml')
#%%
fridge.attempt_transition() 
fridge.current_temperatures['heat_switch'] = 21
fridge.attempt_transition() 

# Test constants functionality
print("=== Testing Constants Functionality ===")
print(f"Loaded criteria: {fridge.criteria}")
print(f"Constants from TOML: switch_temp = 20")

# Test the first transition criteria (should use switch_temp constant)
first_transition = fridge.criteria[0]
print(f"First transition criteria: {first_transition['criteria']}")

# Test criterion evaluation
test_criterion = first_transition['criteria'][0]  # "heat_switch < switch_temp"
print(f"Testing criterion: {test_criterion}")
print(f"Current heat_switch temperature: {fridge.current_temperatures['heat_switch']}")
print(f"Criterion result: {fridge._check_criterion(test_criterion)}")

#%%


if __name__ == "__main__":
    """Demonstrate the state machine with MonitorClient integration"""
    print("=== State Machine with Monitor Integration Demo ===\n")
    
    # Create monitor server (for demo purposes)
    monitor_server = MetricsServer(cryostat_name='mycryo')
    
    # Create monitor client
    monitor_client = MonitorClient(url="http://localhost:8000", timeout=0.1)
    
    # Get the path to the TOML file
    toml_path = os.path.join(os.path.dirname(__file__), "state_machine_1k.toml")
    
# %%

#%%
from fridgeos.monitor.server import MetricsServer
from fridgeos.monitor.client import MonitorClient
import tomllib
import os
import time
import operator


class Fridge(object):
    def __init__(self, config_path):
        self.criteria, self.state_timeouts = self.load_transition_criteria(config_path)
        self.current_temperatures = {
            'heat_switch': 0,
            'pump': 0,
        }
        self.current_state = 'warm'
        self.state_entry_time = time.time()

    def update_heaters(self):
        # update heaters here with HAL client
        pass

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
                # Check if the transition criteria are met or timeout
                print(f'Checking transition from {self.current_state} to {t["to"]}')
                timeout = self.state_timeouts.get((t['from'], t['to']))
                if all(self._check_criterion(c) for c in t['criteria']):
                    print(f'Transition criteria met for {t["from"]} to {t["to"]}')
                    return t
                if timeout is not None and now - self.state_entry_time > timeout:
                    return t
        return None

    def attempt_transition(self):
        """ Attempt to transition to the next state. """
        transition = self.check_transitions()
        if transition:
            print(f'Transitioning from {self.current_state} to {transition["to"]}')
            self.current_state = transition['to']
            self.state_entry_time = time.time()
            return True
        return False

    def _parse_criterion(self, crit):
        """
        Parse a single criterion string into a dict with sensor, operator function, and value.
        """
        parts = crit.strip().split()
        if len(parts) == 3:
            sensor, op, value = parts
            value = float(value)
            # Map op string to function
            if op == '<':  op_func = operator.lt
            elif op == '>': op_func = operator.gt
            else: raise ValueError(f"Invalid operator: {op}")
            return {'sensor': sensor, 'op': op_func, 'value': value}
        else:
            raise ValueError(f"Invalid criterion format: {crit}")


    def load_transition_criteria(self, config_path):
        """
        Reads the TOML config file and parses the transition criteria.
        """
        with open(config_path, "rb") as f:
            config = tomllib.load(f)
        transitions = config.get('transitions', [])
        parsed = []
        state_timeouts = {}
        for t in transitions:
            criteria_list = []
            for crit in t.get('criteria', []):
                # Example crit: "heat_switch < 20"
                criteria_list.append(self._parse_criterion(crit))
            parsed.append({
                'from': t['from'],
                'to': t['to'],
                'criteria': criteria_list
            })
            if t.get('max_seconds') is not None:
                state_timeouts[(t['from'], t['to'])] = t['max_seconds']
        return parsed, state_timeouts




fridge = Fridge(config_path = 'state_machine_1k.toml')
fridge.attempt_transition() 
fridge.current_temperatures['heat_switch'] = 21
fridge.attempt_transition() 
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

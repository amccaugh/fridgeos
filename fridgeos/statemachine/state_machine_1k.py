#%%
from transitions import Machine
import random
from fridgeos.monitor.server import MetricsServer
from fridgeos.monitor.client import MonitorClient
import tomllib
import os
import time
import operator
import random


class Fridge(object):
    def __init__(self, config_path):
        self.machine = Machine(auto_transitions=False) # For plotting the graph only
        self.criteria = self.load_transition_criteria(config_path)
        self.current_temperatures = {
            'heat_switch': 0,
            'pump': 0,
        }

    def update_heaters(self):
        # update heaters here with HAL client
        pass

    def _check_criterion(self, criterion):
        # check if the temperature criterion is met
        return criterion['op'](self.current_temperatures[criterion['sensor']], criterion['value'] )

    def check_transition_criteria(self):
        """
        Check if all transition criteria for the current state are met.
        Goes through each of the criteria in self.criteria for the current state.
        """
        current_state = self.machine.state
        for transition in self.criteria:
            if transition['from'] == current_state:
                # If all criteria are met, return the transition
                for criterion in transition['criteria']:
                    if not self._check_criterion(criterion):
                        break
                else:
                    return transition
        return None


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
        for t in transitions:
            criteria_list = []
            for crit in t.get('criteria', []):
                # Example crit: "heat_switch < 20"
                criteria_list.append(self._parse_criterion(crit))
            parsed.append({
                'from': t['from'],
                'to': t['to'],
                'max_seconds': t.get('max_seconds'),
                'criteria': criteria_list
            })
            self.machine.add_transition(trigger = f'transition_{t["from"]}_{t["to"]}', 
                source = t['from'], dest = t['to'],
                conditions='check_temperature_criteria', after=['update_heaters'])
        return parsed




fridge = Fridge(config_path = 'state_machine_1k.toml')
print(fridge.check_transition_criteria()) # FIXME NOT WORKING START HERE

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
    
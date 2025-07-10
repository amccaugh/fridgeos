#%%
from transitions import Machine
import random
from fridgeos.monitor.server import MetricsServer
from fridgeos.monitor.client import MonitorClient
import tomllib
import os
import time
from typing import Dict, Any, List





class ConfigurableStateMachine:
    """State machine that reads configuration from TOML and uses MonitorClient for conditions"""
    
    def __init__(self, config_path: str, monitor_client: MonitorClient):
        self.config_path = config_path
        self.monitor_client = monitor_client
        
        # Load configuration
        self.config = self._load_config()
        
        # Extract states from transitions
        self.states = self._extract_states()
        
        # Initialize the state machine
        self.machine = Machine(
            model=self,
            states=self.states,
            initial=self.states[0] if self.states else 'unknown',
            auto_transitions=False,
            ignore_invalid_triggers=True
        )
        
        # Add transitions from configuration
        self._add_transitions()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load TOML configuration file"""
        with open(self.config_path, "rb") as f:
            return tomllib.load(f)
    
    def _extract_states(self) -> List[str]:
        """Extract unique states from transitions"""
        states = set()
        for transition in self.config.get('transitions', []):
            states.add(transition['from'])
            states.add(transition['to'])
        return list(states)
    
    def _add_transitions(self):
        """Add transitions from configuration"""
        for i, transition in enumerate(self.config.get('transitions', [])):
            from_state = transition['from']
            to_state = transition['to']
            conditions = transition.get('conditions', [])
            max_seconds = transition.get('max_seconds', None)
            
            # Create a unique trigger name
            trigger_name = f"transition_{i}_{from_state}_to_{to_state}"
            
            # Store transition info for later use
            setattr(self, trigger_name, lambda t=trigger_name, tr=transition: self._execute_transition(t, tr))
    
    def _check_conditions_with_metrics(self, conditions: List[Dict[str, Any]], metrics: Dict[str, Any]) -> bool:
        """Check all conditions using provided metrics"""
        if not conditions:
            return True
        
        for condition in conditions:
            sensor = condition['sensor']
            operator = condition['is']
            target_value = condition['value']
            
            try:
                # Find the sensor value in the metrics
                current_value = None
                for metric_type, values in metrics.items():
                    if sensor in values:
                        current_value = values[sensor]
                        break
                
                if current_value is None:
                    print(f"Warning: Sensor '{sensor}' not found in metrics")
                    return False
                
                # Apply the condition
                if operator == "less than":
                    result = current_value < target_value
                elif operator == "greater than":
                    result = current_value > target_value
                else:
                    print(f"Warning: Unknown operator '{operator}'")
                    return False
                
                print(f"Condition check: {sensor} {operator} {target_value} -> {current_value} = {result}")
                if not result:
                    return False
                    
            except Exception as e:
                print(f"Error checking condition: {e}")
                return False
        
        return True
    
    def _execute_transition(self, trigger_name: str, transition_info: Dict[str, Any]):
        """Execute a transition"""
        try:
            # Get current metrics once for condition checking
            current_metrics = self.monitor_client.get_metrics()
            print(f"Fetched metrics: {current_metrics}")
            
            # Check conditions using the fetched metrics
            conditions = transition_info.get('conditions', [])
            conditions_met = self._check_conditions_with_metrics(conditions, current_metrics)
            
            # If conditions are met, execute the state transition
            if conditions_met:
                print(f"Conditions met! Transitioning from {transition_info['from']} to {transition_info['to']}")
                # Use pytransitions to change state
                self.machine.set_state(transition_info['to'])
                return True
            else:
                print(f"Conditions not met. Staying in state {transition_info['from']}")
                return False
            
        except Exception as e:
            print(f"Error executing transition {trigger_name}: {e}")
            return None
    

    



def demo_state_machine_with_monitor():
    """Demonstrate the state machine with MonitorClient integration"""
    print("=== State Machine with Monitor Integration Demo ===\n")
    
    # Create monitor server (for demo purposes)
    monitor_server = MetricsServer(cryostat_name='mycryo')
    
    # Create monitor client
    monitor_client = MonitorClient(url="http://localhost:8000", timeout=0.1)
    
    # Get the path to the TOML file
    toml_path = os.path.join(os.path.dirname(__file__), "state_machine_1k.toml")
    
    # Create state machine
    state_machine = ConfigurableStateMachine(toml_path, monitor_client)
    
    print(f"States: {state_machine.states}")
    print(f"Current state: {state_machine.state}")
    print(f"Available transitions: {state_machine.machine.get_triggers(state_machine.state)}\n")
    
    # Simulate some metric updates
    print("Updating metrics...")
    monitor_server.update_metric_values(
        metric_name='temperatures',
        new_values_dict={
            'heat_switch': 15.0,  # Below 20, should allow transition
            'pump': 30.0,         # Below 50, should allow transition
        }
    )
    
    # Try to execute transitions
    print("\nAttempting transitions...")
    
    # Get available transitions for current state
    current_state = state_machine.state
    available_triggers = state_machine.machine.get_triggers(current_state)
    
    for trigger in available_triggers:
        print(f"Trying trigger: {trigger}")
        try:
            # Execute the transition
            result = getattr(state_machine, trigger)()
            print(f"Transition result: {result}")
        except Exception as e:
            print(f"Error: {e}")
    
    print("\nDemo completed.")


if __name__ == "__main__":
    demo_state_machine_with_monitor()

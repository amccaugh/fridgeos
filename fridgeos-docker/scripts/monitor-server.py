#%%
from fridgeos.monitor.server import MonitorServer
from fridgeos.hal.client import HALClient
from fridgeos.statemachine.client import StateMachineClient
import random

# Create client instances
hal_client = HALClient(ip='hal', port=5555)
statemachine_client = StateMachineClient(ip='statemachine', port=5556)


class DummyHALClient:
    def get_temperatures(self):
        return {'T1': 1.23 + random.uniform(-0.1, 0.1), 'T2': 4.56 + random.uniform(-0.1, 0.1)}
    def get_heater_values(self):
        return {'H1': 0.1 + random.uniform(-0.1, 0.1), 'H2': 0.2 + random.uniform(-0.1, 0.1)}
    def get_heater_max_values(self):
        return {'H1': 1.0, 'H2': 1.0}

# Dummy StateMachineClient
class DummyStateMachineClient:
    def get_state(self):
        if random.random() < 0.5:
            return {'state': 'cold'}
        else:
            return {'state': 'warm'}

hal_client = DummyHALClient()
statemachine_client = DummyStateMachineClient()

monitor_server = MonitorServer(http_port=8000,
                               hal_client=hal_client,
                               statemachine_client=statemachine_client,
                               min_update_period=1)
# Now visit http://localhost:8000/ in your browser to see the metrics

# Start the monitoring loop
monitor_server.run()
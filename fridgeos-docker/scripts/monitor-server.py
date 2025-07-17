#%%
from fridgeos.monitor.server import MonitorServer


monitor_server = MonitorServer(http_port = 8000,
                               hal_ip = 'hal',
                               hal_port = 5555,
                               statemachine_ip = 'statemachine',
                               statemachine_port = 5556,
                               min_update_period = 1)
# Now visit http://localhost:8000/ in your browser to see the metrics
#%%
from fridgeos import MonitorServer
import tomllib

with open('./config/monitor.toml', "rb") as f:
    name = tomllib.load(f)['name']


monitor_server = MonitorServer(cryostat_name = name,
                               http_port = 8000,
                               hal_ip = 'hal',
                               hal_port = 5555,
                               statemachine_ip = 'statemachine',
                               statemachine_port = 5556,
                               min_update_period = 1)
# Now visit http://localhost:8000/ in your browser to see the metrics
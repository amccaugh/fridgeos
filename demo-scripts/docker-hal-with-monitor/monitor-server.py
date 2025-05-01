#%%
from fridgeos import MonitorServer


monitor_server = MonitorServer(cryostat_name = 'mycryo',
                               http_port = 8000,
                               hal_ip = 'hal',
                               hal_port = 5555,
                               min_update_period = 1)
# Now visit http://localhost:8000/ in your browser to see the metrics
#%%
from fridgeos import MonitorClient

monitor_client = MonitorClient(url = 'http://localhost:8000/', timeout = 0.1)
all_metrics = monitor_client.get_metrics()
temperatures = monitor_client.get_metrics('temperatures')
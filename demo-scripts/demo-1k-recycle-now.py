#%%
from fridgeos import MonitorClient, HALClient
import time
from simple_pid import PID
import numpy as np

hal_client = HALClient(ip = '127.0.0.1', port = '5555')
monitor_client = MonitorClient(url = 'http://localhost:8000/', timeout = 0.1)
metrics_dict = monitor_client.get_metrics()

heater_max_values = metrics_dict['heater_max_values']

pump_pid = PID(10, 0, 0, setpoint=50)
pump_pid.output_limits = (0, heater_max_values['1K-pump'])


metrics_dict = monitor_client.get_metrics()

print('Warming up')
# Heat up the pump
hal_client.set_heater_value('1K-switch', 0)
hal_client.set_heater_value('1K-pump', 25)
time_start=time.time()  # Start timer
while time.time()-time_start < 60*60:
    try:
        metrics_dict = monitor_client.get_metrics()
    except:
        pass
    temperatures = metrics_dict['temperatures']
    new_heater_value = pump_pid(temperatures['1K-pump'])
    hal_client.set_heater_value('1K-pump', new_heater_value)
    print(f'Setting 1K-pump to {new_heater_value}')
    print(f'1K temperature: {temperatures["1K"]}')
    time.sleep(60)

# Let pump cool down
print('Done heating pump, turning switch on')
hal_client.set_heater_value('1K-pump', 0)
hal_client.set_heater_value('1K-switch', 4)

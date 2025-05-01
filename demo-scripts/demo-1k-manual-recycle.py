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


#%%

def wait_until_hour(target_hour):
    while True:
        current_hour = time.localtime().tm_hour
        if current_hour == target_hour:
            break
        current_minute = time.localtime().tm_min
        print(f'Current hour: {current_hour} and minute: {current_minute}, waiting until {target_hour}')
        time.sleep(5*60)  # Check every minute

wait_until_hour(7)

# Heat up the pump
hal_client.set_heater_value('1K-switch', 0)
hal_client.set_heater_value('1K-pump', 25)
time.sleep(60*10)



metrics_dict = monitor_client.get_metrics()
temperatures = metrics_dict['temperatures']
# Heat pump to 50K until 1K stage is cold, turning off switch if it gets too hot
while temperatures['1K'] > 5:
    # If the switch is between 9-10K, scale down the pump heater value
    # switch_factor = np.clip(10-temperatures['1K-switch'], 0, 1)
    switch_factor = 1
    new_pid_heater_value = pump_pid(temperatures['1K-pump'])
    new_heater_value = new_pid_heater_value*switch_factor
    hal_client.set_heater_value('1K-pump', new_heater_value)
    print(f'Setting 1K-pump to {new_heater_value}')
    time.sleep(1)
    metrics_dict = monitor_client.get_metrics()
    temperatures = metrics_dict['temperatures']
    print(temperatures)

# Let pump cool down
print('Done heating pump, turning switch on')
hal_client.set_heater_value('1K-pump', 0)
hal_client.set_heater_value('1K-switch', 4)

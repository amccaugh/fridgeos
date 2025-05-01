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


def wait_until_hour(target_hour):
    while True:
        current_hour = time.localtime().tm_hour
        current_minute = time.localtime().tm_min
        print(f'Current hour: {current_hour} and minute: {current_minute}, waiting until {target_hour}')
        if current_hour == target_hour and current_minute < 30:
            break
        time.sleep(5*60)  # Check every 5 minutes
#%%

metrics_dict = monitor_client.get_metrics()

while True:
    wait_until_hour(7)
    print('It is time, warm it up')
    # Heat up the pump
    hal_client.set_heater_value('1K-switch', 0)
    hal_client.set_heater_value('1K-pump', 25)
    # time.sleep(60*90)
    time_start=time.time()  # Start timer
    while time.time()-time_start < 60*90:
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
    # temperatures = metrics_dict['temperatures']
    # # Heat pump to 50K until 1K stage is cold, turning off switch if it gets too hot
    # hal_client.set_heater_value('1K-switch', 0)
    # print(f'1K temperature: {temperatures["1K"]}')
    # while temperatures['1K'] > 4.75:
    #     print(f'Waiting for 1K t cool, current temperature: {temperatures["1K"]}')
    #     # If the switch is between 9-10K, scale down the pump heater value
    #     # switch_factor = np.clip(10-temperatures['1K-switch'], 0, 1)
    #     new_heater_value = pump_pid(temperatures['1K-pump'])
    #     hal_client.set_heater_value('1K-pump', new_heater_value)
    #     print(f'Setting 1K-pump to {new_heater_value}')
    #     time.sleep(30)
    #     try:
    #         metrics_dict = monitor_client.get_metrics()
    #     except:
    #         pass
    #     temperatures = metrics_dict['temperatures']

    # Let pump cool down
    print('Done heating pump, turning switch on')
    hal_client.set_heater_value('1K-pump', 0)
    hal_client.set_heater_value('1K-switch', 4)
    time.sleep(60)

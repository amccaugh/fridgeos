#%%
from fridgeos import HALClient

halclient = HALClient(ip = '127.0.0.1', port = 8001)
print(halclient.get_heater_values())
print(halclient.get_temperatures())
print(halclient.get_temperature('1K'))
print(halclient.set_heater_value('pump', 0.1))
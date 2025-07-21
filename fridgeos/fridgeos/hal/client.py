import fridgeos.zmqhelper as zmqhelper
import time
import json


class HALClient:
    def __init__(self, ip, port):
        self.connection = zmqhelper.Client(ip, port)

    def send_command(self, command, **kwargs):
        command_json = {"cmd": command}
        command_json.update(kwargs)
        message = json.dumps(command_json)
        response = self.connection.send_message(message)
        return json.loads(response)
    
    def get_temperatures(self):
        return self.send_command("get_temperatures")
    
    def get_temperature(self, name):
        return self.send_command("get_temperature", name = name)
    
    def set_heater_value(self, name, value):
        return self.send_command("set_heater_value", name = name, value = value)
    
    def get_heater_values(self):
        return self.send_command("get_heater_values")
    
    def get_heater_max_values(self):
        return self.send_command("get_heater_max_values")
    
if __name__ == "__main__":
    halclient = HALClient(ip = '127.0.0.1', port = '5555')
    halclient.get_temperatures()

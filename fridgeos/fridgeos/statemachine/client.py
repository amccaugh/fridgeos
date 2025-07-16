#%%
import fridgeos.zmqhelper as zmqhelper
import time
import json


class StateMachineClient:
    def __init__(self, ip, port):
        self.connection = zmqhelper.Client(ip, port)

    def send_command(self, command, **kwargs):
        command_json = {"cmd": command}
        command_json.update(kwargs)
        message = json.dumps(command_json)
        response = self.connection.send_message(message)
        return json.loads(response)
    
    def get_state(self):
        return self.send_command("get_state")
    
    def set_state(self, state):
        return self.send_command("set_state", state = state)
    
if __name__ == "__main__":
    state_machine_client = StateMachineClient(ip = '127.0.0.1', port = '5556')
    print(state_machine_client.get_state())
    print(state_machine_client.set_state('warm'))
    print(state_machine_client.set_state('ASDHFfjdhfafsj'))

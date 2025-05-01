#%%
from transitions import Machine
import random


# T4Ksetpt: 4.2
# T1Ksetpt: 2.8
# Tpump: 50
# T1Kfinal: 0.76
# Tpumpfinal: 6.7
# Tcheck: 0.76             #if the 1K sensor is below this temp the fridge does not recycle
# T1Khigh: 2
# Tswitch: 11

heaters = {
    "pump_heater": "Heater1",
}

criteria = {
    "pump_warming" :
        {
        "pump": 50,
        "1k": 0.1,
        },
    "heat_switch_cooling" :
        {
        "pump": 50,
        "switch": 11,
        },
}


class DummyHALClient:
    def send(self, message_dict):
        if message_dict['cmd'] == "get_temperatures":
            data = {
                "4k": 0.0,
                "1k": 0.0,
                "40k": 0.0,
            }
            return data
        elif message_dict['set_heater_value']:
            print(f"Setting heater {message_dict['name']} to {message_dict['value']}")

client = DummyHALClient()

class FridgeController1K:
    def __init__(self):
        pass

    def enable(self, heater):
        print("Enabling heater: ", heater)
        # client.send(

    def check_temperature_criteria(self):
        temperatures = client.send({"cmd": "get_temperatures"})
        for name, temp in criteria.items():
            if temperatures[name] > temp:
                return True
        temperatures['1k'] > criteria['1k']
    
    def on_enter_pump_warming(self):
        self.enable['pump_heater']
        print("Entered pump_warming state")

    # def advance_to_next_state(self):
    #     print("Advancing to next state")

#
# Initialize the state machine
fridge = FridgeController1K()
states = ['warm', 'heat_switch_cooling', 'pump_warming', 'cold', 'warming_up']
machine = Machine(model=fridge, states=states, initial='heat_switch_cooling')

# Advance from heat_switch_cooling to pump_warming only if we've satisfied the condition
# that we've reached our temperature criteria of interest.  
machine.add_transition(trigger='advance_to_next_state', source='heat_switch_cooling', dest='pump_warming',
                        conditions = 'check_temperature_criteria')
 # Internal transition; no state change; will not execute on_enter_heat_switch_cooling
machine.add_transition(trigger='advance_to_next_state', source='heat_switch_cooling', dest=None)


machine.add_transition(trigger='advance_to_next_state', source='pump_warming', dest='cooling',
                        conditions = 'check_temperature_criteria')
 # Internal transition; no state change; will not execute on_enter_heat_switch_cooling
machine.add_transition(trigger='advance_to_next_state', source='pump_warming', dest=None)



while True:
    fridge.advance_to_next_state()
    fridge.update_pid()
    if message is 'recycle':
        fridge.go_to_state('heat_switch_cooling')


#%%



# class FridgeController:

#     # Define some states. Most of the time, narcoleptic superheroes are just like
#     # everyone else. Except for...
#     

#     def __init__(self):

    #     # Superheroes need to keep in shape.
    #     machine.add_transition('work_out', 'hanging out', 'hungry')

    #     # Those calories won't replenish themselves!
    #     self.machine.add_transition('eat', 'hungry', 'hanging out')

    #     # Superheroes are always on call. ALWAYS. But they're not always
    #     # dressed in work-appropriate clothing.
    #     self.machine.add_transition('distress_call', '*', 'saving the world',
    #                      before='change_into_super_secret_costume')

    #     # When they get off work, they're all sweaty and disgusting. But before
    #     # they do anything else, they have to meticulously log their latest
    #     # escapades. Because the legal department says so.
    #     self.machine.add_transition('complete_mission', 'saving the world', 'sweaty',
    #                      after='update_journal')

    #     # Sweat is a disorder that can be remedied with water.
    #     # Unless you've had a particularly long day, in which case... bed time!
    #     self.machine.add_transition('clean_up', 'sweaty', 'asleep', conditions=['is_exhausted'])
    #     self.machine.add_transition('clean_up', 'sweaty', 'hanging out')

    #     # Our NarcolepticSuperhero can fall asleep at pretty much any time.
    #     self.machine.add_transition('nap', '*', 'asleep')

    # def update_journal(self):
    #     """ Dear Diary, today I saved Mr. Whiskers. Again. """
    #     self.kittens_rescued += 1

    # @property
    # def is_exhausted(self):
    #     """ Basically a coin toss. """
    #     return random.random() < 0.5

    # def change_into_super_secret_costume(self):
    #     print("Beauty, eh?")
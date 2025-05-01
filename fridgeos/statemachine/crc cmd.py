# -*- coding: utf-8 -*-
"""
Created on Wed Sep 11 12:25:56 2024

@author: Ryan Morgenstern @ NIST
"""
#%%
from statemachine import State, StateMachine
from statemachine.contrib.diagram import DotGraphMachine
import asyncio
import json
import time
import requests
import tomllib
import fridgeos.zmqhelper as zmqh

#from timer import ElapsedTime
from simple_pid import PID

class crc_cmd(StateMachine):
    def __init__(self, settings_toml, hal_client, monitor_client):
        # Add ZMQ connection - HAL Client
        self.hal_client = hal_client
        # Add html scrapper - Monitor Client
        self.monitor_client = monitor_client
        # Import settings from toml file
        with open(f'{settings_toml}', "rb") as f:
            self.sm_settings = tomllib.load(f)
        
        # Keep track of time when we enter states. It is set on_entry into new state
        self.enter_state_time = 0
        #Check if just entered state
        self.just_entered = False
        # Controls if the state machine is running (Must call start_state_machine() )
        self.cycle_running = False
        # Time.sleep before state is ran again
        self.state_machine_cycle_time = self.sm_settings['misc']['state_machine_cycle_time'] #seconds
        # Holds all fridge data from metric server. refreshed every state_machine_cycle_time
        self.fridge_state = {}
        self.fridge_timer = ElapsedTime()
        self.dt = 0
        # Varaible for when the still stays activated and not turned off for PID control
        self.still_activated = False
        # The current_cycle will be defined when entering eithe the start_cycle_A or start_cycle_B state. It's used to leave turn_on_still_heater state to the appropriate cycle
        self.current_cycle = None
        # PID controller setup
        self.pid = {}
        # Get max values of HAL TOML hardware by grabbing metric server data
        self.update_fridge_state()
        self.setup_pids()
        self.currently_in_use_pids = {}
        self.time_elapse_dict = {}
        super().__init__()
        # Allows states to move on without transition (required dont touch)
        self.allow_event_without_transition = 1

    def setup_pids(self):
        for key,values in self.sm_settings['pid_configuration'].items():
            max_value = self.fridge_state['heater_max_values'][key]
            self.pid[key] = PID(Kp = values['kp'], 
                                        Kd = values['kd'],
                                        Ki = values['ki'],
                                        sample_time=None,
                                        output_limits = (0, max_value))
            
    #-----------------------------------------------------------------------------------------------------#
    #                                    Defining states of state machine
    #-----------------------------------------------------------------------------------------------------#
    # Wait for the compressor to cool the the heat switches to below < 12K before starting state machine
    wait_for_heat_switches_to_cool = State(name = 'Waiting for heat switches to cool < 12K' , initial = True, value = 1)
    #-----------------------------------------------------------------------------------------------------#
    # Turn on all pumps and regulate to 45K to release He3 & He4 till head temperatures are < 4.1K
    turn_on_all_pumps = State(name = 'Cooling heads < 4K', value = 2)
    #-----------------------------------------------------------------------------------------------------#
    # Cool down the He4 Heads by turning off 4 pump A & B and turning on 4 switch A & B
    turn_on_4_heat_switches = State(name = 'Cooling He4 Heads A & B', value = 3)
    #-----------------------------------------------------------------------------------------------------#
    # Cooldown the He3 heads by turning off 3 pump A & B and turning on 3 switch A & B
    turn_on_3_heat_switches = State(name = 'Cooling He3 Heads A & B', value = 4)
    #-----------------------------------------------------------------------------------------------------#
    # Prepare cycle A by turning off 3 & 4 heat switch A.  Check that they are 0V / Dac value and let them cool < 12K.
    start_cycle_A = State(name = 'Starting Cycle A', value = 5)
    #-----------------------------------------------------------------------------------------------------#
    # I believe this state was added to not thermally shock the system when heating to 45K. 
    get_pumps_warm_A = State(name = 'Warming 3 & 4 A pumps', value = 6)
    #-----------------------------------------------------------------------------------------------------#
    # Turn on 3 & 4 pumps A for a period of time "30*60*1000" and if "cold" line 557 s_m.js
    get_pumps_hot_A = State(name = 'Getting 3 & 4 A pumps hot', value = 7)
    #-----------------------------------------------------------------------------------------------------#
    # Turn on heat switch 4A to cool down 4 head A, check if (3HeadA < 6 & 4HeadA < 1) or 40*60*1000 elapsedtime
    turn_on_heat_switch_4_A = State(name = 'Turn on heat switch 4 A', value = 8)
    #-----------------------------------------------------------------------------------------------------#
    # Turn off 3pumpA and turn on heat switch 3 A. Wait for elapse time
    turn_on_heat_switch_3_A = State(name = 'Turn on heat switch 3 A', value = 9)
    #-----------------------------------------------------------------------------------------------------#
    # Start cycle B by turning off 3 & 4 heat switch B and check that they are 0V / Dac value. Let them cool < 12K
    start_cycle_B = State(name = 'Starting Cycle B', value = 10)
    #-----------------------------------------------------------------------------------------------------#
    # I believe this state was added to not thermally shock the system when heating to 45K. 
    get_pumps_warm_B = State(name = 'Warming 3 & 4 B pumps', value = 11)
    #-----------------------------------------------------------------------------------------------------#
    # Turn on pumps 3 & 4 B to 45K for a period of time and untii 3 and 4 head times less than 6K & 4K
    get_pumps_hot_B = State(name = 'Getting 3 & 4 B pumps hot', value = 12)
    #-----------------------------------------------------------------------------------------------------#
    # Turn on heat switch 4 B to cool down 4 head B, check if (3HeadB < 6 & 4HeadB < 1) or 40*60*1000 elapsedtime
    turn_on_heat_switch_4_B = State(name ='Turn on heat switch 4 B', value = 13)
    #-----------------------------------------------------------------------------------------------------#
    # Turn off 3pumpB and turn on heat switch 3 B. Wait for elapse time
    turn_on_heat_switch_3_B = State(name = 'Turn on heat switch 3 B', value = 14)
    #-----------------------------------------------------------------------------------------------------#
    # Once cold still is below 400mK & Dhead < 600mK, start dilution module
    turn_on_still_heater = State(name = 'Turn on still heater', value = 15)
    #-----------------------------------------------------------------------------------------------------#
    # To speed up system warm up, turning on the heat switches to thermally connect the whole system & HPHs
    # Also turn off still heater? maybe keep it on to warm up still faster... It jsut wont cycle heilum bc not super fluid
    warm_up_system = State(name = 'Warming up system', value = 16, final = True)
    #-----------------------------------------------------------------------------------------------------#
    
   
    #-----------------------------------------------------------------------------------------------------#
    #                               Defining transitions between states
    #-----------------------------------------------------------------------------------------------------#
    # Normal DR cycle between states
    cycle = (
        wait_for_heat_switches_to_cool.to(turn_on_all_pumps, cond = 'wait_for_heat_switches_to_cool_cond')    | 
        turn_on_all_pumps.to(turn_on_4_heat_switches, cond = 'turn_on_all_pumps_cond')                        |
        turn_on_4_heat_switches.to(turn_on_3_heat_switches, cond = 'turn_on_4_heat_switches_cond')            |
        turn_on_3_heat_switches.to(start_cycle_A, cond = 'turn_on_3_heat_switches_cond')                      |

        start_cycle_A.to(get_pumps_warm_A, cond = 'start_cycle_A_cond')                                       |
        get_pumps_warm_A.to(get_pumps_hot_A, cond = 'get_pumps_warm_A_cond')                                  |
        get_pumps_hot_A.to(turn_on_heat_switch_4_A, cond ='get_pumps_hot_A_cond')                             |
        turn_on_heat_switch_4_A.to(turn_on_heat_switch_3_A, cond = 'turn_on_heat_switch_4_A_cond')            |
        turn_on_heat_switch_3_A.to(turn_on_still_heater, cond = 'dilution_cond')                              |
        turn_on_heat_switch_3_A.to(start_cycle_B, cond = 'turn_on_heat_switch_3_A_cond')                      |
        turn_on_still_heater.to(start_cycle_B, cond = 'still_heater_cond_B')                                  |

        start_cycle_B.to(get_pumps_warm_B, cond = 'start_cycle_B_cond')                                       |
        get_pumps_warm_B.to(get_pumps_hot_B, cond = 'get_pumps_warm_B_cond')                                  |
        get_pumps_hot_B.to(turn_on_heat_switch_4_B, cond = 'get_pumps_hot_B_cond')                            |
        turn_on_heat_switch_4_B.to(turn_on_heat_switch_3_B, cond = 'turn_on_heat_switch_4_B_cond')            |
        turn_on_heat_switch_3_B.to(turn_on_still_heater, cond = 'dilution_cond')                              |
        turn_on_heat_switch_3_B.to(start_cycle_A, cond = 'turn_on_heat_switch_3_B_cond')                      |           
        turn_on_still_heater.to(start_cycle_A, cond = 'still_heater_cond_A') |

        start_cycle_A.to(warm_up_system, cond = 'warm_up_system_cond')
        )

    #-----------------------------------------------------------------------------------------------------#
    #        Condition Functions - These determine if the state can transition to the next State          #
    #-----------------------------------------------------------------------------------------------------#
    
    def wait_for_heat_switches_to_cool_cond(self):
        # Goals
        # Check if Switches are below 7K and 4K is below 5Kelvin
        return self.check_temperature_criteria(self.current_state.id) 
    def turn_on_all_pumps_cond(self):
        # Goals
        # Check if all heads are below 6K
        return self.check_temperature_criteria(self.current_state.id) 
    
    def turn_on_4_heat_switches_cond(self):
        # Goals
        # Check if both 3Heads are below 1.55K
        return self.check_temperature_criteria(self.current_state.id) 
    
    def turn_on_3_heat_switches_cond(self):
        # Goals 
        # Check if 3Head PID timers passed their max elapsed time
        return self.timer_check()

    def start_cycle_A_cond(self):
        # Goals
        # Check if 4 & 3 Switch A are below 12K to start A pumps
        return self.check_temperature_criteria(self.current_state.id) 
        
    def get_pumps_warm_A_cond(self):
        # Goals
        # Checks timers for warming 4PUMPA and 3PUMPA            
        return self.timer_check()
    
    def get_pumps_hot_A_cond(self):
        # Goals
        # Checks 4PUMPA timer to see if it has passed
        return self.timer_check()
    
    def turn_on_heat_switch_4_A_cond(self):
        # Goals
        # Check if 4HEADA < 1K and 3HEADA < 6K or if 3UPMPA elapsed time has passed
        if self.check_temperature_criteria(self.current_state.id):
            return True
        elif self.timer_check():
            return True
        else:
            return False
        
    def turn_on_heat_switch_3_A_cond(self):
        # Goals
        # Check if 3SWITCHA & 4SWITCHA timers have passed
        return self.timer_check()
    
    def start_cycle_B_cond(self):
        # Goals
        # Check if 4 & 3 Switch B are below 12K to start B pumps
        return self.check_temperature_criteria(self.current_state.id)

    def get_pumps_warm_B_cond(self):
        # Goals
        # Checks timers for warming 4PUMPB and 3PUMPB
        return self.timer_check()

    def get_pumps_hot_B_cond(self):
        # Goals
        # Checks 4PUMPB timer to see if it has passed
        return self.timer_check()

    def turn_on_heat_switch_4_B_cond(self):
        # Goals
        # Check if 4HEADB < 1K and 3HEADB < 6K or if 3UPMPB elapsed time has passed
        if self.check_temperature_criteria(self.current_state.id):
            return True
        elif self.timer_check():
            return True
        else:
            return False
    def turn_on_heat_switch_3_B_cond(self):
        # Goals
        # Check if 3SWITCHB & 4SWITCHB timers have passed
        return self.timer_check()
    
    def dilution_cond(self):
        # Goals
        # Check if Still temperature < 400mK and Dhead is < 600mK. If self.still_activated == True, then return False and dont go back into the still_heater state
        if self.still_activated == True:
            return False
        return self.check_temperature_criteria(self.current_state.id)
    
    def still_heater_cond_A(self):
        # Goals
        # Checks self.current_cycle to direct still_heater state to either start_cycle_A or start_cycle_B
        if self.current_cycle == 'A':
            return False
        elif self.current_cycle == 'B':
            return True

    def still_heater_cond_B(self):
        # Goals
        # Checks self.current_cycle to direct still_heater state to either start_cycle_A or start_cycle_B
        if self.current_cycle == 'A':
            return True
        elif self.current_cycle == 'B':
            return False
    def warm_up_system_cond(self):
        return False
    #-----------------------------------------------------------------------------------------------------#
    #        On-entry functions - These are the functions/tasks that are executed on entry into a state.  #
    #-----------------------------------------------------------------------------------------------------#  
    #   
    # Initial on_enter functions
    def on_enter_wait_for_heat_switches_to_cool(self):
        print('on_enter: Waiting for all heat switches < 12K & 4K stage < 5K', f'{self.log_time()}')
        self.run_per_state()
    def on_enter_turn_on_all_pumps(self):
        self.run_per_state()
        print('on_enter: Turning on all Pumps', f'{self.log_time()}')
    def on_enter_turn_on_4_heat_switches(self):
        self.run_per_state()
        print('on_enter: Turning on 4HeatSwitches A & B and Turning on 4PUMP A & B', f'{self.log_time()}')
    def on_enter_turn_on_3_heat_switches(self):
        self.run_per_state()
        print('on_enter: Turning on 3HeatSwitches A & B and Turning on 3PUMP A & B', f'{self.log_time()}')

    # Cycle A on_enter functions
    def on_enter_start_cycle_A(self):
        self.run_per_state()
        print('on_enter: Starting cycle He3 & He4 A cycle. Waiting for 4 & 3 SWITCH A < 12K', f'{self.log_time()}')
        self.current_cycle = 'A'
    def on_enter_get_pumps_warm_A(self):
        self.run_per_state()
        print('on_enter: Warming 4PUMPA & 3PUMPA to TOML set value', f'{self.log_time()}')
    def on_enter_get_pumps_hot_A(self):
        self.run_per_state()
        print('on_enter: Heating 4PUMPA & 3PUMPA to 45K', f'{self.log_time()}')
    def on_enter_turn_on_heat_switch_4_A(self):
        self.run_per_state()
        print('on_enter: Turning off 4PUMPA & turning on 4SWITCHA', f'{self.log_time()}\n')
        print('Waiting for 4HEADA < 1K and 3HEADA < 6K or if 3PUMPA elapsed time has passed', f'{self.log_time()}')
    def on_enter_turn_on_heat_switch_3_A(self):
        self.run_per_state()
        print('on_enter: Turning off 3PUMPA & turning on 3SWITCHA', f'{self.log_time()}\n')
        print('Checking if Still < 400mK and Dhead < 600mK', f'{self.log_time()}\n')
        print('or ...Waiting on 3SWITCHA elapse timers', f'{self.log_time()}')

    # Cycle B on_enter functions
    def on_enter_start_cycle_B(self):
        self.run_per_state()
        print('on_enter: Starting cycle He3 & He4 B cycle. Waiting for 4 & 3 SWITCH B < 12K ', f'{self.log_time()}')
        self.current_cycle = 'B'
    def on_enter_get_pumps_warm_B(self):
        self.run_per_state()
        print('on_enter: Warming 4PUMPB & 3PUMPB to TOML set value', f'{self.log_time()}')
    def on_enter_get_pumps_hot_B(self):
        self.run_per_state()
        print('on_enter: Heating 4PUMPB & 3PUMPB to 45K', f'{self.log_time()}')
    def on_enter_turn_on_heat_switch_4_B(self):
        self.run_per_state()
        print('on_enter: Turning off 4PUMPB & turning on 4SWITCHB', f'{self.log_time()}\n')
        print('Waiting for 4HEADB < 1K and 3HEADB < 6K or if 3PUMPB elapsed time has passed', f'{self.log_time()}')
    def on_enter_turn_on_heat_switch_3_B(self):
        self.run_per_state()
        print('on_enter: Turning off 3PUMPB & turning on 3SWITCHB', f'{self.log_time()}\n')
        print('Checking if Still < 400mK and Dhead < 600mK', f'{self.log_time()}\n')
        print('or... Waiting on 3SWITCHB elapse timers', f'{self.log_time()}')

    # Dilution on_enter function
    def on_enter_dilution(self):
        self.run_per_state()
        self.still_activated = True
        print('on_enter: Starting Dilution cycle. Turning on Still heater', f'{self.log_time()}')

    
    
      #-----------------------------------------------------------------------------------------------------#
    #                                   functions used for grabbing data                                  #
    #-----------------------------------------------------------------------------------------------------#

    # This grabs values of nested sensor_keys from a specific dictionary key
    def get_values_from_keys(self,key, sensor_keys, data_json):
        results = {}
        for sensor in sensor_keys:
            if sensor in data_json[f'{key}']:
                results[sensor] = data_json[f'{key}'][sensor]
        return results
    
    # This function will call the query metric server and return only the temperature of the sensors
    def get_temperature(self, sensors):
        data = self.monitor_client.get_metrics()
        return self.get_values_from_keys(sensor_keys = sensors, data_json = data, key = 'temperatures')
    
    # This function will call the query metric server and return only the heater values
    def get_heater_value(self, heater):
        data = self.monitor_client.get_metrics()
        return self.get_values_from_keys(sensor_keys= heater, data_json = data, key = 'heaters')

    #-----------------------------------------------------------------------------------------------------#
    #                      Action functions used to communicate with HAL.                                 #
    #-----------------------------------------------------------------------------------------------------#
    
    def set_heater_value(self, heater, value):
        response = self.hal_client.set_heater_value(f'{heater}', f'{value}')
        return response

    #-----------------------------------------------------------------------------------------------------#
    # Async functions for the state machine
    #------------------------------------------------------------------------------------------------------#
    async def turn_on_state_machine(self):
        # Starts state machine cycle
        self.cycle_running = True
        await self.run_cycle()
    async def turn_off_state_machine(self):
        # Stops state machine cycle
        self.cycle_running = False
    async def run_cycle(self):
        # Loop which runs the state machine
        while self.cycle_running:
            # Update the temperatures inside the state machine
            self.update_fridge_state()
            # Run the state machine to check if we should move to the next state or not
            # If we move to a new state, update the list of currently-in-use PIDs
            self.cycle()
            # Scan through the list of currently-in-use PIDs and update their setpoints
            self.update_pid_values()
            await asyncio.sleep(self.state_machine_cycle_time)
    
    def non_async__turn_on_state_machine(self):
        # Starts state machine cycle
        self.cycle_running = True
        self.non_async_run_cycle()
    def non_async__turn_off_state_machine(self):    
        # Stops state machine cycle
        self.cycle_running = False
    def non_async_run_cycle(self):
            while self.cycle_running:
                # Update the temperatures inside the state machine
                self.update_fridge_state()
                # Run the state machine to check if we should move to the next state or not
                # If we move to a new state, update the list of currently-in-use PIDs
                self.cycle()
                # Scan through the list of currently-in-use PIDs and update their setpoints
                self.update_pid_values()
                time.sleep(self.state_machine_cycle_time)
    #------------------------------------------------------------------------------------------------------#
    #                                       Misc functions for the state machine
    #------------------------------------------------------------------------------------------------------#
    def update_fridge_state(self):
        #self.fridge_state = self.query_metric_server()
        fridge_data, success = self.monitor_client.get_metrics()
        if success:
            self.fridge_state = fridge_data
        elif not success:
            print('Failed to get fridge state from monitor server')
        self.dt = self.fridge_timer()[1]
        self.fridge_timer.reset()

    def update_pid_values(self):
    # Update the setpoints of all PIDs in the list of currently-in-use PIDs
        #print('Updating PID values and sending to HAL')
        for pid_key in self.currently_in_use_pids:
            # Get current temperature of key
            current_value = self.fridge_state['temperatures'][pid_key]
            # Define state machine setpoint of key Ex 4PUMP @ 45K
            setpoint = self.currently_in_use_pids[pid_key]
            # Update PID setpoint
            self.pid[pid_key].setpoint = setpoint
            # Get new value from PID
            new_value = self.pid[pid_key](input_ = current_value, dt = self.dt)
            # Send new value to HAL
            #print('Current Temp =',current_value ,'Setting', pid_key, 'to', new_value, 'with dt =', self.dt)
            self.set_heater_value(heater = pid_key, value = new_value)

    # Checks temperature of fridge and returns True if all temperatures are below the threshold
    def check_temperature_criteria(self, state, excluded_variable = None):
        threshold_temps = self.sm_settings[f'{state}']['temperature_thresholds']
        current_temps = self.fridge_state['temperatures']
        # Filters current_temps to only include keys that are in threshold_temps
        filtered_current_data = {key: current_temps[key] for key in threshold_temps if key in current_temps}
        # Exclude a specific variable from the check
        if all(filtered_current_data[thermometer] < threshold_temps[thermometer] 
               for thermometer in threshold_temps if thermometer != excluded_variable):
            return True
        else:
            return False
    def check_temperature_criteria_sensor(self, sensor):
        # Get the temperature of the sensor
        current_temp = self.fridge_state['temperatures'][sensor]
        # Get the threshold for the sensor
        state = self.current_state.id
        threshold_temp = self.sm_settings[f'{state}']['temperature_thresholds'][sensor]
        # Check if the current temperature is below the threshold
        if current_temp < threshold_temp:
            return True
        else:
            return False
    # This will find the heaters and switches that contain 'pid_set_value' in their subkey. 
    # It is only called on entry to make self.currently_in_use_pids
    def find_sub_subkey(self, state, sub_subkey):
        """
        Find all subkeys and their values where the given sub-subkey exists in a nested dictionary.

        Parameters:
        - data (dict): The main dictionary with nested structures.
        - sub_subkey (str): The sub-subkey to search for.

        Returns:
        - dict: A dictionary of subkeys and their values where the sub-subkey exists.
        """
        data = self.sm_settings[f'{state}']
        result = {}

        for key, subkeys in data.items():
            # Ensure subkeys is a dictionary
            if isinstance(subkeys, dict):
                for subkey, subvalue in subkeys.items():
                    # Check if the subvalue is a dictionary and contains the sub-subkey
                    if isinstance(subvalue, dict) and sub_subkey in subvalue:
                        result[subkey] = subvalue[sub_subkey]

        return result
    #Makes timer objects
    def make_timers(self, dict_of_timers):
        for key, value in dict_of_timers.items():
            self.time_elapse_dict[key] = ElapsedTime(value)
            
    #Function for cycling through timers and checking if true
    def timer_check(self):
        for key in self.time_elapse_dict:
            #Check if time passed is true
            #EDIT ME I remove [0]
            if self.time_elapse_dict[key]()[0]:
                return True
        return False

    # Function used for keeping track of time in the state
    # EDIT ME
    def check_just_entered(self):
        if self.just_entered:
            self.just_entered = False
            self.enterStateTime = time.time()
            #Console / logging stuff
            return True
        else:
            return False

    def turn_off_not_in_use_pids(self):
        for key in self.pid:
            # Skip STILLHEATER if still_activated is True
            if key == "STILLHEATER" and self.still_activated:
                continue
            if key not in self.currently_in_use_pids.keys():
                print('Turning off', key)
                self.set_heater_value(key, 0)

    def run_per_state(self):
        # Resets time_elapse_dict
        self.time_elapse_dict = {}
        # Save STILLHEATER PID if it exists
        saved_pid_key = self.currently_in_use_pids.get('STILLHEATER')
        # Clear all PIDs
        self.currently_in_use_pids = {}
        # Restore STILLHEATER PID if it was saved
        if saved_pid_key is not None:
            self.currently_in_use_pids['STILLHEATER'] = saved_pid_key
        # Get new PIDs from state machine settings
        new_pids = self.find_sub_subkey(self.current_state.id, sub_subkey = 'pid_set_value')
        # Update the dictionary without overwriting STILLHEATER
        for key, value in new_pids.items():
            if key != 'STILLHEATER' or 'STILLHEATER' not in self.currently_in_use_pids:
                self.currently_in_use_pids[key] = value
        # Sets up elapse time objects
        self.dict_to_turn_into_timers = self.find_sub_subkey(self.current_state.id, sub_subkey = 'elapse_time_max')
        self.make_timers(self.dict_to_turn_into_timers)
        self.turn_off_not_in_use_pids()
        # EDIT ME 
        self.check_just_entered()

    def log_time(self):
        date = time.localtime()
        log_time = f'{date.tm_year}-{date.tm_mon}-{date.tm_mday} {date.tm_hour}:{date.tm_min}:{date.tm_sec}'
        return log_time

class ElapsedTime:
    def __init__(self, threshold_seconds=None):
        """
        Initialize the ElapsedTime object.
    

        Parameters:
        - threshold_seconds (float, optional): The time threshold in seconds.
          If None, threshold checks will not be performed.
        """
        self.threshold_seconds = threshold_seconds
        self.start_time = time.time()

    def reset(self):
        """
        Reset the timer.
        """
        self.start_time = time.time()

    def __call__(self):
        """
        Check if the elapsed time exceeds the optional threshold and return elapsed time.

        Returns:
        - (bool or None, float): A tuple containing:
            - bool: True if elapsed time exceeds the threshold, False otherwise. 
                    If no threshold is provided, this is None.
            - float: Elapsed time in seconds since the timer was started.
        """
        elapsed_time = time.time() - self.start_time

        # Check if threshold_seconds is provided
        if self.threshold_seconds is None:
            return None, elapsed_time
        
        return elapsed_time >= self.threshold_seconds, elapsed_time

    def time_remaining(self):
        """
        Get the remaining time until the threshold is reached.

        Returns:
        - float or None: Time remaining in seconds. 
                         If the threshold is exceeded, returns 0.
                         If no threshold is set, returns None.
        """
        if self.threshold_seconds is None:
            return None

        elapsed = time.time() - self.start_time
        return max(0, self.threshold_seconds - elapsed)
        
    
#%%
graph = DotGraphMachine(crc_cmd)  # also accepts instances

dot = graph()

dot.to_string()  

dot.write_png(fr'C:\Users\rdm8\Downloads\test.png')
 

    
#%%

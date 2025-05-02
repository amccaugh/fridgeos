# %%
from statemachine import State, StateMachine
#from statemachine.contrib.diagram import DotGraphMachine
import json
import time
import requests
import tomllib
import fridgeos.zmqhelper as zmqh
from simple_pid import PID

class Single_shot_1k(StateMachine):
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
        self.just_entered = True
        # Controls if the state machine is running (Must call start_state_machine() )
        self.cycle_running = False
        # Time.sleep before state is ran again
        self.state_machine_cycle_time = self.sm_settings['misc']['state_machine_cycle_time'] #seconds
        # Holds all fridge data from metric server. refreshed every state_machine_cycle_time
        self.fridge_state = {}
        self.fridge_timer = ElapsedTime()
        self.dt = 0
        # Clock recycle bool to sotp pre_cool from going bac into head_cold
        # I dont think This ever needs to be false other than first start up...
        self.clock_recycle = False
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
    # Non-Async functions for starting the state machine & main cycle
    #------------------------------------------------------------------------------------------------------#
    def turn_on_state_machine(self):
        # Starts state machine cycle
        self.cycle_running = True
        self.run_cycle()
    def turn_off_state_machine(self):    
        # Stops state machine cycle
        self.cycle_running = False
    def run_cycle(self):
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
    # EDIT ME Add console / logging stuff
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
            if key not in self.currently_in_use_pids.keys():
                print('Turning off', key)
                self.set_heater_value(key, 0)

    def run_per_state(self):
        # Resets time_elapse_dict
        self.time_elapse_dict = {}
        # Resets currently in use PIDs
        self.currently_in_use_pids = {}
        # Rebuilds currently in use PIDs from the state machine settings
        self.currently_in_use_pids = self.find_sub_subkey(self.current_state.id, sub_subkey = 'pid_set_value')
        # Sets up elapse time objects
        self.dict_to_turn_into_timers = self.find_sub_subkey(self.current_state.id, sub_subkey = 'elapse_time_max')
        self.make_timers(self.dict_to_turn_into_timers)


        # EDIT ME 
        self.check_just_entered
        self.turn_off_not_in_use_pids()

    def log_time(self):
        date = time.localtime()
        log_time = f'{date.tm_year}-{date.tm_mon}-{date.tm_mday} {date.tm_hour}:{date.tm_min}:{date.tm_sec}'
        return log_time
    #-----------------------------------------------------------------------------------------------------#
    #                                    Defining states of state machine
    #-----------------------------------------------------------------------------------------------------#
    # Wait for the cryocooler to cool down 4K to below 4.1K
    pre_cool = State(name = 'Precooling 4K to below 4.1K' , initial = True, value = 1)
    #-----------------------------------------------------------------------------------------------------#
    # Prepare cycle by turning off pumps and switches
    # Wait for the compressor to cool the heat switch to below < 10K before starting state machine
    start_recycle = State(name = 'Turning off switches & pumps and waiting for 4heat switch too cool below 10K', value = 2)
    #-----------------------------------------------------------------------------------------------------#
    # I believe this state was added to not thermally shock the system when heating to 45K. 
    get_pump_warm = State(name = 'Warming 4pump to 25K to not thermal shock system', value = 3)
    #-----------------------------------------------------------------------------------------------------#
    # Turn on 4 pumps for a period of time "30*60*1000" or if 4head < 3K #EDIT ME -> change time 
    get_pump_hot = State(name = 'warming 4pump to 45K', value = 4)
    #-----------------------------------------------------------------------------------------------------#
    # Turn off 4pump 
    turn_off_pump = State(name = 'Turning off 4pump', value = 5)
    #-----------------------------------------------------------------------------------------------------#
    # Turn on heat switch 4 to cool down 4 head, 
    turn_on_heat_switch_4 = State(name = 'Turning on 4switch and cooling down', value = 6)
    #-----------------------------------------------------------------------------------------------------#
    # Confirm state of 4head being <1K
    head_cold = State(name = '4head is below 1K', value =7)
    #-----------------------------------------------------------------------------------------------------#
    # To speed up system warm up, turning on the heat switches to thermally connect the whole system & HPHs
    # Also turn off still heater? maybe keep it on to warm up still faster... It jsut wont cycle heilum bc not super fluid
    warm_up_system = State(name = 'Warming up system', value = 8, final = True)
    #-----------------------------------------------------------------------------------------------------#
    
    #-----------------------------------------------------------------------------------------------------#
    #                               Defining transitions between s•••••••••••tates
    #-----------------------------------------------------------------------------------------------------#
    # Normal 1K cycle between states
    cycle = (
        pre_cool.to(head_cold, cond = 'already_cold_cond')                |
        pre_cool.to(start_recycle, cond = 'pre_cool_cond')                | 
        start_recycle.to(get_pump_warm, cond = 'start_recycle_cond')      |
        get_pump_warm.to(get_pump_hot, cond = 'pump_warm_cond')           |
        get_pump_hot.to(turn_off_pump, cond = 'pump_hot_cond' )           |
        turn_off_pump.to(turn_on_heat_switch_4, cond = 'pump_off_cond')   |
        turn_on_heat_switch_4.to(head_cold, cond = 'heat_switch_on_cond') |
        turn_on_heat_switch_4.to(pre_cool, cond = 'head_not_cooling_cond')|
        head_cold.to(pre_cool, cond = 'head_cold_recycle_cond')           |
        head_cold.to(warm_up_system, cond = 'stop_func')                             
    )    
    #-----------------------------------------------------------------------------------------------------#
    #        Condition Functions - These determine if the state can transition to the next State          #
    #-----------------------------------------------------------------------------------------------------#
    def pre_cool_cond(self):
        # Goals
        # Check if 4K stage is < 4.1K
        #print('checking mainplate', flush = True)
        return self.check_temperature_criteria(self.current_state.id, excluded_variable= '4HEAD')    
    def already_cold_cond(self):
        # Check if 1K head is already cold
        #print('checking 4head', flush = True)
        if self.clock_recycle == False:
            return self.check_temperature_criteria_sensor(sensor = '4HEAD')
    def start_recycle_cond(self):
        # Goals
        # Make sure pump and switch is off before starting cycle
        # Check if heat switch is less than 10K 
        return self.check_temperature_criteria(self.current_state.id)       
    def pump_warm_cond(self):
        # PD warming slowly to 45K to thermall shock system (too much heat too fast causing overshoot)
        return self.timer_check()
    def pump_hot_cond(self):
        # PD controling at 45K. PD called on entery of state
        # Once 4head is below 3.8K, move to next state
        if self.check_temperature_criteria(self.current_state.id):
            return True
        else:
            return self.timer_check()
    def pump_off_cond(self):
        return self.timer_check()
    def heat_switch_on_cond(self):
        # Move to head_cold state if below 875mK
        return self.check_temperature_criteria(self.current_state.id)
    def head_not_cooling_cond(self):
        # If 4head doesnt get below 0.875K in 1.5 hours, Try recycling
        return self.timer_check()
    def head_cold_recycle_cond(self):
        # Initialize a timer when the cold_stage_temp exceeds the threshold
        if not hasattr(self, 'head_cold_timer'):
            self.head_cold_timer = ElapsedTime(threshold_seconds=10)

        # Get current time and temperature
        current_hour = time.localtime().tm_hour
        current_min = time.localtime().tm_min
        target_hour = self.sm_settings['misc']['start_recycle_clock_hour']
        target_min = self.sm_settings['misc']['start_recycle_clock_min']
        # Get the current temperature of the 4HEAD
        cold_stage_temp = self.fridge_state['temperatures']['4HEAD']
        threshold = self.sm_settings['misc']['start_recycle_temp']

        # Check if 4HEAD temperature exceeds the threshold
        if cold_stage_temp > threshold:
            print(f'4Head is starting to warm up > {threshold}K, monitoring timer...')
            if self.head_cold_timer()[0]:  # Check if timer exceeds 10 seconds
                print(f'4Head has been above {threshold}K for 10 seconds, will begin recycle', f'{self.log_time()}')
                return True
        else:
            # Reset the timer if the temperature drops below the threshold
            self.head_cold_timer.reset()

        # Check if it's the target time to start recycling
        if current_hour == target_hour and current_min == target_min:
            print(f'It is {target_hour}:{target_min}, will begin recycle')
            self.clock_recycle = True
            return True

        return False
    def stop_func(self, bool_test = False):
        #-----------------------------------------------------------------------------------------------------#
        # Exit condition used for all states to end the state machine
        #-----------------------------------------------------------------------------------------------------#
        # EDIT ME
        #-----------------------------------------------------------------------------------------------------#
        return bool_test
    #-----------------------------------------------------------------------------------------------------#
    #        On-entry functions - These are the functions/tasks that are executed on entry into a state.  #
    #-----------------------------------------------------------------------------------------------------#    
    def on_enter_pre_cool(self):

        # Turn off heaters and switches during precooling
        print('on_enter_pre_cool', f'{self.log_time()}')
        self.run_per_state()
    def on_enter_start_recycle(self):
        print('on_enter_start_recycle', f'{self.log_time()}')
        self.run_per_state()
    def on_enter_get_pump_warm(self):
        self.run_per_state()
        print('on_enter_pump_warm', f'{self.log_time()}')
    def on_enter_get_pump_hot(self):
        print('on_enter_get_pump_hot', f'{self.log_time()}')
        self.run_per_state()

        #self.set_all_key_values(self.current_state.id, 'relays')
    def on_enter_turn_on_heat_switch_4(self):
        self.run_per_state()
        print('Turning on 4switch to begin <1K cooldown', f'{self.log_time()}', flush=True)
    def on_enter_head_cold(self):
        self.run_per_state()
        #self.set_all_key_values(self.current_state.id, 'relays')
        print('Head is below 875mK', f'{self.log_time()}', flush=True)
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



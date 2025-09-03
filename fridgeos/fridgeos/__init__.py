"""FridgeOS - Simple, easy-to-use control software for cryostats"""

__version__ = "0.2.0"

from fridgeos.hal import HALServer, HALClient
from fridgeos.scraper import Scraper, PostgresUploader
from fridgeos.statemachine import StateMachineServer, StateMachineClient
# from fridgeos.statemachine import single_shot_1k
# from fridgeos.statemachine import continous_dr

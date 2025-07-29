- Make it possible to set EITHER value or temperature directly for any heater
- Have HAL return "success" when it does something so we know heaters got set, and statemachine doesn't update heater values unless
- Add timed entry for a given state (e.g. 7am)
[[timed_transition]]
from = "cold" # optional
to = "recycling"
hour_of_day = 21
- Rename files to hal.py with HALclient and HALserver etc

Optional:
- Add required sequential temp readings to avoid glitches changing state
- Add Grafana "value mapping" for state
- Settings.toml:
    - Set scraping interval
    - debug to be set to true/false
- Have StateMachineServer version point to the correct fridgeos version

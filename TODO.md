- Make heaters EITHER be PID or directly settable (make temperatures defined in K? Like "40K"?)
- Why do I need to --build every time I change the toml?
- Have HAL return "success" when it does something so we know heaters got set, and statemachine doesn't update heater values unless
- Add timed entry for a given state (e.g. 7am)
[[timed_transition]]
from = "cold" # optional
to = "recycling"
hour_of_day = 21
- Fix "Could not connect to HAL" errors with health check during startup


Optional:
- Add required sequential temp readings to avoid glitches changing state
- Rename files to hal.py with HALclient and HALserver etc
- Add Grafana "value mapping" for state
- Settings.toml:
    - Set scraping interval
    - debug to be set to true/false
- Have StateMachineServer version point to the correct fridgeos version

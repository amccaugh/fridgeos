- Add statemachine timer to show when things are stale, by having integer update_number that database_scraper keeps track of and doesn't push updates if it's the same number
- Make easier to select config, with default dummy-config if nothing in /config/
- Make it possible to set EITHER value or temperature directly for any heater
- Allow state machine to be paused (either stop state transitions or state transitions + PID heater control)


Optional:
- Add required sequential temp readings to avoid glitches changing state
- Add Grafana "value mapping" for state
- Settings.toml:
    - Set scraping interval
    - debug to be set to true/false
- Have StateMachineServer version point to the correct fridgeos version

- Make easier to select config, with default dummy-config if nothing in /config/
- Make it possible to set EITHER value or temperature directly for any heater
- Have HAL return "success" when it does something so we know heaters got set, and statemachine doesn't update heater values unless
- Allow state machine to be paused (either stop state transitions or state transitions + PID heater control)
- Optimize postgres number of processors  


Optional:
- Add required sequential temp readings to avoid glitches changing state
- Add Grafana "value mapping" for state
- Settings.toml:
    - Set scraping interval
    - debug to be set to true/false
- Have StateMachineServer version point to the correct fridgeos version

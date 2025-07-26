- Add required sequential temp readings to avoid glitches changing state
- Create a new "heaters" databse table, make the database-scraper upload it to that table, and create a grafana panel called "Heater values" underneath the existing panels with a time series visualization
- Have HAL return "success" when it does something so we know heaters got set, and statemachine doesn't update heater values unless
- Add timed entry for a given state (e.g. 7am)

Optional:
- Rename files to hal.py with HALclient and HALserver etc
- Add Grafana "value mapping" for state
- Settings.toml:
    - Set scraping interval
    - debug to be set to true/false
- Have StateMachineServer version point to the correct fridgeos version
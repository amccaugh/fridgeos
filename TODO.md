- Make example-configs/ folder
- Add configs/ to gitignore and remove past tracked files
- Make it possible to set EITHER value (4) or temperature ("4K") directly for any heater


Optional:
- Add required sequential temp readings to avoid glitches changing state
- Add Grafana "value mapping" for state
- Settings.toml:
    - Set scraping interval
    - debug to be set to true/false
- Have StateMachineServer version point to the correct fridgeos version

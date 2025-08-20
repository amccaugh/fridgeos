- Make it possible to set EITHER value (4) or temperature ("4K") directly for any heater
- Make state machine require you to type in fridge name
- Make proper non-admin grafana user

Documentation:
- Add 
```
0 7 * * * curl -X PUT http://localhost:8000/state -H 'Content-Type: application/json' -d '{"state": "recycling"}'
```


Optional:
- Add required sequential temp readings to avoid glitches changing state
- Add Grafana "value mapping" for state
- Settings.toml:
    - Set scraping interval
    - debug to be set to true/false
- Have StateMachineServer version point to the correct fridgeos version

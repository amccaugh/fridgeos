- Make proper non-admin grafana user

Documentation:
- Add 
```
0 7 * * * curl -X PUT http://localhost:8000/state -H 'Content-Type: application/json' -d '{"state": "recycling"}'
```
- Add
```
sudo usermod -a -G dialout $USER
```

Optional:
- Add Grafana "value mapping" for state
- Have StateMachineServer version point to the correct fridgeos version

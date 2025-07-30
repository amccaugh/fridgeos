- Make easier to select config, with default dummy-config if nothing in /config/
- Make it possible to set EITHER value or temperature directly for any heater
- Have HAL return "success" when it does something so we know heaters got set, and statemachine doesn't update heater values unless
- Allow state machine to be paused (either stop state transitions or state transitions + PID heater control)
- Optimize postgres number of processors  
- Fix long Current Temperatures query time
  - "Stat" panel with Calculation = Last non-null value
            SELECT
            "time" AS "time",
            value AS Temp,
            name,
            sensor
            FROM
            cryostats
            WHERE
            (
                name = '${cryostatname}'
                AND sensor NOT LIKE '%slot%'
                AND (time > now() - INTERVAL '10 MINUTE')
            )
            ORDER BY
            time
            LIMIT
            50000


{
  "datasource": {
    "type": "grafana-postgresql-datasource",
    "uid": "bbcdc51a-8ecc-49d5-9fbe-ffc92d962256"
  },
  "fieldConfig": {
    "defaults": {
      "mappings": [],
      "thresholds": {
        "mode": "absolute",
        "steps": [
          {
            "color": "green",
            "value": null
          },
          {
            "color": "red",
            "value": 80
          }
        ]
      },
      "color": {
        "mode": "thresholds"
      },
      "displayName": "${__field.labels.sensor}"
    },
    "overrides": []
  },
  "gridPos": {
    "h": 13,
    "w": 5,
    "x": 19,
    "y": 0
  },
  "id": 2,
  "options": {
    "reduceOptions": {
      "values": false,
      "calcs": [
        "lastNotNull"
      ],
      "fields": ""
    },
    "orientation": "horizontal",
    "textMode": "auto",
    "wideLayout": true,
    "colorMode": "value",
    "graphMode": "area",
    "justifyMode": "auto"
  },
  "pluginVersion": "10.2.3",
  "targets": [
    {
      "datasource": {
        "type": "grafana-postgresql-datasource",
        "uid": "bbcdc51a-8ecc-49d5-9fbe-ffc92d962256"
      },
      "editorMode": "code",
      "format": "time_series",
      "rawQuery": true,
      "rawSql": "SELECT\n  \"time\" AS \"time\",\n  value AS Temp,\n  name,\n  sensor\nFROM\n  cryostats\nWHERE\n  (\n    name = '${cryostatname}'\n    AND sensor NOT LIKE '%slot%'\n    AND (time > now() - INTERVAL '10 MINUTE')\n  )\nORDER BY\n  time\nLIMIT\n  50000",
      "refId": "A",
      "sql": {
        "columns": [
          {
            "parameters": [],
            "type": "function"
          }
        ],
        "groupBy": [
          {
            "property": {
              "type": "string"
            },
            "type": "groupBy"
          }
        ],
        "limit": 50
      }
    }
  ],
  "title": "Current temps",
  "type": "stat"
}

Optional:
- Add required sequential temp readings to avoid glitches changing state
- Add Grafana "value mapping" for state
- Settings.toml:
    - Set scraping interval
    - debug to be set to true/false
- Have StateMachineServer version point to the correct fridgeos version

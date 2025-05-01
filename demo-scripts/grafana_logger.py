#%%
import psycopg2
from datetime import datetime, timezone
from fridgeos.monitor.client import MonitorClient
import asyncio

# Connect to database
conn = psycopg2.connect(
host = "example.com",
user = "myuser",
port = 5432,
password = "mypass",
database = "qittlab",)
ip = '127.0.0.1'
http_port = 8000
grafana_scraper = MonitorClient(url=f'http://localhost:{http_port}/', timeout=0.1)

async def grafana_log(scraper, am_running):
    while am_running:
        try:
            data_dict = scraper.get_metrics()
            cur = conn.cursor()
            timestamp = datetime.now(timezone.utc)
            sql = (f"INSERT INTO cryostats"
                    "(time, name, sensor, value) "
                    "VALUES (%(time)s, %(name)s, %(sensor)s, %(value)s)")
            try:
                for sensor,temperature in data_dict['temperatures'].items():
                    data = {
                        'time': timestamp,
                        'name': '1K_GL4_3341',
                        'sensor': sensor,
                        'value': temperature,
                        }
                    cur.execute(sql, data)
            except:
                pass
            try:
                for key, value in data_dict['heaters'].items():
                    if key == '4SWITCH':
                        data = {
                            'time': timestamp,
                            'name': '1K_GL4_3341',
                            'sensor': f'{key}_heater',
                            'value': value
                            }
                        cur.execute(sql, data)

                    elif key == '4PUMP':
                        for sub_key,value in data_dict['heaters'][f'{key}'].items():
                            data = {
                                'time': timestamp,
                                'name': '1K_GL4_3341',
                                'sensor': f'{key}_{sub_key}',
                                'value': value
                                }
                            cur.execute(sql, data)
            except: 
                pass
            conn.commit()
            time.sleep(5)
        except KeyboardInterrupt:
            raise
        except Exception as e:
            print(f'Error: {e}')
            time.sleep(5)
            pass
async def start_grafana_logger():
    asyncio.create_task(grafana_log(grafana_scraper, am_running=True))
async def stop_grafana_logger():
    asyncio.create_task(grafana_log(grafana_scraper, am_running=False))
    
asyncio.run(start_grafana_logger()) 

# %%

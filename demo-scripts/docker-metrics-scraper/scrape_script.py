#%%
from fridgeos import Scraper, PostgresUploader
import pandas as pd
import psycopg2
import tomllib
import datetime
import time


#### SETUP

# Load database connection details
with open("./config/secrets.toml", mode="rb") as f:
    db_details = tomllib.load(f)['database']

# Create the scraper
scraper = Scraper(timeout = 0.5, num_workers = 10)
uploader = PostgresUploader(
    host=db_details['host'],
    port=db_details['port'],
    user=db_details['user'],
    password=db_details['password'],
    database=db_details['database'],
    timeout = 1
)

### MAIN LOOP
while True:
    print('Scraping...', flush=True)
    try:
        # Load list of fridge URLs to scrap
        with open("./config/fridge_list_to_scrape.txt", 'r') as file:
            lines = file.readlines()
        fridge_list_to_scrape = [line.strip() for line in lines]

        # Scrape URLs
        responses = scraper.scrape(fridge_list_to_scrape)
        print('Responses:', responses, flush=True)

        # If anything responds, convert to DataFrame and upload to database
        if responses:
            df_temperatures, df_heaters, df_state = uploader.scraped_responses_to_df(responses)
            print(df_temperatures)
            uploader.upload_dataframe_to_table(df_temperatures, 'cryostats')
    except Exception as e:
        print(e, flush=True)
    time.sleep(5)


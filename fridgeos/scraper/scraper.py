#%%
import concurrent.futures
import requests
import json
import pandas as pd
import psycopg2
import tomllib
import datetime
import time

class Scraper:
    """ A multi-threaded HTTP scraper that fetches JSON data from a list of URLs. """
    def __init__(self,  timeout = 1, num_workers = 10):
        self.timeout = timeout
        self.num_workers = num_workers

    def fetch(self, url):
        try:
            response = requests.get(url, timeout = self.timeout)
            return (url, response.status_code, response.text)
        except requests.RequestException as e:
            return (url, None, str(e))

    def scrape(self, urls):
        responses = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.num_workers) as executor:
            future_to_url = {executor.submit(self.fetch, url): url for url in urls}
            for future in concurrent.futures.as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    url, status_code, content = future.result()
                    if status_code == 200:
                        responses[url] = json.loads(content)
                except Exception as exc:
                    print(f"URL: {url} generated an exception: {exc}")
        return responses


class PostgresUploader:

    def __init__(self, host, port, user, password, database, timeout = 1):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.timeout = timeout

    def scraped_responses_to_df(self, responses):
        """
        Convert a dictionary of responses into three separate pandas DataFrames.
        Parameters:
        responses (dict): A dictionary containing response data. Each key is a unique identifier, 
                            and each value is a dictionary
        Returns:
        tuple: A tuple containing three pandas DataFrames:
                - df_temperatures: DataFrame with columns ['time', 'cryostatname', 'sensorname', 'temperature']
                - df_heaters: DataFrame with columns ['time', 'cryostatname', 'heatername', 'value']
                - df_state: DataFrame with columns ['time', 'cryostatname', 'state']
        """

        temperatures_df_list = []
        heaters_df_list = []
        state_df_list = []
        current_time = datetime.datetime.now(datetime.timezone.utc)
        for response in responses.values():
            cryostat_name = response['metadata']['cryostat_name']
            if 'temperatures' in response:
                df = pd.DataFrame({
                    'time' : current_time,
                    'name' :  cryostat_name,
                    'sensor': response['temperatures'].keys(),
                    'value':  response['temperatures'].values()}
                    )
                temperatures_df_list.append(df)
            if 'heaters' in response:
                df = pd.DataFrame({
                    'time' : current_time,
                    'cryostat' :  cryostat_name,
                    'name': response['heaters'].keys(),
                    'value':  response['heaters'].values()}
                    )
                heaters_df_list.append(df)
            if 'state' in response:
                df = pd.DataFrame({
                    'time' : current_time,
                    'cryostat' :  [cryostat_name],
                    'state': [response['state']]},
                    )
                state_df_list.append(df)
        if len(temperatures_df_list) > 0:
            df_temperatures = pd.concat(temperatures_df_list)
        else:
            df_temperatures = None
        if len(heaters_df_list) > 0:
            df_heaters = pd.concat(heaters_df_list)
        else:
            df_heaters = None
        if len(state_df_list) > 0:
            df_state = pd.concat(state_df_list)
        else:
            df_state = None

        return df_temperatures, df_heaters, df_state


    def upload_dataframe_to_table(self, df, table_name):
        """
        Uploads the entries of a pandas DataFrame to a table in a PostgreSQL database.

        Parameters:
        df (pd.DataFrame): The DataFrame to upload.
        table_name (str): The name of the table to upload the data to.
        """
        # Establish a connection to the database
        with psycopg2.connect(
                        host = self.host,
                        port = self.port,
                        user = self.user,
                        password = self.password,
                        dbname = self.database,
                        connect_timeout = self.timeout) as conn:
            with conn.cursor() as cursor:
                # Iterate over DataFrame rows
                for index, row in df.iterrows():
                    # Construct the SQL INSERT statement
                    columns = ', '.join(row.index)
                    values = ', '.join([f'%({col})s' for col in row.index])
                    sql = f"INSERT INTO {table_name} ({columns}) VALUES ({values})"
                    
                    # Execute the SQL command
                    cursor.execute(sql, row.to_dict())
                
                # Commit the transaction
                conn.commit()


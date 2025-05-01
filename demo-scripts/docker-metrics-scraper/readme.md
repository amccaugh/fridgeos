Fill `config/fridge_list_to_scrape.txt` with addresses that should be scraped

```
http://myfridgecomputer1.myhost.com:8000
http://myfridgecomputer2.myhost.com:8000
```

Fill out `config/secrets.toml` with database details

```
[database]
host = "mydatabasehost.org"
user = "myuser"
port = 5432
password = "mypassword"
database = "mydb"
```

Run the docker container:

`docker-compose up -d --build`

To attach to it find the docker container

`docker container ls`

And attach to it:

`docker attach a5c1db31f961`
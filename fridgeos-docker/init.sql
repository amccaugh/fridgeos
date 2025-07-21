CREATE TABLE temperatures (
    time TIMESTAMPTZ NOT NULL,
    sensorname TEXT NOT NULL,
    temperature REAL NOT NULL);
SELECT create_hypertable('temperatures', 'time');

CREATE TABLE states (
    time TIMESTAMPTZ NOT NULL,
    state TEXT NOT NULL);
SELECT create_hypertable('states', 'time');

-- Create fridgeosuser
CREATE USER fridgeosuser WITH PASSWORD 'fridgeos123';
GRANT CONNECT ON DATABASE fridgedb TO fridgeosuser;
GRANT USAGE ON SCHEMA public TO fridgeosuser;
GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA public TO fridgeosuser;
GRANT SELECT, INSERT ON TABLE temperatures TO fridgeosuser;
GRANT SELECT, INSERT ON TABLE states TO fridgeosuser;
ALTER ROLE fridgeosuser SET statement_timeout = '60s';
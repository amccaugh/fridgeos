CREATE TABLE temperatures (
    time TIMESTAMPTZ NOT NULL,
    sensorname TEXT NOT NULL,
    temperature REAL NOT NULL);
SELECT create_hypertable('temperatures', 'time');
CREATE INDEX ON temperatures (sensorname, time DESC);

CREATE TABLE states (
    time TIMESTAMPTZ NOT NULL,
    state TEXT NOT NULL);
SELECT create_hypertable('states', 'time');

CREATE TABLE heaters (
    time TIMESTAMPTZ NOT NULL,
    heatername TEXT NOT NULL,
    value REAL NOT NULL);
SELECT create_hypertable('heaters', 'time');
CREATE INDEX ON heaters (heatername, time DESC);

-- Create fridgeosuser
CREATE USER fridgeosuser WITH PASSWORD 'fridgeos123';
GRANT CONNECT ON DATABASE fridgedb TO fridgeosuser;
GRANT USAGE ON SCHEMA public TO fridgeosuser;
GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA public TO fridgeosuser;
GRANT SELECT, INSERT ON TABLE temperatures TO fridgeosuser;
GRANT SELECT, INSERT ON TABLE states TO fridgeosuser;
GRANT SELECT, INSERT ON TABLE heaters TO fridgeosuser;
ALTER ROLE fridgeosuser SET statement_timeout = '60s';
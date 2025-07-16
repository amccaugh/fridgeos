CREATE TABLE temperatures (
    time TIMESTAMPTZ NOT NULL,
    fridgename TEXT NOT NULL,
    sensorname TEXT NOT NULL,
    temperature REAL NOT NULL);
SELECT create_hypertable('temperatures', 'time');
CREATE INDEX idx_cryostat ON temperatures(fridgename);

-- Create fridgeosuser
CREATE USER fridgeosuser WITH PASSWORD '${FRIDGEOS_PASSWORD}';
GRANT CONNECT ON DATABASE fridgedb TO fridgeosuser;
GRANT USAGE ON SCHEMA public TO fridgeosuser;
GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA public TO fridgeosuser;
GRANT SELECT, INSERT ON TABLE cryostat_temperatures TO fridgeosuser;
ALTER ROLE fridgeosuser SET statement_timeout = '60s';
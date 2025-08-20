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

-- Performance optimizations
-- Update statistics more frequently for time-series data
ALTER TABLE temperatures SET (autovacuum_analyze_scale_factor = 0.02);
ALTER TABLE heaters SET (autovacuum_analyze_scale_factor = 0.02);
ALTER TABLE states SET (autovacuum_analyze_scale_factor = 0.1);

-- TimescaleDB specific optimizations
-- Set chunk time interval to 1 day for better performance
SELECT set_chunk_time_interval('temperatures', INTERVAL '1 day');
SELECT set_chunk_time_interval('heaters', INTERVAL '1 day');
SELECT set_chunk_time_interval('states', INTERVAL '1 day');

-- Enable compression on older data (older than 1 day)
ALTER TABLE temperatures SET (
  timescaledb.compress,
  timescaledb.compress_segmentby = 'sensorname'
);
ALTER TABLE heaters SET (
  timescaledb.compress,
  timescaledb.compress_segmentby = 'heatername'
);

-- Auto-compress data older than 1 day
SELECT add_compression_policy('temperatures', INTERVAL '1 day');
SELECT add_compression_policy('heaters', INTERVAL '1 day');
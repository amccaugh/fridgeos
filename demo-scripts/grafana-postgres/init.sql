CREATE TABLE cryostat_temperatures (
    time TIMESTAMPTZ NOT NULL,
    cryostatname TEXT NOT NULL,
    sensorname TEXT NOT NULL,
    temperature REAL NOT NULL);
SELECT create_hypertable('cryostat_temperatures', 'time');
CREATE INDEX idx_cryostat ON cryostat_temperatures(cryostatname);
from pathlib import Path
import duckdb

DB_PATH = Path(__file__).parent / "f1.duckdb" 

def connect(read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """Open the warehouse. Use read_only = True from notebooks to avoid locks."""
    return duckdb.connect(str(DB_PATH), read_only = read_only)

SCHEMA = """
CREATE TABLE IF NOT EXISTS races (
    season      INTEGER,
    round       INTEGER,
    race_name   VARCHAR,
    circuit_id  VARCHAR,
    race_date   DATE,
    PRIMARY KEY (season, round)
);

CREATE TABLE IF NOT EXISTS circuits (
    circuit_id  VARCHAR PRIMARY KEY,
    name        VARCHAR,
    country     VARCHAR,
    lat         DOUBLE,
    lng         DOUBLE
);

CREATE TABLE IF NOT EXISTS results (
    season         INTEGER,
    round          INTEGER,
    driver_id      VARCHAR,
    constructor_id VARCHAR,
    grid           INTEGER,
    position       INTEGER,
    points         DOUBLE,
    status         VARCHAR,
    PRIMARY KEY (season, round, driver_id)
);

CREATE TABLE IF NOT EXISTS qualifying (
    season         INTEGER,
    round          INTEGER,
    driver_id      VARCHAR,
    quali_position INTEGER,
    q1_ms          BIGINT,
    q2_ms          BIGINT,
    q3_ms          BIGINT,
    PRIMARY KEY (season, round, driver_id)
);

CREATE TABLE IF NOT EXISTS laps (
    season       INTEGER,
    round        INTEGER,
    driver_id    VARCHAR,
    lap_number   INTEGER,
    lap_time_ms  BIGINT,
    compound     VARCHAR,
    tyre_life    INTEGER,
    stint        INTEGER,
    position     INTEGER,
    PRIMARY KEY (season, round, driver_id, lap_number)
);

CREATE TABLE IF NOT EXISTS drivers (
    driver_id     VARCHAR PRIMARY KEY,
    code          VARCHAR,
    forename      VARCHAR,
    surname       VARCHAR,
    nationality   VARCHAR,
    date_of_birth DATE
);

CREATE TABLE IF NOT EXISTS constructors (
    constructor_id VARCHAR PRIMARY KEY,
    name           VARCHAR,
    nationality    VARCHAR
);
"""

def init_db() -> None:
    """Create the warehouse and all tables if they don't already exist."""
    con = connect()
    con.execute(SCHEMA)
    con.close()

def table_counts() -> dict[str, int]:
    """Health check: how many rows are in each table."""
    con = connect(read_only=True)
    tables = [r[0] for r in con.execute("SHOW TABLES").fetchall()]
    counts = {t: con.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in tables}
    con.close()
    return counts


if __name__ == "__main__":
    init_db()
    print("Warehouse ready at", DB_PATH)
    print("Row counts:", table_counts())
import sys
import time
import fastf1
from fastf1.ergast import Ergast
import db

CACHE_DIR = "fastf1_cache"
fastf1.Cache.enable_cache(CACHE_DIR)

def _int_or_none(value):
    """Convert a value to int, returning None for missing/NaN values."""
    try:
        if value is None or (isinstance(value, float) and value != value):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None
    
def _time_to_ms(value):
    """Convert a pandas Timedelta lap time to whole millisecons (None if missing/NaN)."""
    try:
        return int(value.total_seconds() * 1000)
    except (AttributeError, TypeError, ValueError):
        return None
    
def ingest_reference_data(season: int, con) -> None:
    """Fill the drivers and constructors tables for a one season."""
    ergast = Ergast(result_type = "pandas", auto_cast = True)

    drivers = ergast.get_driver_info(season = season)
    for _, d in drivers.iterrows():
        con.execute(
            "INSERT OR REPLACE INTO drivers VALUES (?,?,?,?,?,?)",
            [d["driverId"], d["driverCode"], d["givenName"], d["familyName"], d["driverNationality"], d["dateOfBirth"]],
        )

    constructors = ergast.get_constructor_info(season = season)
    for _, c in constructors.iterrows():
        con.execute(
            "INSERT OR REPLACE INTO constructors VALUES (?,?,?)",
            [c["constructorId"], c["constructorName"], c["constructorNationality"]],
        )

def ingest_schedule(season: int, con) -> None:
    """Fill races and circuits for one season."""
    ergast = Ergast(result_type = "pandas", auto_cast = True)
    schedule = ergast.get_race_schedule(season)
    for _, row in schedule.iterrows():
        con.execute(
            "INSERT OR REPLACE INTO circuits VALUES (?, ?, ?, ?, ?)",
            [row["circuitId"], row["circuitName"], row["country"],
             float(row["lat"]), float(row["long"])],
        )
        con.execute(
            "INSERT OR REPLACE INTO races VALUES (?, ?, ?, ?, ?)",
            [season, int(row["round"]), row["raceName"],
             row["circuitId"], row["raceDate"]],
        )

def ingest_results(season: int, con) -> None:
    """Fill the results table, fetching one race at a time to avoid truncation."""
    ergast = Ergast(result_type = "pandas", auto_cast = True)

    # Ask our own warehouse how many rounds this season has.
    rounds = con.execute(
        "SELECT round FROM races WHERE season = ? ORDER BY round", [season]
    ).fetchall()

    time.sleep(0.5)

    for (rnd,) in rounds:
        res = ergast.get_race_results(season=season, round=rnd)
        if not res.content:          # safety: skip if a race returns nothing
            continue
        race = res.content[0]        # single race -> first (only) DataFrame
        for _, r in race.iterrows():
            con.execute(
                "INSERT OR REPLACE INTO results VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [season, rnd, r["driverId"], r["constructorId"],
                 _int_or_none(r["grid"]), _int_or_none(r["position"]),
                 float(r["points"]), r["status"]],
            )

def ingest_qualifying(season: int, con) -> None:
    """Fill the qualifying table, one race at a time."""
    ergast = Ergast(result_type = "pandas", auto_cast = True)

    rounds = con.execute(
        "SELECT round FROM races WHERE season = ? ORDER BY round", [season]
    ).fetchall()

    time.sleep(0.5)

    for (rnd,) in rounds:
        res = ergast.get_qualifying_results(season=season, round=rnd)
        if not res.content:
            continue
        quali = res.content[0]
        for _, q in quali.iterrows():
            con.execute(
                "INSERT OR REPLACE INTO qualifying VALUES (?, ?, ?, ?, ?, ?, ?)",
                [season, rnd, q["driverId"], _int_or_none(q["position"]),
                 _time_to_ms(q["Q1"]), _time_to_ms(q["Q2"]), _time_to_ms(q["Q3"])],
            )

if __name__ == "__main__":
    db.init_db()
    con = db.connect()

    seasons = [2021, 2022, 2023, 2024, 2025]
    for season in seasons:
        print(f"Ingesting {season} ...")
        ingest_reference_data(season, con)
        ingest_schedule(season, con)
        ingest_results(season, con)
        ingest_qualifying(season, con)

    con.close()
    print("Ingestion complete. Counts:", db.table_counts())
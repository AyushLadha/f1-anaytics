import pandas as pd
import db

RECENT_WINDOW = 5 # how many past races the "recent form" feature should look at

def build_modeling_table():
    con = db.connect(read_only = True)
    df = con.execute(
        """
    SELECT
        r.season, r.round, r.driver_id, ra.race_date, ra.circuit_id,
        r.constructor_id, r.grid, r.position, r.points, r.status, q.quali_position
    From results r
    Join races ra Using (season, round)
    Left Join qualifying q Using (season, round, driver_id)
    Order by ra.race_date, r.round"""
    ).df()
    con.close()
    # Target 1: Did the driver finish in the top 3?
    df["podium"] = (df["position"] <= 3).fillna(False).astype(int)

    # Sort chronologically - every leak-free feature below depends on this order.
    df = df.sort_values(["race_date", "round"]).reset_index(drop=True)

    # Treat a DNF as a bad finish (20th) for form purposes, rather than NULL.
    df["finish_for_form"] = df["position"].fillna(20)

    # Driver's average finishing position over the PREVIOUS races (not this one).
    df["driver_recent_finish"] = (
        df.groupby("driver_id")["finish_for_form"]
        .transform(lambda s: s.shift(1).rolling(RECENT_WINDOW, min_periods=1).mean())
    )

    # Constructor recent form: teams average points over their previous races
    df["constructor_recent_points"] = (
        df.groupby("constructor_id")["points"]
        .transform(lambda s: s.shift(1).rolling(RECENT_WINDOW, min_periods = 1).mean())
    )

    # Driver's history AT THIS CIRCUIT: average finish in previous visits here.
    df["driver_circuit_finish"] = (
        df.groupby(["driver_id", "circuit_id"])["finish_for_form"]
        .transform(lambda s: s.shift(1).expanding().mean())
    )

    feature_cols = [
        "grid",
        "quali_position",
        "driver_recent_finish",
        "constructor_recent_points",
        "driver_circuit_finish",
    ]
    keep = ["season", "round", "race_date", "driver_id", "podium"] + feature_cols
    return df[keep], feature_cols

if __name__ == "__main__":
    table, feature_cols = build_modeling_table()
    print("rows:", len(table))
    print("features:", feature_cols)
    print("podium rate:", round(table["podium"].mean(), 3))
    print("missing values per feature:")
    print(table[feature_cols].isna().sum())

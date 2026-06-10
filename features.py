import pandas as pd
import db

RECENT_WINDOW = 5 # how many past races the "recent form" feature should look at

# Approximate seconds penalty vs SOFT compound, applied to convert any-compound
# pace into a "soft-equivalent" pace so it's comparable across drivers.
# Values are empirical estimates — refine later from your own data.
COMPOUND_PENALTY_MS = {
    "SOFT": 0,
    "MEDIUM": 500,
    "HARD": 1100,
    "INTERMEDIATE": 8000,   # wet-tyre laps are dramatically slower; we'd usually
    "WET": 12000,           # rather treat these as NaN, but defensive defaults are fine
}

def _soft_equivalent_ms(pace_ms, compound):
    """Convert a pace on any compound into approximate SOFT-equivalent pace."""
    if pace_ms is None or pd.isna(pace_ms) or compound not in COMPOUND_PENALTY_MS:
        return None
    return pace_ms - COMPOUND_PENALTY_MS[compound]

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

def build_quali_modeling_table():
    """Build the per-driver-per-race table for qualifying-position prediction.

    Target is qualifying position. Grid and qualifying position are EXCLUDED
    from features (they ARE the answer or directly derived from it). Practice
    pace is included, joined via the drivers.code mapping.
    """
    con = db.connect(read_only = True)
    df = con.execute(
        """
        SELECT
            r.season, r.round, ra.race_date, ra.circuit_id,
            r.driver_id, r.constructor_id,
            r.position AS race_finish,
            r.points, r.status,
            q.quali_position,
            pp_fp2.fastest_lap_ms   AS fp2_pace_ms,
            pp_fp2.fastest_compound AS fp2_compound,
            pp_fp3.fastest_lap_ms   AS fp3_pace_ms,
            pp_fp3.fastest_compound AS fp3_compound
        FROM results r
        JOIN races ra USING (season, round)
        JOIN drivers d ON d.driver_id = r.driver_id
        LEFT JOIN qualifying q
        ON q.season = r.season
        AND q.round = r.round
        AND q.driver_id = r.driver_id
        LEFT JOIN practice_pace pp_fp2
               ON pp_fp2.season = r.season
              AND pp_fp2.round = r.round
              AND pp_fp2.session = 'FP2'
              AND pp_fp2.driver_id = d.code
        LEFT JOIN practice_pace pp_fp3
               ON pp_fp3.season = r.season
              AND pp_fp3.round = r.round
              AND pp_fp3.session = 'FP3'
              AND pp_fp3.driver_id = d.code
        WHERE q.quali_position IS NOT NULL
        ORDER BY ra.race_date, r.round
        """
    ).df()
    con.close()
    # Convert raw pace to "gap to fastest in the session" — comparable across circuits.
    # Soft-equivalent pace first, then ranked relative to the session's leader.
    df["fp2_soft_ms"] = df.apply(
        lambda row: _soft_equivalent_ms(row["fp2_pace_ms"], row["fp2_compound"]), axis=1
    )
    df["fp3_soft_ms"] = df.apply(
        lambda row: _soft_equivalent_ms(row["fp3_pace_ms"], row["fp3_compound"]), axis=1
    )

    # Subtract the session's fastest soft-equivalent pace from each driver's lap.
    # This gives "gap to fastest" in ms - small positive = close to the front.
    df["fp2_gap_ms"] = df["fp2_soft_ms"] - df.groupby(["season", "round"])["fp2_soft_ms"].transform("min")
    df["fp3_gap_ms"] = df["fp3_soft_ms"] - df.groupby(["season", "round"])["fp3_soft_ms"].transform("min")

    # Sort chronologically — load-bearing for every leak-free feature below.
    df = df.sort_values(["race_date", "round"]).reset_index(drop=True)

    # Driver recent qualifying form: average qualifying position over the previous N races.
    df["driver_recent_quali"] = (
        df.groupby("driver_id")["quali_position"]
        .transform(lambda s: s.shift(1).rolling(RECENT_WINDOW, min_periods=1).mean())
    )

    # Constructor recent qualifying form: team's average qualifying position.
    # Constructor recent form needs special care: both teammates qualify in the
    # same session, so a naive driver-level shift would leak the teammate's
    # quali into the other driver's "recent form" feature for the SAME race.
    # Fix: collapse to one row per (constructor, race) first, shift/roll on that
    # team-level timeline, then merge back to every driver-row.

    team_race = (
        df.groupby(["constructor_id", "season", "round", "race_date"], as_index=False)
          ["quali_position"]
          .mean()
          .sort_values(["constructor_id", "race_date", "round"])
    )
    team_race["constructor_recent_quali"] = (
        team_race.groupby("constructor_id")["quali_position"]
        .transform(lambda s: s.shift(1).rolling(RECENT_WINDOW, min_periods=1).mean())
    )

    df = df.merge(
        team_race[["constructor_id", "season", "round", "constructor_recent_quali"]],
        on=["constructor_id", "season", "round"],
        how="left",
    )

    # Driver's history at this specific circuit: average quali position in previous visits.
    df["driver_circuit_quali"] = (
        df.groupby(["driver_id", "circuit_id"])["quali_position"]
        .transform(lambda s: s.shift(1).expanding().mean())
    )
    
    feature_cols = [
        "fp2_gap_ms",
        "fp3_gap_ms",
        "driver_recent_quali",
        "constructor_recent_quali",
        "driver_circuit_quali",
    ]
    keep = ["season", "round", "race_date", "driver_id", "quali_position"] + feature_cols
    return df[keep], feature_cols

if __name__ == "__main__":
    table, feature_cols = build_quali_modeling_table()
    print("rows:", len(table))
    print("features:", feature_cols)
    print("\nmissing values per feature:")
    print(table[feature_cols].isna().sum())
    print("\nsample of the modeling table:")
    print(table.head(8))
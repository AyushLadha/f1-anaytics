import fastf1

fastf1.Cache.enable_cache("fastf1_cache")

# Load one practice session: 2023, round 1 (Bahrain), FP2.
session = fastf1.get_session(2023, 1, "FP2")
session.load(telemetry=False, weather=False, messages=False)

laps = session.laps
print("number of laps:", len(laps))
print("columns:", list(laps.columns))
print()
print(laps[["Driver", "LapNumber", "LapTime", "Compound", "TyreLife", "IsAccurate"]].head(10))

# How many SOFT laps per driver are "accurate"?
soft_accurate = laps[(laps["Compound"] == "SOFT") & (laps["IsAccurate"])]
print("\naccurate SOFT laps per driver:")
print(soft_accurate.groupby("Driver")["LapTime"].count().sort_values(ascending=False))

# Each driver's best accurate SOFT lap.
print("\nfastest accurate SOFT lap per driver:")
print(soft_accurate.groupby("Driver")["LapTime"].min().sort_values())
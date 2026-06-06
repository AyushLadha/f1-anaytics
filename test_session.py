import fastf1

fastf1.Cache.enable_cache("fastf1_cache")

# Try a session we know we don't have yet
session = fastf1.get_session(2022, 16, "FP1")
session.load(telemetry=False, weather=False, messages=False)

print("LOADED OK. laps:", len(session.laps))
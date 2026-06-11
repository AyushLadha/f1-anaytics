import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error

import features

table, feature_cols = features.build_quali_modeling_table()

TEST_SEASON = table["season"].max()
train = table[table["season"] < TEST_SEASON]
test = table[table["season"] == TEST_SEASON]

X_train, y_train = train[feature_cols], train["quali_position"]
X_test, y_test = test[feature_cols], test["quali_position"]

model = HistGradientBoostingRegressor(
    max_iter=300, learning_rate=0.05, max_depth=4, random_state=42
)
model.fit(X_train, y_train)

predicted = model.predict(X_test)

mae = mean_absolute_error(y_test, predicted)
print(f"MAE: {mae:.2f} positions")
print(f"sample predictions vs actual:")
for actual, pred in list(zip(y_test, predicted))[:8]:
    print(f"  predicted {pred:.1f}  actual {actual}")

test = test.assign(predicted=predicted)

# Per-race grid prediction quality.
pole_hits = 0
top3_hits = 0
top10_hits = 0
race_count = 0

for (season, rnd), grp in test.groupby(["season", "round"]):
    actual_pole = grp.loc[grp["quali_position"].idxmin(), "driver_id"]
    predicted_pole = grp.loc[grp["predicted"].idxmin(), "driver_id"]
    if actual_pole == predicted_pole:
        pole_hits += 1

    actual_top3 = set(grp.nsmallest(3, "quali_position")["driver_id"])
    predicted_top3 = set(grp.nsmallest(3, "predicted")["driver_id"])
    top3_hits += len(actual_top3 & predicted_top3)

    actual_top10 = set(grp.nsmallest(10, "quali_position")["driver_id"])
    predicted_top10 = set(grp.nsmallest(10, "predicted")["driver_id"])
    top10_hits += len(actual_top10 & predicted_top10)

    race_count += 1

print(f"\nover {race_count} races:")
print(f"  pole correctly predicted:  {pole_hits}/{race_count} = {pole_hits/race_count:.1%}")
print(f"  top-3 hit rate:            {top3_hits}/{race_count * 3} = {top3_hits/(race_count*3):.1%}")
print(f"  top-10 hit rate:           {top10_hits}/{race_count * 10} = {top10_hits/(race_count*10):.1%}")
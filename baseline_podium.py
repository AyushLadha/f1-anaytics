import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score, average_precision_score
import features
from sklearn.inspection import permutation_importance

# Build the modeling table (with the leak-free features)
table, feature_cols = features.build_modeling_table()

# Chronological split: train on every season except the most recent, test on it.
test_season = table["season"].max()
train = table[table["season"] < test_season]
test = table[table["season"] == test_season]

X_train, y_train = train[feature_cols], train["podium"]
X_test, y_test = test[feature_cols], test["podium"]

# Initialize and fit the model.
model = HistGradientBoostingClassifier(max_iter = 300, learning_rate = 0.05, max_depth = 4, random_state = 42)
model.fit(X_train, y_train)

# Predicted probabilities of podium for each the test set.
proba = model.predict_proba(X_test)[:, 1]

print("sample predicted podium probabilities:", proba[:5].round(3))
print("min/max probability:", proba.min().round(3), proba.max().round(3))
print(f"ROC AUC:  {roc_auc_score(y_test, proba):.3f}")
print(f"PR  AUC:  {average_precision_score(y_test, proba):.3f}  (base rate {y_test.mean():.3f})")

test = test.assign(proba = proba)
hits, total = 0, 0
for (season, rnd), grp in test.groupby(["season", "round"]):
    predicted_top3 = grp.nlargest(3, "proba")
    hits += predicted_top3["podium"].sum()
    total += 3

print(f"podium hit rate: {hits}/{total} = {hits / total:.3f}")

imp = permutation_importance(model, X_test, y_test, n_repeats = 10, random_state = 42)
importance = (
    pd.DataFrame({"feature": feature_cols, "importance": imp.importances_mean})
    .sort_values("importance", ascending=False)
)
print(importance.to_string(index = False))
import pandas as pd
import numpy as np


# Load data from Excel file

df1 = pd.read_excel('data.xlsx', sheet_name='data')
df2 = pd.read_excel('data.xlsx', sheet_name='metadata')


X = df1.iloc[:, :-1].values  # Features
y = df1.iloc[:, -1].values   # Target variable

# Gets the ideal warmth rating for a given temperature using a logistical curve

def TempToWarmth(temp):
    return 4 + (12/(1 + np.exp(-0.3 * (-temp + 55))))


# Combines data from top and bottom items, and calculates the formality and ideal warmth differences.
tmp = []
for row in X:
    top = row[0]
    bottom = row[1]
    top_info = df2[df2['Item'] == top].iloc[:, 1:-1].values[0]
    bottom_info = df2[df2['Item'] == bottom].iloc[:, 1:-1].values[0]

    # ColorTop, ColorBottom, Formality Diff, Ideal Warmth Diff
    combined_info = [top_info[0], bottom_info[0], abs(top_info[1] - bottom_info[1]), abs(top_info[2] + bottom_info[2] - TempToWarmth(row[2]))]
    tmp.append(combined_info)
        
X = np.array(tmp)

# Encode the categorical features (ColorTop and ColorBottom) using one-hot encoding

from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer

ct = ColumnTransformer(
    [("encoder", OneHotEncoder(sparse_output=False), [0, 1])],
    remainder='passthrough'
)

X = ct.fit_transform(X)

# Split the data into training and testing sets

from sklearn.model_selection import train_test_split

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Train a Random Forest Classifier

from sklearn.ensemble import RandomForestRegressor

rf = RandomForestRegressor(n_estimators=883, max_depth=12, min_samples_leaf=1, min_samples_split=2, random_state=42)
rf.fit(X_train, y_train)

y_pred = rf.predict(X_test)

# Evaluate the model

from sklearn.metrics import mean_squared_error, r2_score
mse = mean_squared_error(y_test, y_pred)
print(f'Mean Squared Error: {mse}')
r2 = r2_score(y_test, y_pred)
print(f'R^2 Score: {r2}')

"""""

import joblib
joblib.dump(rf, 'outfit_recommender_rf.joblib')

"""""

"""""

import optuna
from plotly.io import show
from sklearn.model_selection import cross_val_score

def objective(trial):
    n_estimators = trial.suggest_int('n_estimators', 100, 2000)
    max_depth = trial.suggest_int('max_depth', 5, 50)
    min_samples_split = trial.suggest_int('min_samples_split', 2, 20)
    min_samples_leaf = trial.suggest_int('min_samples_leaf', 1, 20)
    
    rf = RandomForestRegressor(n_estimators=n_estimators, 
                               max_depth=max_depth, 
                               min_samples_split=min_samples_split,
                               min_samples_leaf=min_samples_leaf,
                               random_state=42)
    
    score = cross_val_score(rf, X_train, y_train, cv=5, scoring='neg_mean_squared_error', n_jobs=-1).mean()
    
    return score

study = optuna.create_study(direction='maximize', sampler = optuna.samplers.TPESampler(seed=42))
study.optimize(objective, n_trials=200)

print(study.best_params)

fig = optuna.visualization.plot_slice(study, params=['n_estimators', 'max_depth', 'min_samples_split', 'min_samples_leaf'])
show(fig)


"""""
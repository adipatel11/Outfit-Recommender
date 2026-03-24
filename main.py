import pandas as pd
import numpy as np


# Load data from Excel file

df1 = pd.read_excel('data.xlsx', sheet_name='data')
df2 = pd.read_excel('data.xlsx', sheet_name='metadata')


X = df1.iloc[:, :-1].values  # Features
y = df1.iloc[:, -1].values   # Target variable

# Gets the ideal warmth rating for a given temperature. 
def TempToWarmth(temp):
    return (-19/70)*(temp-90) + 1

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

from sklearn.ensemble import RandomForestClassifier

rf = RandomForestClassifier(n_estimators=1000, max_depth=10, random_state=42)
rf.fit(X_train, y_train)

y_pred = rf.predict(X_test)

# Evaluate the model

from sklearn.metrics import classification_report, confusion_matrix

print("Confusion Matrix:")
print(confusion_matrix(y_test, y_pred))
print("\nClassification Report:")
print(classification_report(y_test, y_pred))




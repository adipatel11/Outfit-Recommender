import itertools
import numpy as np
import pandas as pd
import joblib
import tkinter as tk
from PIL import Image, ImageTk
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer


def TempToWarmth(temp):
    return 4 + (12 / (1 + np.exp(-0.3 * (-temp + 55))))


# Load data
df1 = pd.read_excel('data.xlsx', sheet_name='data')
df2 = pd.read_excel('data.xlsx', sheet_name='metadata')

# Rebuild the ColumnTransformer fit so encoding matches what the model was trained on
X_raw = df1.iloc[:, :-1].values
tmp = []
for row in X_raw:
    top_info = df2[df2['Item'] == row[0]].iloc[:, 1:-1].values[0]
    bot_info  = df2[df2['Item'] == row[1]].iloc[:, 1:-1].values[0]
    tmp.append([top_info[0], bot_info[0],
                abs(top_info[1] - bot_info[1]),
                abs(top_info[2] + bot_info[2] - TempToWarmth(row[2]))])

ct = ColumnTransformer([("encoder", OneHotEncoder(sparse_output=False), [0, 1])], remainder='passthrough')
ct.fit(np.array(tmp))

rf = joblib.load('outfit_recommender_rf.joblib')

# Get temperature from user
temp = float(input("Enter temperature (°F): "))
warmth_target = TempToWarmth(temp)

# Cache item metadata to avoid repeated dataframe lookups
item_info = {row.iloc[0]: row.iloc[1:-1].values for _, row in df2.iterrows()}

tops    = df2[df2['Type'] == 'top']['Item'].tolist()
bottoms = df2[df2['Type'] == 'bottom']['Item'].tolist()

K = max(3, min(5, len(tops), len(bottoms)))

# Compute neutral top and bottom using median color/warmth and most common category
top_meta = np.array([item_info[t] for t in tops])
bot_meta = np.array([item_info[b] for b in bottoms])

neutral_top  = [pd.Series(top_meta[:, 0]).mode()[0], np.median(top_meta[:, 1].astype(float)), np.median(top_meta[:, 2].astype(float))]
neutral_bot  = [pd.Series(bot_meta[:, 0]).mode()[0], np.median(bot_meta[:, 1].astype(float)), np.median(bot_meta[:, 2].astype(float))]

# Shortlist top-K tops by scoring each against the neutral bottom
top_scores = []
for top in tops:
    info = item_info[top]
    features = [[info[0], neutral_bot[0],
                 abs(info[1] - neutral_bot[1]),
                 abs(info[2] + neutral_bot[2] - warmth_target)]]
    top_scores.append((rf.predict(ct.transform(features))[0], top))
shortlisted_tops = [t for _, t in sorted(top_scores, reverse=True)[:K]]

# Shortlist top-K bottoms by scoring each against the neutral top
bot_scores = []
for bottom in bottoms:
    info = item_info[bottom]
    features = [[neutral_top[0], info[0],
                 abs(neutral_top[1] - info[1]),
                 abs(neutral_top[2] + info[2] - warmth_target)]]
    bot_scores.append((rf.predict(ct.transform(features))[0], bottom))
shortlisted_bottoms = [b for _, b in sorted(bot_scores, reverse=True)[:K]]

# Evaluate only K² combinations among shortlisted items
best_score, best_top, best_bottom = -np.inf, None, None
for top, bottom in itertools.product(shortlisted_tops, shortlisted_bottoms):
    top_info = item_info[top]
    bot_info  = item_info[bottom]
    features = [[top_info[0], bot_info[0],
                 abs(top_info[1] - bot_info[1]),
                 abs(top_info[2] + bot_info[2] - warmth_target)]]
    score = rf.predict(ct.transform(features))[0]
    if score > best_score:
        best_score, best_top, best_bottom = score, top, bottom

# Display best outfit in tkinter
root = tk.Tk()
root.title("Best Outfit")

def open_scaled(path, width=200):
    img = Image.open(path)
    w, h = img.size
    return img.resize((width, int(h * width / w)), Image.LANCZOS)

top_img    = ImageTk.PhotoImage(open_scaled(f"item_pics/{best_top}.png"))
bottom_img = ImageTk.PhotoImage(open_scaled(f"item_pics/{best_bottom}.png"))

tk.Label(root, text=f"Best outfit for {temp}°F  (score: {best_score:.2f})", font=("Helvetica", 14)).pack(pady=8)
tk.Label(root, image=top_img).pack()
tk.Label(root, text=f"Top: Item {best_top}").pack()
tk.Label(root, image=bottom_img).pack()
tk.Label(root, text=f"Bottom: Item {best_bottom}").pack(pady=4)

root.mainloop()

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

# Score every top/bottom combination
tops    = df2[df2['Type'] == 'top']['Item'].tolist()
bottoms = df2[df2['Type'] == 'bottom']['Item'].tolist()

best_score, best_top, best_bottom = -np.inf, None, None
for top, bottom in itertools.product(tops, bottoms):
    top_info = df2[df2['Item'] == top].iloc[:, 1:-1].values[0]
    bot_info  = df2[df2['Item'] == bottom].iloc[:, 1:-1].values[0]
    features = [[top_info[0], bot_info[0],
                 abs(top_info[1] - bot_info[1]),
                 abs(top_info[2] + bot_info[2] - TempToWarmth(temp))]]
    score = rf.predict(ct.transform(features))[0]
    if score > best_score:
        best_score, best_top, best_bottom = score, top, bottom

# Display best outfit in tkinter
root = tk.Tk()
root.title("Best Outfit")

top_img    = ImageTk.PhotoImage(Image.open(f"item_pics/{best_top}.png").resize((200, 200)))
bottom_img = ImageTk.PhotoImage(Image.open(f"item_pics/{best_bottom}.png").resize((200, 200)))

tk.Label(root, text=f"Best outfit for {temp}°F  (score: {best_score:.2f})", font=("Helvetica", 14)).pack(pady=8)
tk.Label(root, image=top_img).pack()
tk.Label(root, text=f"Top: Item {best_top}").pack()
tk.Label(root, image=bottom_img).pack()
tk.Label(root, text=f"Bottom: Item {best_bottom}").pack(pady=4)

root.mainloop()

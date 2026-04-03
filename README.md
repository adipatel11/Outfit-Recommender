# Outfit Recommender

A machine learning system that recommends the best outfit for a given temperature. It learns your personal style by asking you to rate random outfit combinations, then trains a Random Forest model on your ratings to suggest the top + bottom pairing most suited to the weather.

## How It Works

1. **Rate outfits** — Run the data collection tool to score random top/bottom combinations on a scale of 1–10 at various temperatures.
2. **Train the model** — A Random Forest Regressor learns your preferences, using color, formality, and temperature-appropriate warmth as features.
3. **Get a recommendation** — Enter today's temperature and the app displays the best-scoring outfit with images.

## Project Structure

```
Outfit-Recommender/
├── make_data/
│   └── rate_outfits.py       # GUI tool for rating outfit combinations
├── item_pics/                 # PNG images of each clothing item (named by item ID)
├── data.xlsx                  # Training data and item metadata
├── train.py                   # Model training script
├── predict.py                 # Prediction and display script
├── outfit_recommender_rf.joblib  # Saved trained model
└── requirements.txt
```

## Setup

```bash
pip install -r requirements.txt
```

## Usage

### Step 1 — Collect Training Data

```bash
python make_data/rate_outfits.py
```

A window will display a random top + bottom at a random temperature. Press `1`–`9` or `0` (for 10) to score the outfit, or `Space` to skip. Ratings are saved to `data.xlsx` automatically.

### Step 2 — Train the Model

```bash
python train.py
```

Trains a Random Forest Regressor on your ratings and saves the model to `outfit_recommender_rf.joblib`. Prints MSE and R² on the test split.

### Step 3 — Get a Recommendation

```bash
python predict.py
```

Enter the current temperature in °F. A window will display the best-scoring top and bottom combination for that temperature.

## How the Model Works

Each outfit combination is represented by four features:

| Feature | Description |
|---|---|
| Color (top) | One-hot encoded color of the top |
| Color (bottom) | One-hot encoded color of the bottom |
| Formality difference | Absolute difference in formality rating between items |
| Warmth difference | How closely the outfit's combined warmth matches the ideal for the temperature |

The ideal warmth for a given temperature is calculated using a logistic curve, so the model learns both style preferences and weather-appropriateness simultaneously.

Hyperparameters were tuned using [Optuna](https://optuna.org/) with 200 trials of TPE sampling.

## Requirements

- Python 3.8+
- numpy, pandas, scikit-learn, Pillow, openpyxl, joblib
- optuna, plotly (for hyperparameter tuning only)

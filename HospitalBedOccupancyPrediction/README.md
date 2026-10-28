# Hospital Bed Occupancy Prediction Using Random Forest Regression

A complete, working Machine Learning mini-project built for college ML laboratory demonstrations and viva examinations.

The application forecasts daily hospital inpatient bed occupancy, occupancy rates (Bed Occupancy Rate — BOR %), and remaining buffer capacity for a selected future date using historical patient flow data and **Random Forest Regression**.

---

## 1. Project Objective

Hospital capacity crises, emergency department overcrowding, and ambulance diversion frequently occur when bed occupancy surpasses safe operational thresholds (typically 85%). 

This project provides an educational local web application that:
1. Ingests historical hospital census data (occupied beds, capacity, patient admissions, patient discharges, and timestamps).
2. Executes the complete supervised machine learning workflow from data cleaning to model deployment.
3. Predicts the expected number of occupied beds for a future target date.
4. Computes the predicted Bed Occupancy Rate:
   $$\text{Occupancy Percentage} = \left(\frac{\text{Predicted Occupied Beds}}{\text{Total Available Beds}}\right) \times 100$$
5. Determines remaining buffer capacity ($\text{Total Available Beds} - \text{Constrained Occupancy}$) and classifies the operational risk level (Safe, Optimal, Warning >85%, Severe Surge >95%).

> **Disclaimer:** This software is an **academic forecasting prototype** developed solely for college laboratory and machine learning demonstration. It is not clinically certified and must never be utilized as the sole basis for clinical triage, nurse staffing, or hospital bed dispatch.

---

## 2. Technologies Used

- **Python 3.10+ / 3.14**: Core programming language
- **Flask**: Lightweight local web server and REST routing
- **Scikit-learn (`sklearn.ensemble.RandomForestRegressor`)**: Ensemble machine learning modeling and evaluation
- **Pandas**: Structured time series data manipulation and preprocessing
- **NumPy**: Numerical matrix computations and bounding constraints
- **Matplotlib & Seaborn**: High-resolution medical analytics and diagnostic charts
- **Joblib**: Model serialization and artifact persistence
- **HTML5, CSS3, JavaScript**: Responsive clinical analytics web interface (Inter & Outfit typography)

---

## 3. Dataset Collection & Source

- **File Location:** `data/hospital_bed_occupancy.csv`
- **Data Provenance:** Public healthcare tracking census data aggregated from verified acute hospital capacity repositories (Sledilnik Acute Healthcare Census / COVID-19 Clinical Capacity Repository).
- **Observations:** 2,234 rows across two clinical wards:
  - `General Medical Ward` (1,117 daily records)
  - `Intensive Care Unit (ICU)` (1,117 daily records)
- **Time Range:** March 10, 2020 through March 31, 2023 (over 3 years of daily tracking)

### Dataset Schema

| Column Name | Data Type | Description |
| :--- | :--- | :--- |
| `date` | `datetime` (YYYY-MM-DD) | Daily timestamp of observation |
| `hospital_name` | `string` | Healthcare institution / facility identifier |
| `ward` | `string` | Clinical care department (`General Medical Ward`, `Intensive Care Unit (ICU)`) |
| `total_beds` | `integer` | Registered operational bed capacity |
| `occupied_beds` | `integer` | **Prediction Target:** Actual occupied beds at census cutoff |
| `admissions` | `integer` | Number of newly admitted patients on that date |
| `discharges` | `integer` | Number of discharged or transferred patients on that date |

---

## 4. Complete Machine Learning Workflow

The project implements all 10 stages of the supervised machine learning lifecycle:

1. **Problem Definition:** Formulate bed requirement forecasting as a supervised continuous regression task.
2. **Data Collection:** Retrieve authenticated time-series observations covering multiple departments.
3. **Data Preprocessing:** Validate numerical types, audit missing values, sort chronologically, and resolve operational surge overflow.
4. **Exploratory Data Analysis (EDA):** Generate high-resolution plots for occupancy trends, capacity percentages, patient flow comparisons, and feature correlations.
5. **Feature Selection:** Select predictors available strictly at prediction time ($t-1$ historical information).
6. **Feature Engineering:** Construct autoregressive lags, 7-day moving averages, and calendar seasonality features with zero lookahead bias.
7. **Train-Test Split:** Apply strict chronological splitting (80% historical training, 20% future testing).
8. **Model Training:** Fit a 100-tree Random Forest Regressor on the training split.
9. **Model Evaluation:** Measure performance using MAE, MSE, RMSE, and $R^2$; assess residuals for normality and homoscedasticity.
10. **Bed Occupancy Prediction:** Interactive local web form allowing administrators to test custom capacity and patient flow scenarios.

---

## 5. Feature Engineering & Selection

To prevent **target leakage** (data leakage), future day $t$ information is strictly prohibited:

- **Lag Features (Autoregressive):**
  - `lag_1_occupied_beds`: Occupied beds on day $t-1$
  - `lag_1_occupancy_rate`: $\text{Occupied Beds}_{t-1} / \text{Total Beds}_{t-1}$
  - `recent_admissions`: Patient admissions on day $t-1$
  - `recent_discharges`: Patient discharges on day $t-1$
- **Rolling Momentum Features:**
  - `rolling_7_occupied_beds`: 7-day moving average of occupied beds (shifted by 1 day)
  - `rolling_7_admissions`: 7-day moving average of new admissions
  - `rolling_7_discharges`: 7-day moving average of patient discharges
- **Calendar & Seasonality Features:**
  - `day_of_week`: 0 (Monday) to 6 (Sunday) — captures weekend elective admission drops
  - `month`: 1 to 12 — captures seasonal winter respiratory surges
  - `day_of_month`: 1 to 31
  - `is_weekend`: Binary flag (1 for Saturday/Sunday, 0 for weekdays)
- **Physical Capacity:**
  - `total_beds`: Registered ward capacity

---

## 6. Train-Test Split Strategy

Time series data exhibits strong temporal autocorrelation. **Random shuffling is strictly avoided** because training on future observations to predict past observations causes severe lookahead bias.

- **Split Ratio:** Chronological 80% Train, 20% Held-Out Test
- **Training Set:** 1,785 records (March 11, 2020 to August 20, 2022)
- **Testing Set:** 447 records (August 20, 2022 to March 31, 2023)

---

## 7. Model Training & Evaluation Metrics

The model is trained using `sklearn.ensemble.RandomForestRegressor(n_estimators=100, random_state=42)`.

### Test Split Quantitative Results

| Metric | Score | Clinical Meaning |
| :--- | :--- | :--- |
| **Mean Absolute Error (MAE)** | **3.132 beds** | The model's predictions deviate by an average of only ~3 beds from actual hospital census counts. |
| **Mean Squared Error (MSE)** | **22.296** | Average squared prediction error, heavily penalizing large outliers. |
| **Root Mean Squared Error (RMSE)** | **4.722 beds** | Standard deviation of prediction errors in actual bed units. |
| **Coefficient of Determination ($R^2$)** | **0.9833 (98.33%)** | Explains 98.33% of the total variance in hospital bed occupancy relative to the baseline mean. |

All metrics and plots are generated directly from held-out test data during training.

---

## 8. Project Structure

```text
HospitalBedOccupancyPrediction/
├── app.py                     # Flask web server and prediction routing
├── train_model.py             # Complete ML training & evaluation pipeline
├── download_dataset.py        # Automated dataset retriever & offline generator
├── requirements.txt           # Python dependencies
├── README.md                  # Project documentation & college viva guide
├── data/
│   ├── hospital_bed_occupancy.csv           # Original historical dataset
│   └── hospital_bed_occupancy_processed.csv # Feature-engineered dataset
├── models/
│   ├── bed_occupancy_model.pkl              # Serialized Random Forest model
│   └── model_metadata.json                  # Performance metrics & configuration
├── static/
│   ├── style.css              # Clinical analytics visual theme
│   └── plots/
│       ├── occupancy_over_time.png          # Historical occupancy trends
│       ├── occupancy_percentage.png         # Bed occupancy rate (%) vs 85% safety line
│       ├── admissions_discharges.png        # Patient flow (admissions vs discharges)
│       ├── feature_correlation.png          # Correlation matrix heatmap
│       ├── actual_vs_predicted.png          # Test set validation line chart
│       └── residual_analysis.png            # Normality & homoscedasticity scatter
└── templates/
    └── index.html             # Web interface with Figs 1–9 and prediction form
```

---

## 9. Installation & Execution Guide

### Step 1: Navigate to Project Directory
```powershell
cd HospitalBedOccupancyPrediction
```

### Step 2: Install Required Dependencies
```powershell
pip install -r requirements.txt
```

### Step 3: Run the Machine Learning Training Pipeline
This step loads the dataset, cleans records, generates all 6 visual analytics plots, fits the Random Forest Regressor, evaluates test metrics, and exports model artifacts:
```powershell
python train_model.py
```

### Step 4: Launch the Local Flask Web Application
```powershell
python app.py
```
Open your browser and navigate to:
```text
http://127.0.0.1:5000/
```

---

## 10. How to Use the Prediction Form

1. In the web interface, scroll to **Fig. 8 — Hospital Bed Occupancy Prediction Form** (or click **Predict Occupancy** in the top navigation).
2. Click one of the **Quick Sample Presets** (e.g., `⚡ General Medical Ward Preset` or `⚡ ICU Preset`) or manually enter:
   - **Ward**: Select `General Medical Ward` or `Intensive Care Unit (ICU)`
   - **Prediction Date**: Selected target date
   - **Total Available Beds**: Available ward capacity (e.g. 250)
   - **Historical Occupied Beds**: Previous-day baseline occupancy (e.g. 195)
   - **Recent Admissions**: New patient intake (e.g. 22)
   - **Recent Discharges**: Patient releases/transfers (e.g. 19)
3. Click **Predict Bed Occupancy**.
4. The system validates inputs, computes engineered features, queries the fitted model, applies operational boundaries, and renders:
   - **Predicted Occupied Beds**
   - **Predicted Occupancy Rate %**
   - **Remaining Buffer Capacity**
   - **Capacity Status Classification** (Safe, Optimal, Critical Warning >85%, Severe Surge >95%)

---

## 11. Viva Voce Questions & Answers (College Project Record)

**Q1: What type of machine learning problem is this?**  
*Answer:* Supervised Machine Learning, specifically continuous numerical regression, because the target variable (`occupied_beds`) is a continuous quantity predicted from historical input features.

**Q2: Why choose Random Forest Regression over Simple Linear Regression?**  
*Answer:* Hospital patient dynamics exhibit non-linear patterns (such as weekend elective drops, winter epidemic spikes, and non-linear bed turnover). Random Forest handles non-linear interactions, resists overfitting through bootstrap aggregation (bagging), and requires no assumptions of feature normality.

**Q3: How do you prevent data leakage in time series forecasting?**  
*Answer:* We shift all lag and rolling features by at least 1 day ($t-1$), ensuring the model never sees future admissions, discharges, or occupancy counts. Additionally, we use a chronological train-test split rather than random cross-validation.

**Q4: What is the clinical significance of the 85% occupancy threshold?**  
*Answer:* Healthcare literature (such as NHS England and WHO hospital standards) establishes 85% Bed Occupancy Rate as the safety ceiling. Beyond 85%, emergency department boarding times rise, hospital-acquired infection risks escalate, and elective surgeries are routinely canceled.

---

## 12. Limitations & Ethical Considerations

- **Data Generalization:** Predictions depend on the staffing and admission patterns of the training dataset. Changes in medical protocols, epidemics, or hospital expansion alter bed turnover dynamics.
- **Unforeseen Shocks:** Extreme natural disasters, mass-casualty incidents, or sudden epidemic waves cannot be predicted solely from historical patterns without external epidemiological signals.
- **Educational Scope:** This project serves as an educational prototype and should not replace experienced clinical hospital capacity managers.

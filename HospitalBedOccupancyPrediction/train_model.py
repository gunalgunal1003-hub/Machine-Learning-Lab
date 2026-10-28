"""
Hospital Bed Occupancy Prediction Using Random Forest Regression
Complete Machine Learning Training Pipeline:
1. Load dataset
2. Inspect & Preprocess (missing values, duplicates, consistency checks)
3. Exploratory Data Analysis (EDA) visualizations
4. Feature Engineering (lag features, rolling averages, calendar features)
5. Chronological Train-Test Split (80/20)
6. Model Training (Random Forest Regressor)
7. Model Evaluation (MAE, MSE, RMSE, R²)
8. Evaluation Plots (Actual vs Predicted, Residual Analysis)
9. Artifact Preservation (Model pkl, metadata json, processed dataset)
"""

import os
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for local server/headless execution
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import joblib

# Set professional styling for medical analytics charts
plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
plt.rcParams.update({
    "font.sans-serif": ["Segoe UI", "DejaVu Sans", "Helvetica", "Arial"],
    "font.family": "sans-serif",
    "figure.titlesize": 14,
    "axes.titlesize": 13,
    "axes.labelsize": 11,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "figure.autolayout": True
})

PRIMARY_COLOR = "#2563eb"    # Clinical Blue
SECONDARY_COLOR = "#0d9488"  # Medical Teal
ACCENT_COLOR = "#dc2626"     # Alert Red
DARK_NEUTRAL = "#0f172a"     # Slate Navy
LIGHT_BG = "#f8fafc"         # Clean Off-White

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, "data")
    models_dir = os.path.join(base_dir, "models")
    plots_dir = os.path.join(base_dir, "static", "plots")
    
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(models_dir, exist_ok=True)
    os.makedirs(plots_dir, exist_ok=True)
    
    raw_csv = os.path.join(data_dir, "hospital_bed_occupancy.csv")
    processed_csv = os.path.join(data_dir, "hospital_bed_occupancy_processed.csv")
    model_path = os.path.join(models_dir, "bed_occupancy_model.pkl")
    metadata_path = os.path.join(models_dir, "model_metadata.json")

    # Step 1: Check dataset existence
    if not os.path.exists(raw_csv):
        raise FileNotFoundError(
            f"Expected dataset not found at {raw_csv}. "
            f"Please run download_dataset.py first to acquire the verified hospital dataset."
        )

    print("=================================================================")
    print("Hospital Bed Occupancy Prediction — ML Training Pipeline")
    print("Algorithm: Random Forest Regression (Supervised Learning)")
    print("=================================================================")

    # Step 2: Load raw data
    df_raw = pd.read_csv(raw_csv)
    raw_count = len(df_raw)
    raw_cols = df_raw.columns.tolist()
    missing_raw = int(df_raw.isna().sum().sum())
    duplicates_raw = int(df_raw.duplicated().sum())

    print(f"\n[+] Step 2: Raw Dataset Loaded Successfully")
    print(f"    - Dimensions: {df_raw.shape[0]} rows, {df_raw.shape[1]} columns")
    print(f"    - Columns: {raw_cols}")
    print(f"    - Missing values detected: {missing_raw}")
    print(f"    - Duplicate rows detected: {duplicates_raw}")

    # Step 3: Data Preprocessing
    print(f"\n[+] Step 3: Data Preprocessing & Validation")
    df = df_raw.copy()
    df["date"] = pd.to_datetime(df["date"])
    
    # Ensure numeric columns
    numeric_cols = ["total_beds", "occupied_beds", "admissions", "discharges"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    
    # Drop any null records created by coercion
    df = df.dropna(subset=numeric_cols).reset_index(drop=True)
    
    # Remove negative counts
    df = df[(df["total_beds"] > 0) & 
            (df["occupied_beds"] >= 0) & 
            (df["admissions"] >= 0) & 
            (df["discharges"] >= 0)].copy()

    # Constraint check: Cap occupied beds at total_beds to reflect operational reality
    inconsistent_bed_count = int((df["occupied_beds"] > df["total_beds"]).sum())
    print(f"    - Records with surge occupancy exceeding registered baseline: {inconsistent_bed_count}")
    df["occupied_beds"] = np.minimum(df["occupied_beds"], df["total_beds"])
    df["occupancy_percentage"] = (df["occupied_beds"] / df["total_beds"]) * 100.0

    # Sort strictly chronologically
    df = df.sort_values(by=["ward", "date"]).reset_index(drop=True)
    retained_count = len(df)
    date_min = df["date"].min().strftime("%Y-%m-%d")
    date_max = df["date"].max().strftime("%Y-%m-%d")

    print(f"    - Retained records after cleaning: {retained_count}")
    print(f"    - Date Range: {date_min} to {date_max}")

    # Step 4: Generate Exploratory Data Analysis (EDA) Plots
    print(f"\n[+] Step 4: Generating Exploratory Data Analysis (EDA) Plots...")
    generate_eda_plots(df, plots_dir)

    # Step 5: Feature Engineering
    print(f"\n[+] Step 5: Feature Engineering & Selection")
    print("    - Creating calendar features: day_of_week, month, day_of_month, is_weekend")
    print("    - Creating lag features: lag_1_occupied_beds, lag_1_occupancy_rate")
    print("    - Creating rolling features: 7-day rolling occupied beds, admissions, discharges")
    print("    - CRITICAL: Features use shift(1) strictly ensuring NO future target leakage!")

    wards_features = []
    for ward_name, group in df.groupby("ward"):
        g = group.copy().sort_values("date")
        
        # Calendar features
        g["day_of_week"] = g["date"].dt.day_of_week
        g["month"] = g["date"].dt.month
        g["day_of_month"] = g["date"].dt.day
        g["is_weekend"] = (g["day_of_week"] >= 5).astype(int)
        
        # Lag-1 features (known from day t-1)
        g["lag_1_occupied_beds"] = g["occupied_beds"].shift(1)
        g["lag_1_occupancy_rate"] = (g["occupied_beds"] / g["total_beds"]).shift(1)
        g["recent_admissions"] = g["admissions"].shift(1)
        g["recent_discharges"] = g["discharges"].shift(1)
        
        # Rolling 7-day features (shifted by 1 to strictly prevent lookahead)
        g["rolling_7_occupied_beds"] = g["occupied_beds"].shift(1).rolling(window=7, min_periods=1).mean()
        g["rolling_7_admissions"] = g["admissions"].shift(1).rolling(window=7, min_periods=1).mean()
        g["rolling_7_discharges"] = g["discharges"].shift(1).rolling(window=7, min_periods=1).mean()
        
        wards_features.append(g)

    df_featured = pd.concat(wards_features).dropna().sort_values("date").reset_index(drop=True)
    
    # Save processed dataset
    df_featured_save = df_featured.copy()
    df_featured_save["date"] = df_featured_save["date"].dt.strftime("%Y-%m-%d")
    df_featured_save.to_csv(processed_csv, index=False)
    print(f"    - Processed dataset saved to: {processed_csv}")

    # Step 6: Feature Selection
    feature_cols = [
        "total_beds",
        "lag_1_occupied_beds",
        "lag_1_occupancy_rate",
        "rolling_7_occupied_beds",
        "recent_admissions",
        "recent_discharges",
        "rolling_7_admissions",
        "rolling_7_discharges",
        "day_of_week",
        "month",
        "day_of_month",
        "is_weekend"
    ]
    target_col = "occupied_beds"

    # Step 7: Chronological Train-Test Split (80% Train, 20% Test)
    print(f"\n[+] Step 7: Chronological Train-Test Split (Preserving Time Series Order)")
    split_index = int(len(df_featured) * 0.8)
    train_df = df_featured.iloc[:split_index].copy()
    test_df = df_featured.iloc[split_index:].copy()

    X_train = train_df[feature_cols]
    y_train = train_df[target_col]
    X_test = test_df[feature_cols]
    y_test = test_df[target_col]

    train_dates = (train_df["date"].min().strftime("%Y-%m-%d"), train_df["date"].max().strftime("%Y-%m-%d"))
    test_dates = (test_df["date"].min().strftime("%Y-%m-%d"), test_df["date"].max().strftime("%Y-%m-%d"))

    print(f"    - Training records: {len(X_train)} (Date Range: {train_dates[0]} to {train_dates[1]})")
    print(f"    - Testing records:  {len(X_test)} (Date Range: {test_dates[0]} to {test_dates[1]})")

    # Step 8: Random Forest Model Training
    print(f"\n[+] Step 8: Training Random Forest Regressor...")
    rf_model = RandomForestRegressor(
        n_estimators=100,
        random_state=42,
        max_depth=12,
        min_samples_split=4,
        min_samples_leaf=2,
        n_jobs=-1
    )
    rf_model.fit(X_train, y_train)
    print("    - Model training completed successfully.")

    # Step 9: Model Evaluation on Held-Out Test Data
    print(f"\n[+] Step 9: Evaluating Model on Held-Out Test Period...")
    test_predictions = rf_model.predict(X_test)
    
    mae = float(mean_absolute_error(y_test, test_predictions))
    mse = float(mean_squared_error(y_test, test_predictions))
    rmse = float(np.sqrt(mse))
    r2 = float(r2_score(y_test, test_predictions))

    print(f"    ---------------------------------------------")
    print(f"    Evaluation Metric                 Score")
    print(f"    ---------------------------------------------")
    print(f"    Mean Absolute Error (MAE):       {mae:.3f} beds")
    print(f"    Mean Squared Error (MSE):        {mse:.3f}")
    print(f"    Root Mean Squared Error (RMSE):  {rmse:.3f} beds")
    print(f"    R² Score (Variance Explained):   {r2:.4f} ({r2*100:.2f}%)")
    print(f"    ---------------------------------------------")

    # Step 10: Generate Evaluation Plots
    print(f"\n[+] Step 10: Generating Evaluation & Residual Plots...")
    generate_evaluation_plots(test_df, y_test, test_predictions, plots_dir)

    # Feature Importance analysis
    importances = rf_model.feature_importances_
    feat_imp = sorted(zip(feature_cols, importances), key=lambda x: x[1], reverse=True)
    print("    - Top 5 Feature Importances:")
    for f, imp in feat_imp[:5]:
        print(f"      * {f:<26}: {imp:.4f}")

    # Step 11: Save Model & Metadata Artifacts
    print(f"\n[+] Step 11: Preserving Model Artifacts...")
    joblib.dump(rf_model, model_path)
    print(f"    - Model binary saved to: {model_path}")

    # Build comprehensive metadata for the Flask UI
    metadata = {
        "project_name": "Hospital Bed Occupancy Prediction Using Random Forest Regression",
        "algorithm": "Random Forest Regression (sklearn.ensemble.RandomForestRegressor)",
        "model_parameters": {
            "n_estimators": 100,
            "random_state": 42,
            "max_depth": 12,
            "min_samples_split": 4,
            "min_samples_leaf": 2
        },
        "dataset_summary": {
            "raw_records": raw_count,
            "retained_records": retained_count,
            "missing_values_handled": missing_raw,
            "duplicates_removed": duplicates_raw,
            "inconsistent_bed_records_handled": inconsistent_bed_count,
            "date_range_start": date_min,
            "date_range_end": date_max,
            "wards": list(df["ward"].unique()),
            "provenance": "Verified Public Healthcare Tracking Dataset (Sledilnik Healthcare / COVID-19 Acute Care Data)",
            "target_variable": target_col
        },
        "train_test_split": {
            "strategy": "Chronological (Time-Based Non-Shuffled)",
            "train_ratio": 0.80,
            "test_ratio": 0.20,
            "train_records": len(X_train),
            "test_records": len(X_test),
            "train_dates": f"{train_dates[0]} to {train_dates[1]}",
            "test_dates": f"{test_dates[0]} to {test_dates[1]}"
        },
        "evaluation_metrics": {
            "mae": round(mae, 3),
            "mse": round(mse, 3),
            "rmse": round(rmse, 3),
            "r2_score": round(r2, 4),
            "r2_percentage": round(r2 * 100, 2)
        },
        "features": feature_cols,
        "feature_importances": {f: round(float(imp), 4) for f, imp in feat_imp}
    }

    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=4)
    print(f"    - Metadata JSON saved to: {metadata_path}")

    print("\n=================================================================")
    print("SUCCESS: Machine Learning Pipeline Completed!")
    print("Ready for Flask Web Application Execution.")
    print("=================================================================")

def generate_eda_plots(df, plots_dir):
    """Generates all required EDA charts from real dataset values."""
    
    # 1. Bed Occupancy Over Time
    fig, ax = plt.subplots(figsize=(10, 4.8), dpi=150)
    for ward, grp in df.groupby("ward"):
        ax.plot(grp["date"], grp["occupied_beds"], label=f"{ward} (Occupied)", linewidth=2)
        ax.plot(grp["date"], grp["total_beds"], linestyle="--", alpha=0.5, label=f"{ward} (Capacity)")
    ax.set_title("Historical Hospital Bed Occupancy & Capacity Over Time", fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Date", fontsize=11)
    ax.set_ylabel("Number of Beds", fontsize=11)
    ax.legend(frameon=True, facecolor="white", edgecolor="#e2e8f0", loc="upper left", fontsize=9)
    ax.grid(True, linestyle=":", alpha=0.6)
    plt.savefig(os.path.join(plots_dir, "occupancy_over_time.png"), bbox_inches="tight")
    plt.close()

    # 2. Occupancy Percentage Over Time
    fig, ax = plt.subplots(figsize=(10, 4.8), dpi=150)
    for ward, grp in df.groupby("ward"):
        ax.plot(grp["date"], grp["occupancy_percentage"], label=f"{ward} BOR (%)", linewidth=1.8)
    # Recommended operational threshold line (85% standard)
    ax.axhline(85, color=ACCENT_COLOR, linestyle="--", linewidth=1.8, label="Critical Safety Threshold (85%)")
    ax.set_title("Bed Occupancy Rate (BOR %) Relative to Capacity Over Time", fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Date", fontsize=11)
    ax.set_ylabel("Occupancy Rate (%)", fontsize=11)
    ax.set_ylim(0, 105)
    ax.legend(frameon=True, facecolor="white", edgecolor="#e2e8f0", loc="upper right", fontsize=9)
    ax.grid(True, linestyle=":", alpha=0.6)
    plt.savefig(os.path.join(plots_dir, "occupancy_percentage.png"), bbox_inches="tight")
    plt.close()

    # 3. Patient Admissions and Discharges Comparison Over Time
    fig, ax = plt.subplots(figsize=(10, 4.8), dpi=150)
    daily_totals = df.groupby("date")[["admissions", "discharges"]].sum().reset_index()
    # 7-day rolling smoothing for clearer visual trend comparison
    daily_totals["adm_roll"] = daily_totals["admissions"].rolling(7, min_periods=1).mean()
    daily_totals["dis_roll"] = daily_totals["discharges"].rolling(7, min_periods=1).mean()
    
    ax.plot(daily_totals["date"], daily_totals["adm_roll"], color=PRIMARY_COLOR, label="Daily Admissions (7-day Avg)", linewidth=2)
    ax.plot(daily_totals["date"], daily_totals["dis_roll"], color=SECONDARY_COLOR, label="Daily Discharges (7-day Avg)", linewidth=2, linestyle="-.")
    ax.set_title("Patient Flow: Admissions vs. Discharges Over Time", fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Date", fontsize=11)
    ax.set_ylabel("Patients per Day", fontsize=11)
    ax.legend(frameon=True, facecolor="white", edgecolor="#e2e8f0", loc="upper right", fontsize=9)
    ax.grid(True, linestyle=":", alpha=0.6)
    plt.savefig(os.path.join(plots_dir, "admissions_discharges.png"), bbox_inches="tight")
    plt.close()

    # 4. Feature Correlation Heatmap
    fig, ax = plt.subplots(figsize=(8, 6.2), dpi=150)
    corr_cols = ["occupied_beds", "total_beds", "admissions", "discharges", "occupancy_percentage"]
    corr_matrix = df[corr_cols].corr()
    mask = np.triu(np.ones_like(corr_matrix, dtype=bool))
    cmap = sns.diverging_palette(220, 20, as_cmap=True)
    sns.heatmap(
        corr_matrix,
        mask=mask,
        annot=True,
        fmt=".2f",
        cmap="Blues",
        vmin=-1,
        vmax=1,
        square=True,
        linewidths=1.2,
        cbar_kws={"shrink": 0.8},
        ax=ax
    )
    ax.set_title("Correlation Heatmap: Key Operational Variables", fontsize=13, fontweight="bold", pad=14)
    plt.savefig(os.path.join(plots_dir, "feature_correlation.png"), bbox_inches="tight")
    plt.close()

def generate_evaluation_plots(test_df, y_true, y_pred, plots_dir):
    """Generates actual-vs-predicted and residual analysis plots."""
    
    eval_df = test_df.copy()
    eval_df["actual"] = y_true.values
    eval_df["predicted"] = y_pred
    eval_df["residual"] = eval_df["actual"] - eval_df["predicted"]

    # 1. Actual vs Predicted Line Chart
    fig, ax = plt.subplots(figsize=(10, 4.8), dpi=150)
    for ward, grp in eval_df.groupby("ward"):
        ax.plot(grp["date"], grp["actual"], label=f"{ward} (Actual)", alpha=0.75, linewidth=1.8)
        ax.plot(grp["date"], grp["predicted"], label=f"{ward} (RF Predicted)", linestyle="--", linewidth=1.8)
    ax.set_title("Actual vs. Random Forest Predicted Bed Occupancy (Test Period)", fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Date", fontsize=11)
    ax.set_ylabel("Occupied Beds", fontsize=11)
    ax.legend(frameon=True, facecolor="white", edgecolor="#e2e8f0", loc="upper left", fontsize=9)
    ax.grid(True, linestyle=":", alpha=0.6)
    plt.savefig(os.path.join(plots_dir, "actual_vs_predicted.png"), bbox_inches="tight")
    plt.close()

    # 2. Residual Analysis: Distribution & Scatter Plot
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5), dpi=150)
    
    # Residual Distribution
    sns.histplot(eval_df["residual"], kde=True, color=PRIMARY_COLOR, bins=25, ax=ax1)
    ax1.axvline(0, color=ACCENT_COLOR, linestyle="--", linewidth=1.5)
    ax1.set_title("Residual Error Distribution", fontsize=12, fontweight="bold")
    ax1.set_xlabel("Residual (Actual - Predicted Beds)", fontsize=10)
    ax1.set_ylabel("Frequency", fontsize=10)

    # Residuals vs Predicted Values
    ax2.scatter(eval_df["predicted"], eval_df["residual"], alpha=0.5, color=SECONDARY_COLOR, edgecolor="#0f766e", s=30)
    ax2.axhline(0, color=ACCENT_COLOR, linestyle="--", linewidth=1.5)
    ax2.set_title("Residuals vs. Predicted Occupied Beds", fontsize=12, fontweight="bold")
    ax2.set_xlabel("Predicted Occupied Beds", fontsize=10)
    ax2.set_ylabel("Residual Error", fontsize=10)
    ax2.grid(True, linestyle=":", alpha=0.6)

    plt.suptitle("Model Residual Error Analysis (Homoscedasticity & Normality Check)", fontsize=13, fontweight="bold", y=1.02)
    plt.savefig(os.path.join(plots_dir, "residual_analysis.png"), bbox_inches="tight")
    plt.close()

if __name__ == "__main__":
    main()

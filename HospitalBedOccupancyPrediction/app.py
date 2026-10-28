"""
Hospital Bed Occupancy Prediction Using Random Forest Regression
Flask Web Application
"""

import os
import json
import datetime
import pandas as pd
import numpy as np
from flask import Flask, render_template, request, jsonify, redirect, url_for
import joblib

app = Flask(__name__)

# Base Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE_DIR, "models")
DATA_DIR = os.path.join(BASE_DIR, "data")
PLOTS_DIR = os.path.join(BASE_DIR, "static", "plots")

MODEL_PATH = os.path.join(MODELS_DIR, "bed_occupancy_model.pkl")
METADATA_PATH = os.path.join(MODELS_DIR, "model_metadata.json")
PROCESSED_DATA_PATH = os.path.join(DATA_DIR, "hospital_bed_occupancy_processed.csv")
RAW_DATA_PATH = os.path.join(DATA_DIR, "hospital_bed_occupancy.csv")

# Global Cache for Model & Metadata
model = None
metadata = None
processed_df = None

def load_system_artifacts():
    global model, metadata, processed_df
    try:
        if os.path.exists(MODEL_PATH):
            model = joblib.load(MODEL_PATH)
        if os.path.exists(METADATA_PATH):
            with open(METADATA_PATH, "r") as f:
                metadata = json.load(f)
        if os.path.exists(PROCESSED_DATA_PATH):
            processed_df = pd.read_csv(PROCESSED_DATA_PATH)
        elif os.path.exists(RAW_DATA_PATH):
            processed_df = pd.read_csv(RAW_DATA_PATH)
    except Exception as e:
        print(f"[!] Error loading model artifacts: {e}")

# Load artifacts upon startup
load_system_artifacts()

@app.route("/")
def index():
    # If artifacts are missing, offer setup guide
    if model is None or metadata is None:
        return render_template(
            "index.html",
            setup_required=True,
            error_message="Model artifacts not found. Please execute 'python train_model.py' to generate model and visual analytics."
        )

    # Prepare preview records for display (Fig. 1)
    preview_records = []
    if processed_df is not None:
        sample_cols = ["date", "hospital_name", "ward", "total_beds", "occupied_beds", "admissions", "discharges"]
        available_cols = [c for c in sample_cols if c in processed_df.columns]
        preview_records = processed_df[available_cols].head(6).to_dict(orient="records")

    # Pass everything to template
    return render_template(
        "index.html",
        setup_required=False,
        metadata=metadata,
        preview_records=preview_records,
        current_date=datetime.date.today().strftime("%Y-%m-%d"),
        prediction=None,
        form_data=None,
        form_error=None
    )

@app.route("/predict", methods=["POST"])
def predict():
    if model is None or metadata is None:
        return jsonify({"success": False, "error": "Model not loaded. Run train_model.py first."}), 500

    form_data = request.form.to_dict() if request.form else (request.get_json() or {})
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json

    # 1. Input Validation
    ward = form_data.get("ward", "").strip()
    prediction_date_str = form_data.get("prediction_date", "").strip()
    total_beds_str = form_data.get("total_beds", "").strip()
    lag_1_occupied_str = form_data.get("lag_1_occupied_beds", "").strip()
    recent_admissions_str = form_data.get("recent_admissions", "").strip()
    recent_discharges_str = form_data.get("recent_discharges", "").strip()

    errors = []

    # Validate Ward
    available_wards = metadata.get("dataset_summary", {}).get("wards", ["General Medical Ward", "Intensive Care Unit (ICU)"])
    if not ward or ward not in available_wards:
        ward = available_wards[0] if available_wards else "General Medical Ward"

    # Validate Date
    try:
        pred_date = datetime.datetime.strptime(prediction_date_str, "%Y-%m-%d").date()
    except Exception:
        errors.append("Invalid Prediction Date format. Please use YYYY-MM-DD.")
        pred_date = datetime.date.today()

    # Validate Numerical Fields
    try:
        total_beds = float(total_beds_str)
        if total_beds <= 0:
            errors.append("Total Available Beds must be a positive number greater than 0.")
    except (ValueError, TypeError):
        errors.append("Total Available Beds must be a valid numeric quantity.")
        total_beds = 100.0

    try:
        lag_1_occupied = float(lag_1_occupied_str)
        if lag_1_occupied < 0:
            errors.append("Recent/Previous-Day Occupied Beds cannot be negative.")
        elif lag_1_occupied > total_beds * 2.0:
            errors.append(f"Recent Occupied Beds ({lag_1_occupied}) is unrealistically high compared to capacity ({total_beds}).")
    except (ValueError, TypeError):
        errors.append("Previous-Day Occupied Beds must be a valid number.")
        lag_1_occupied = 70.0

    try:
        recent_admissions = float(recent_admissions_str)
        if recent_admissions < 0:
            errors.append("Recent Admissions cannot be negative.")
    except (ValueError, TypeError):
        errors.append("Recent Admissions must be a valid number.")
        recent_admissions = 10.0

    try:
        recent_discharges = float(recent_discharges_str)
        if recent_discharges < 0:
            errors.append("Recent Discharges cannot be negative.")
    except (ValueError, TypeError):
        errors.append("Recent Discharges must be a valid number.")
        recent_discharges = 8.0

    if errors:
        error_msg = " | ".join(errors)
        if is_ajax:
            return jsonify({"success": False, "error": error_msg}), 400
        preview_records = processed_df.head(6).to_dict(orient="records") if processed_df is not None else []
        return render_template(
            "index.html",
            setup_required=False,
            metadata=metadata,
            preview_records=preview_records,
            prediction=None,
            form_data=form_data,
            form_error=error_msg
        )

    # 2. Feature Extraction matching train_model.py exactly
    day_of_week = pred_date.weekday()  # 0=Monday, 6=Sunday
    month = pred_date.month
    day_of_month = pred_date.day
    is_weekend = 1 if day_of_week >= 5 else 0

    lag_1_occupancy_rate = lag_1_occupied / max(1.0, total_beds)
    
    # 7-day rolling approximations based on recent trajectory
    rolling_7_occupied = lag_1_occupied
    rolling_7_admissions = recent_admissions
    rolling_7_discharges = recent_discharges

    # Build input feature vector
    feature_names = metadata.get("features", [
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
    ])

    input_dict = {
        "total_beds": total_beds,
        "lag_1_occupied_beds": lag_1_occupied,
        "lag_1_occupancy_rate": lag_1_occupancy_rate,
        "rolling_7_occupied_beds": rolling_7_occupied,
        "recent_admissions": recent_admissions,
        "recent_discharges": recent_discharges,
        "rolling_7_admissions": rolling_7_admissions,
        "rolling_7_discharges": rolling_7_discharges,
        "day_of_week": day_of_week,
        "month": month,
        "day_of_month": day_of_month,
        "is_weekend": is_weekend
    }

    input_df = pd.DataFrame([input_dict])[feature_names]

    # 3. Model Inference
    raw_prediction = float(model.predict(input_df)[0])
    
    # Sensible operational constraint:
    # Cannot be negative; cannot exceed physical capacity in standard operation
    operational_prediction = int(round(max(0.0, min(total_beds, raw_prediction))))
    constrained_flag = (raw_prediction < 0 or raw_prediction > total_beds)

    # Output Calculations
    occupancy_percentage = round((operational_prediction / total_beds) * 100.0, 1)
    remaining_beds = int(max(0.0, total_beds - operational_prediction))

    # Operational status classification
    if occupancy_percentage >= 95.0:
        status_label = "Severe Capacity Surge"
        status_class = "status-danger"
        status_desc = "Ward is approaching full saturation. Immediate bed diversion or surge protocols advised."
    elif occupancy_percentage >= 85.0:
        status_label = "Critical High Utilization"
        status_class = "status-warning"
        status_desc = "Above the 85% clinical safety threshold. High risk of emergency admission bottlenecks."
    elif occupancy_percentage >= 65.0:
        status_label = "Optimal Operating Capacity"
        status_class = "status-success"
        status_desc = "Healthy bed turnover with adequate buffer capacity for elective and emergency demand."
    else:
        status_label = "Under-Utilized Capacity"
        status_class = "status-info"
        status_desc = "Substantial vacant bed availability. Operational resources well within buffer limits."

    result = {
        "success": True,
        "ward": ward,
        "prediction_date": pred_date.strftime("%Y-%m-%d"),
        "day_name": pred_date.strftime("%A"),
        "total_beds": int(total_beds),
        "raw_predicted_beds": round(raw_prediction, 2),
        "operational_occupied_beds": operational_prediction,
        "occupancy_percentage": occupancy_percentage,
        "remaining_beds": remaining_beds,
        "is_constrained": constrained_flag,
        "status_label": status_label,
        "status_class": status_class,
        "status_desc": status_desc,
        "inputs_used": {
            "lag_1_occupied": int(lag_1_occupied),
            "recent_admissions": int(recent_admissions),
            "recent_discharges": int(recent_discharges),
            "day_of_week": day_of_week,
            "month": month,
            "is_weekend": bool(is_weekend)
        }
    }

    if is_ajax:
        return jsonify(result)

    preview_records = processed_df.head(6).to_dict(orient="records") if processed_df is not None else []
    return render_template(
        "index.html",
        setup_required=False,
        metadata=metadata,
        preview_records=preview_records,
        prediction=result,
        form_data=form_data,
        form_error=None
    )

@app.route("/api/sample-data/<ward_name>")
def get_sample_data(ward_name):
    """Provides instant preset values for testing and demonstration."""
    if ward_name == "Intensive Care Unit (ICU)":
        return jsonify({
            "total_beds": 35,
            "lag_1_occupied_beds": 26,
            "recent_admissions": 5,
            "recent_discharges": 4,
            "prediction_date": (datetime.date.today() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        })
    else:  # General Medical Ward
        return jsonify({
            "total_beds": 250,
            "lag_1_occupied_beds": 195,
            "recent_admissions": 22,
            "recent_discharges": 19,
            "prediction_date": (datetime.date.today() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        })

@app.route("/api/health")
def health():
    return jsonify({
        "status": "healthy",
        "model_loaded": model is not None,
        "metadata_loaded": metadata is not None,
        "processed_data_loaded": processed_df is not None
    })

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)

import joblib
import numpy as np
import pandas as pd
from flask import Flask, render_template, request

app = Flask(__name__)

# Load trained model
pipe = joblib.load("mobile_price_predictor.pkl")


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/predict", methods=["POST"])
def predict():
    try:
        # Basic user inputs
        brand = request.form["brand"]
        name = request.form["name"]
        processor = request.form["processor"]
        ram_gb = float(request.form["ram_gb"])
        storage_gb = float(request.form["storage_gb"])
        rear_camera_mp = float(request.form["rear_camera_mp"])
        front_camera_mp = float(request.form["front_camera_mp"])
        battery_category = request.form["battery_category"]
        feature_score = float(request.form["feature_score"])

        # Derived features
        total_camera_mp = rear_camera_mp + front_camera_mp
        is_high_ram = 1 if ram_gb >= 8 else 0
        is_fast_charging = 1
        fast_charging_w = 45
        display_width = 1080
        display_ppi = 400
        refresh_rate_hz = 120
        rear_camera_count = 3
        total_pixels = 1080 * 2400
        has_nfc = 1
        cores = "octa"
        price_per_gb_ram = 0
        price_per_gb_storage = 0
        price_category = "flagship"

        # Create dataframe
        new_data = pd.DataFrame(
            [
                {
                    "brand": brand,
                    "name": name,
                    "processor": processor,
                    "processor_speed_ghz": 3.2,
                    "ram_gb": ram_gb,
                    "storage_gb": storage_gb,
                    "display_width": display_width,
                    "display_ppi": display_ppi,
                    "refresh_rate_hz": refresh_rate_hz,
                    "rear_camera_mp": rear_camera_mp,
                    "front_camera_mp": front_camera_mp,
                    "total_camera_mp": total_camera_mp,
                    "total_pixels": total_pixels,
                    "rear_camera_count": rear_camera_count,
                    "has_nfc": has_nfc,
                    "fast_charging_w": fast_charging_w,
                    "is_fast_charging": is_fast_charging,
                    "is_high_ram": is_high_ram,
                    "feature_score": feature_score,
                    "battery_category": battery_category,
                    "price_category": price_category,
                    "cores": cores,
                    "price_per_gb_ram": price_per_gb_ram,
                    "price_per_gb_storage": price_per_gb_storage,
                }
            ]
        )

        # Prediction
        log_pred = pipe.predict(new_data)[0]
        price = np.expm1(log_pred)

        return render_template(
            "index.html", prediction_text=f"Predicted Price: ₹{price:,.2f}"
        )

    except Exception as e:
        return render_template("index.html", prediction_text=f"Error: {e}")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)

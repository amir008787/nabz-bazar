import os
import os
from flask import Flask, jsonify, send_file
import requests

app = Flask(__name__)

API_URL = "https://nerkhara.com/api/v1/latest.json"

@app.route("/")
def home():
    return send_file("index.html")

@app.route("/api/prices")
def prices():
    try:
        response = requests.get(API_URL, timeout=15)
        response.raise_for_status()
        items = response.json()["items"]

        wanted = [
            "usd", "eur", "gold-18k",
            "coin-emami", "coin-half", "coin-quarter"
        ]

        data = {
            item["id"]: {
                "price": item["price"],
                "unit": item["unit"],
                "updated": item["updated_utc"],
                "stale": item["stale"]
            }
            for item in items
            if item["id"] in wanted
        }

        return jsonify({"prices": data})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

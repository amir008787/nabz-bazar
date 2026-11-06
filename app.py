import os
from flask import Flask, jsonify, send_file
import requests

app = Flask(__name__)

API_URL = "https://talasanj.info/api/v1/prices"

@app.route("/")
def home():
    return send_file("index.html")

@app.route("/api/prices")
def prices():
    try:
        key = os.environ.get("TALASANJ_API_KEY")

        headers = {
            "Authorization": f"Bearer {key}",
            "X-Client-Name": "Nabz Bazar",
            "X-Client-Url": "https://nabz-bazar.fadehost.app"
        }

        response = requests.get(API_URL, headers=headers, timeout=15)
        response.raise_for_status()

        result = response.json()

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))	


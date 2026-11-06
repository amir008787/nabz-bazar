import os
import json
import time
import threading
import logging
from datetime import datetime, timezone

import requests
from flask import Flask, jsonify, send_file

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

API_URL = "https://talasanj.info/api/v1/prices"
CACHE_FILE = "prices_cache.json"
REFRESH_INTERVAL = 20
REQUEST_TIMEOUT = 12

EITA_TOKEN = os.environ.get("EITA_BOT_TOKEN")
EITA_API = "https://eitaayar.ir/api"

cache_lock = threading.Lock()
refresh_lock = threading.Lock()

cache = {
    "data": None,
    "last_success": None,
    "last_error": None
}


def load_cache():
    global cache

    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, "r", encoding="utf-8") as file:
                saved = json.load(file)

            if isinstance(saved, dict) and saved.get("data"):
                cache["data"] = saved["data"]
                cache["last_success"] = saved.get("last_success")
                logging.info("Saved price cache loaded.")
    except Exception:
        logging.exception("Could not load saved cache.")


def save_cache(data):
    temporary_file = CACHE_FILE + ".tmp"

    try:
        saved = {
            "data": data,
            "last_success": datetime.now(timezone.utc).isoformat()
        }

        with open(temporary_file, "w", encoding="utf-8") as file:
            json.dump(saved, file, ensure_ascii=False)

        os.replace(temporary_file, CACHE_FILE)

    except Exception:
        logging.exception("Could not save price cache.")


def fetch_prices():
    key = os.environ.get("TALASANJ_API_KEY")

    if not key:
        raise RuntimeError("TALASANJ_API_KEY is not configured.")

    response = requests.get(
        API_URL,
        headers={"Authorization": f"Bearer {key}"},
        timeout=REQUEST_TIMEOUT
    )

    response.raise_for_status()
    data = response.json()

    if not isinstance(data, dict) or not isinstance(data.get("prices"), dict):
        raise ValueError("Invalid price API response.")

    return data


def refresh_prices():
    if not refresh_lock.acquire(blocking=False):
        return False

    try:
        data = fetch_prices()

        with cache_lock:
            cache["data"] = data
            cache["last_success"] = datetime.now(timezone.utc).isoformat()
            cache["last_error"] = None

        save_cache(data)
        logging.info("Prices updated successfully.")
        return True

    except Exception as error:
        with cache_lock:
            cache["last_error"] = str(error)

        logging.exception("Price update failed.")
        return False

    finally:
        refresh_lock.release()


def background_updater():
    while True:
        refresh_prices()
        time.sleep(REFRESH_INTERVAL)


def start_background_updater():
    thread = threading.Thread(
        target=background_updater,
        daemon=True,
        name="price-updater"
    )
    thread.start()


load_cache()
start_background_updater()


@app.route("/")
def home():
    return send_file("index.html")


@app.route("/api/prices")
def prices():
    with cache_lock:
        data = cache["data"]
        last_success = cache["last_success"]
        last_error = cache["last_error"]

    if data is None:
        return jsonify({
            "error": "اطلاعات هنوز دریافت نشده است.",
            "last_error": last_error
        }), 503

    result = dict(data)
    result["cache"] = {
        "last_success": last_success,
        "source": "server_cache",
        "refresh_interval": REFRESH_INTERVAL,
        "stale": bool(last_error)
    }

    response = jsonify(result)
    response.headers["Cache-Control"] = "no-store"
    return response


@app.route("/health")
def health():
    with cache_lock:
        ready = cache["data"] is not None

    return jsonify({
        "status": "ok",
        "cache_ready": ready
    })


@app.route("/eita/webhook", methods=["POST"])
def eita_webhook():
    from flask import request

    data = request.get_json(silent=True) or {}
    message = data.get("message", {})

    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "").strip()

    if chat_id and text in ["/start", "قیمت", "/price"]:
        with cache_lock:
            market_data = cache["data"]

        if not market_data:
            answer = "⏳ اطلاعات قیمت هنوز آماده نیست."
        else:
            market = market_data.get("prices", {})

            names = {
                "usd": "دلار",
                "usdt": "تتر",
                "gram18": "طلای ۱۸ عیار",
                "gram24": "طلای ۲۴ عیار",
                "coin_full": "سکه امامی",
                "coin_half": "نیم سکه",
                "coin_quarter": "ربع سکه"
            }

            answer = "📊 نبض بازار\n\n"

            for code, name in names.items():
                item = market.get(code, {})
                value = item.get("price")

                if isinstance(value, (int, float)):
                    answer += f"🔹 {name}: {value:,.0f} تومان\n"

            answer += "\n🌐 https://nabz-bazar.fadehost.app"

        if EITA_TOKEN:
            try:
                requests.post(
                    f"{EITA_API}/sendMessage",
                    json={
                        "token": EITA_TOKEN,
                        "chat_id": chat_id,
                        "text": answer
                    },
                    timeout=10
                )
            except Exception:
                logging.exception("Eitaa message failed.")

    return jsonify({"ok": True})


if __name__ == "__main__":
    from werkzeug.serving import run_simple

    run_simple(
        "0.0.0.0",
        int(os.environ.get("PORT", 8080)),
        app,
        threaded=True
    )

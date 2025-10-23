# webhook_to_csv.py
from flask import Flask, request, jsonify
import hashlib
import os
import csv
from pathlib import Path
from datetime import datetime

app = Flask(__name__)

# Environment variable untuk merchant key
MERCHANT_KEY = os.getenv("LYNK_SECRET_KEY")
if not MERCHANT_KEY:
    print("WARNING: LYNK_SECRET_KEY environment variable not set. Set it before production use.")

CSV_PATH = Path("contacts.csv")

def validate_lynk_signature(ref_id, amount, message_id, received_signature, secret_key):
    # Semua jadi string, sesuai dokumentasi: amount + refId + message_id + secret_key
    signature_string = str(amount) + str(ref_id) + str(message_id) + str(secret_key)
    calculated_signature = hashlib.sha256(signature_string.encode("utf-8")).hexdigest()
    return calculated_signature == str(received_signature)

def append_to_csv(name, phone):
    # Pastikan file ada dan masukkan header bila belum ada
    file_exists = CSV_PATH.exists()
    with CSV_PATH.open("a", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        if not file_exists:
            writer.writerow(["name", "phone", "saved_at"])  # header
        writer.writerow([name, phone, datetime.utcnow().isoformat()])

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        headers = request.headers
        payload = request.get_json(force=True, silent=True)
        if not payload:
            return jsonify({"status":"error","message":"Invalid or empty JSON payload"}), 400

        # Ambil signature dari header
        received_signature = headers.get("X-Lynk-Signature")
        if not received_signature:
            return jsonify({"status":"error","message":"Missing X-Lynk-Signature header"}), 401

        # Ambil data sesuai struktur contoh Lynk.id
        data = payload.get("data", {})
        msg_data = data.get("message_data", {}) or {}
        totals = msg_data.get("totals", {}) or {}

        ref_id = msg_data.get("refId") or msg_data.get("refId", "")
        message_id = data.get("message_id") or ""
        amount = totals.get("grandTotal") if totals.get("grandTotal") is not None else ""

        # validate signature - pastikan merchant key terisi
        if not MERCHANT_KEY:
            return jsonify({"status":"error","message":"Server merchant key not configured"}), 500

        if not validate_lynk_signature(ref_id, amount, message_id, received_signature, MERCHANT_KEY):
            return jsonify({"status":"error","message":"Invalid signature"}), 401

        # Ambil detail customer
        customer = msg_data.get("customer", {}) or {}
        raw_name = customer.get("name")
        phone = customer.get("phone")

        if not raw_name and not phone:
            # mungkin payload tidak berisi customer — tetap ok tapi beri info
            return jsonify({"status":"ok","message":"No customer data found in payload"}), 200

        # Format nama: prefix "1-" di depan nama pembeli
        safe_name = f"1-{raw_name}" if raw_name else "1-"

        # Simpan ke CSV
        append_to_csv(safe_name, phone or "")

        print(f"[{datetime.utcnow().isoformat()}] Saved contact: {safe_name} | {phone}")

        return jsonify({"status":"ok","message":"Contact saved"}), 200

    except Exception as e:
        print("Error processing webhook:", e)
        return jsonify({"status":"error","message":str(e)}), 500

if __name__ == "__main__":
    # Jalankan di port 5000; di Replit/Render/GCP sesuaikan
    app.run(host="0.0.0.0", port=5000)

# app.py
import os
from flask import Flask, request, make_response
import requests
from requests.auth import HTTPBasicAuth

app = Flask(__name__)

# Read secrets from environment variables (set these in Render → Environment)
CLIENT_ID = os.environ.get("CLIENT_ID")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET")
REDIRECT_URI = os.environ.get("REDIRECT_URI")  # e.g., https://qbconnect.irtaero.com/callback

# Optional: set EXPECTED_STATE if you want to validate the OAuth "state" value
EXPECTED_STATE = os.environ.get("EXPECTED_STATE")

TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"


def require_config():
    missing = [k for k, v in {
        "CLIENT_ID": CLIENT_ID,
        "CLIENT_SECRET": CLIENT_SECRET,
        "REDIRECT_URI": REDIRECT_URI,
    }.items() if not v]
    if missing:
        return make_response(
            "Server is missing configuration: " + ", ".join(missing), 500
        )
    return None


@app.get("/")
def root():
    return "ok", 200


@app.get("/healthz")
def healthz():
    return "ok", 200


@app.get("/callback")
def callback():
    # Ensure env vars are present
    cfg_err = require_config()
    if cfg_err:
        return cfg_err

    code = request.args.get("code")
    state = request.args.get("state")
    realm_id = request.args.get("realmId")
    dryrun = request.args.get("dryrun") in ("1", "true", "yes") or code == "test"

    if not (code and state and realm_id):
        return make_response("Missing OAuth params (code, state, realmId).", 400)

    # Optional CSRF check
    if EXPECTED_STATE and state != EXPECTED_STATE:
        return make_response("State mismatch.", 400)

    if dryrun:
        html = (
            "<h2>QuickBooks authorization page reached (dry run)</h2>"
            f"<p>realmId={realm_id}</p>"
            "<p>No token exchange attempted.</p>"
        )
        return make_response(html, 200)

    # Real token exchange
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }

    try:
        resp = requests.post(
            TOKEN_URL,
            data=data,  # form-encoded
            auth=HTTPBasicAuth(CLIENT_ID, CLIENT_SECRET),
            timeout=20,
        )
    except Exception as e:
        return make_response(f"Network error contacting Intuit: {e}", 502)

    if resp.status_code != 200:
        # Common reasons: redirect URI mismatch, expired/used code, wrong keys.
        return make_response(f"Error exchanging code: {resp.text}", 400)

    tokens = resp.json()
    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")

    # For now, print to logs. In production, store securely (DB/secret manager).
    print("Realm ID:", realm_id)
    print("Access Token:", access_token)
    print("Refresh Token:", refresh_token)

    html = (
        "<h2>QuickBooks authorization complete</h2>"
        "<p>You can close this window now.</p>"
    )
    return make_response(html, 200)


if __name__ == "__main__":
    # Local test server (Render uses gunicorn)
    app.run(host="0.0.0.0", port=8080)

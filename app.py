from flask import Flask, request, make_response
import requests
from requests.auth import HTTPBasicAuth

app = Flask(__name__)

# Replace these with your Intuit production app credentials
CLIENT_ID = "ABw4rgJtBnmtDP2PkM4YoQt4ozh062iU4EYGMDF0nvy9mvpA03"
CLIENT_SECRET = "4XfzT8dJWlMqScJyTVOjXhipzqLiI3lb5s7gDiR7"
REDIRECT_URI = "https://qbconnect.irtaero.com/callback"

TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"

@app.get("/callback")
def callback():
    code = request.args.get("code")
    state = request.args.get("state")
    realm_id = request.args.get("realmId")

    if not (code and state and realm_id):
        return make_response("Missing OAuth params.", 400)

    # Exchange authorization code for tokens
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }

    r = requests.post(
        TOKEN_URL,
        data=data,
        auth=HTTPBasicAuth(CLIENT_ID, CLIENT_SECRET),
        timeout=20
    )

    if r.status_code != 200:
        return f"Error exchanging code: {r.text}", 400

    tokens = r.json()
    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")

    # Save securely in production (database, secret manager, etc.)
    print("Access Token:", access_token)
    print("Refresh Token:", refresh_token)

    return """
    <h2>QuickBooks authorization complete</h2>
    <p>You can close this window now.</p>
    """

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
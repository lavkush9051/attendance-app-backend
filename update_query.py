import requests

def trigger_sap_sync(date=None):
    # Use your server IP or localhost if same machine
    url = "http://127.0.0.1:8000/sap-sync/leaves"

    params = {}
    if date:
        params["date"] = date  # YYYY-MM-DD

    try:
        response = requests.post(url, params=params)
        response.raise_for_status()  # Raise error for bad response codes

        print("SAP Sync Triggered Successfully!")
        print("Response:", response.json())

    except requests.exceptions.RequestException as e:
        print("Error while calling SAP Sync API:", e)

if __name__ == "__main__":
    # You can pass a date here, or leave empty for today
    trigger_sap_sync("2025-11-29")

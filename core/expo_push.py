import requests
import json

EXPO_URL = "https://exp.host/--/api/v2/push/send"

def send_push_message(token, title, message):
    payload = {
        "to": token,
        "title": title,
        "body": message,
        "sound": "default"
    }

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    response = requests.post(EXPO_URL, data=json.dumps(payload), headers=headers)

    print("Status code:", response.status_code)
    print("Response:", response.json())
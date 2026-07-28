import requests

EXPO_URL = "https://exp.host/--/api/v2/push/send"


def send_push_message(token, title, message):
    payload = {
        "to": token,
        "title": title,
        "body": message,
        "sound": "default",
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    try:
        response = requests.post(EXPO_URL, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        # логируем через logging, а не print — попадёт в реальные логи/Sentry
        import logging
        logging.getLogger(__name__).error("Expo push failed for token %s: %s", token, e)
        return None
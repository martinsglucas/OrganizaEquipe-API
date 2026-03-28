import firebase_admin
from firebase_admin import credentials, messaging
import os
import json

INVALID_TOKEN_CODES = {
    "unregistered",
    "registration-token-not-registered",
    "invalid-argument",
}

def _initialize_firebase():
    if firebase_admin._apps:
        return True

    firebase_credentials_json = os.environ.get("FIREBASE_CREDENTIALS_JSON")

    try:
        if firebase_credentials_json:
            cred_dict = json.loads(firebase_credentials_json)
            cred = credentials.Certificate(cred_dict)
        else:
            print("FIREBASE_CREDENTIALS_JSON não configurada.")
            return False

        firebase_admin.initialize_app(cred)
        return True
    except Exception as e:
        print(f"Erro ao inicializar Firebase Admin: {e}")
        return False

def _extract_invalid_tokens(response, tokens):
    invalid_tokens = []

    for token, send_response in zip(tokens, response.responses):
        if send_response.success:
            continue

        error_code = getattr(send_response.exception, "code", "") or ""
        if error_code in INVALID_TOKEN_CODES:
            invalid_tokens.append(token)

    return invalid_tokens

def send_schedule_notification(fcm_tokens: list[str], schedule_name: str, schedule_date, schedule_hour):
    if not fcm_tokens:
        return []

    if not _initialize_firebase():
        return []

    formatted_date = schedule_date.strftime("%d/%m/%Y")
    formatted_hour = schedule_hour.strftime("%H:%M")
    
    title = "📅 Você foi escalado!"
    body = f"{schedule_name} • {formatted_date} às {formatted_hour}"

    message = messaging.MulticastMessage(
        tokens=fcm_tokens,
        data={
            "title": title,
            "body": body,
            "type": "new_schedule",
            "schedule_name": schedule_name,
            "schedule_date": str(schedule_date),
            "schedule_hour": str(schedule_hour),
        },
        webpush=messaging.WebpushConfig(
        notification=messaging.WebpushNotification(
            title=title,
            body=body,
            icon="https://organizaequipe.onrender.com/favicon.ico",
        ),
        fcm_options=messaging.WebpushFCMOptions(
            link="https://organizaequipe.onrender.com/escala",
        ),
    ),
    )

    try:
        response = messaging.send_each_for_multicast(message)
        print(f"Notificações enviadas: {response.success_count} sucesso(s), {response.failure_count} falha(s)")
        return _extract_invalid_tokens(response, fcm_tokens)
    except Exception as e:
        print(f"Erro ao enviar notificações FCM: {e}")
        return []
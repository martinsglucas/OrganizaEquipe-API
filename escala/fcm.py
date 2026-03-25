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

def send_schedule_notification(fcm_tokens: list[str], schedule_name: str, schedule_date: str):
    if not fcm_tokens:
        return []

    if not _initialize_firebase():
        return []

    message = messaging.MulticastMessage(
        tokens=fcm_tokens,
        data={
            "title": "📅 Nova escala criada!",
            "body": f"Você foi escalado para: {schedule_name} em {schedule_date}",
            "type": "new_schedule",
            "schedule_name": schedule_name,
            "schedule_date": str(schedule_date),
        }
    )

    try:
        response = messaging.send_each_for_multicast(message)
        print(f"Notificações enviadas: {response.success_count} sucesso(s), {response.failure_count} falha(s)")
    except Exception as e:
        print(f"Erro ao enviar notificações FCM: {e}")
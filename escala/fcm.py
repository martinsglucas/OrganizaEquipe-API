import firebase_admin
from firebase_admin import credentials, exceptions, messaging
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

        exception = send_response.exception
        error_code = (getattr(exception, "code", "") or "").lower()
        if isinstance(
            exception,
            (messaging.UnregisteredError, exceptions.InvalidArgumentError),
        ) or error_code in INVALID_TOKEN_CODES:
            invalid_tokens.append(token)

    return invalid_tokens


def _send_multicast_notification(
    fcm_tokens: list[str],
    title: str,
    body: str,
    data: dict[str, str],
    link: str,
):
    if not fcm_tokens:
        return {
            "invalid_tokens": [],
            "success_count": 0,
            "failure_count": 0,
        }

    if not _initialize_firebase():
        return {
            "invalid_tokens": [],
            "success_count": 0,
            "failure_count": len(fcm_tokens),
        }

    try:
        message = messaging.MulticastMessage(
            tokens=fcm_tokens,
            data=data,
            webpush=messaging.WebpushConfig(
                notification=messaging.WebpushNotification(
                    title=title,
                    body=body,
                    icon="https://organizaequipe.onrender.com/favicon.ico",
                ),
                fcm_options=messaging.WebpushFCMOptions(
                    link=link,
                ),
            ),
        )
        response = messaging.send_each_for_multicast(message)
        print(
            f"Notificações enviadas: {response.success_count} sucesso(s), "
            f"{response.failure_count} falha(s)"
        )
        return {
            "invalid_tokens": _extract_invalid_tokens(response, fcm_tokens),
            "success_count": response.success_count,
            "failure_count": response.failure_count,
        }
    except Exception as e:
        print(f"Erro ao enviar notificações FCM: {e}")
        return {
            "invalid_tokens": [],
            "success_count": 0,
            "failure_count": len(fcm_tokens),
        }


def send_schedule_notification(fcm_tokens: list[str], schedule_name: str, schedule_date, schedule_hour):
    if not fcm_tokens:
        return []

    formatted_date = schedule_date.strftime("%d/%m/%Y")
    formatted_hour = schedule_hour.strftime("%H:%M")

    title = "📅 Você foi escalado!"
    body = f"{schedule_name} • {formatted_date} às {formatted_hour}"

    result = _send_multicast_notification(
        fcm_tokens=fcm_tokens,
        title=title,
        body=body,
        data={
            "title": title,
            "body": body,
            "type": "new_schedule",
            "schedule_name": schedule_name,
            "schedule_date": str(schedule_date),
            "schedule_hour": str(schedule_hour),
        },
        link="https://organizaequipe.onrender.com/escala",
    )

    return result["invalid_tokens"]


def send_confirmation_reminder_notification(
    fcm_tokens: list[str],
    schedule_id: int,
    schedule_name: str,
    schedule_date,
    schedule_hour,
    window_hours: int,
):
    formatted_date = schedule_date.strftime("%d/%m/%Y")
    formatted_hour = schedule_hour.strftime("%H:%M")
    title = "⏰ Confirme sua participação"
    body = f"{schedule_name} • {formatted_date} às {formatted_hour}"

    return _send_multicast_notification(
        fcm_tokens=fcm_tokens,
        title=title,
        body=body,
        data={
            "title": title,
            "body": body,
            "type": "schedule_confirmation_reminder",
            "schedule_id": str(schedule_id),
            "schedule_name": schedule_name,
            "schedule_date": str(schedule_date),
            "schedule_hour": str(schedule_hour),
            "reminder_window_hours": str(window_hours),
        },
        link="https://organizaequipe.onrender.com/escala",
    )


def send_unavailability_reminder_notification(fcm_tokens: list[str], month):
    title = "📆 Registre suas indisponibilidades"
    body = "Informe os dias em que você não estará disponível neste mês."

    return _send_multicast_notification(
        fcm_tokens=fcm_tokens,
        title=title,
        body=body,
        data={
            "title": title,
            "body": body,
            "type": "monthly_unavailability_reminder",
            "month": str(month),
        },
        link="https://organizaequipe.onrender.com/indisponibilidade",
    )

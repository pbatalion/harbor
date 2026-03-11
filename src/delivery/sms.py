from __future__ import annotations

from typing import Sequence

import requests

from src.settings import Settings


def send_sms_alert(settings: Settings, urgent_items: Sequence[str]) -> bool:
    if not urgent_items:
        return False
    if not settings.delivery_sms_enabled:
        return False

    if not (
        settings.twilio_account_sid
        and settings.twilio_auth_token
        and settings.twilio_from
        and settings.twilio_to
    ):
        return False

    body = "Urgent AI Assistant items:\n" + "\n".join(f"- {item}" for item in urgent_items[:8])

    response = requests.post(
        f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}/Messages.json",
        data={
            "From": settings.twilio_from,
            "To": settings.twilio_to,
            "Body": body,
        },
        auth=(settings.twilio_account_sid, settings.twilio_auth_token),
        timeout=20,
    )
    return response.status_code in {200, 201}

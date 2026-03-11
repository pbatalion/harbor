from __future__ import annotations

from collections.abc import Iterable


def filter_noise_emails(
    emails: Iterable[dict], noise_senders: list[str], noise_subject_keywords: list[str]
) -> list[dict]:
    filtered: list[dict] = []
    sender_rules = [rule.lower() for rule in noise_senders]
    subject_rules = [rule.lower() for rule in noise_subject_keywords]

    for email in emails:
        sender = str(email.get("sender", "")).lower()
        subject = str(email.get("subject", "")).lower()

        sender_noise = any(rule in sender for rule in sender_rules)
        subject_noise = any(rule in subject for rule in subject_rules)
        if sender_noise or subject_noise:
            continue
        filtered.append(email)

    return filtered

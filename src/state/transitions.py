from __future__ import annotations


def next_email_thread_state(
    *, has_new_external_reply: bool, user_replied: bool, thread_closed: bool
) -> str:
    if thread_closed:
        return "resolved"
    if has_new_external_reply and not user_replied:
        return "updated"
    if user_replied:
        return "waiting_on_them"
    return "pending"

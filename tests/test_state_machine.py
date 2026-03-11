from src.state.transitions import next_email_thread_state


def test_waiting_on_them_after_user_reply() -> None:
    state = next_email_thread_state(has_new_external_reply=False, user_replied=True, thread_closed=False)
    assert state == "waiting_on_them"


def test_updated_when_external_reply_and_no_user_reply() -> None:
    state = next_email_thread_state(has_new_external_reply=True, user_replied=False, thread_closed=False)
    assert state == "updated"


def test_resolved_when_closed() -> None:
    state = next_email_thread_state(has_new_external_reply=True, user_replied=True, thread_closed=True)
    assert state == "resolved"

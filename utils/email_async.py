import threading
from .mailgun_service import send_mailgun_email


def send_email_async(subject, text, html, to_list):
    def _send():
        try:
            response = send_mailgun_email(subject, text, html, to_list)
            print(response)
        except Exception as e:
            print("Mailgun error:", e)

    threading.Thread(target=_send, daemon=True).start()


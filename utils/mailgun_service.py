import requests
from django.conf import settings


API_KEY = settings.MAILGUN_API_KEY
MAILGUN_DOMAIN= settings.MAILGUN_DOMAIN


def send_mailgun_email(subject, text, html, to_list):
    return requests.post(
        f"https://api.mailgun.net/v3/{settings.MAILGUN_DOMAIN}/messages",
        auth=("api", API_KEY),
        data={
            "from": f"{settings.SITE_NAME} <contact@{MAILGUN_DOMAIN}>",
            "to": to_list,
            "subject": subject,
            "text": text,
            "html": html,
        },
        timeout=5
    )

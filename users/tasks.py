# users/tasks.py
from django.conf import settings
from celery import shared_task
import requests
from django.template.loader import render_to_string

@shared_task(bind=True, max_retries=3)
def send_welcome_email(self, user_email, username):
    try:
        context = {
            "user": username,
            "login_url": f"{settings.SITE_URL}/login"
        }

        html_content = render_to_string("email/welcome-email.html", context)
        response = requests.post(
            f"https://api.mailgun.net/v3/{settings.MAILGUN_DOMAIN}/messages",
            auth=("api", settings.SENDING_API_KEY),
            data={
                "from": f"{settings.SITE_NAME} <mailgun@{settings.MAILGUN_DOMAIN}>",
                "to": [user_email],
                "subject": "Bienvenido 🎉",
                "html": html_content,
            },
        )

        response.raise_for_status()

    except Exception as exc:
        raise self.retry(exc=exc, countdown=10)

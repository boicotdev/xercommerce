# users/tasks.py

from celery import shared_task
import requests
from django.template.loader import render_to_string
from decouple import config

@shared_task(bind=True, max_retries=3)
def send_welcome_email(self, user_email, username):
    try:
        context = {
            "user": username,
            "login_url": "https://avoberry.vervel.app/login"
        }

        html_content = render_to_string("email/welcome-email.html", context)
        response = requests.post(
            f"https://api.mailgun.net/v3/{config('MAILGUN_DOMAIN')}/messages",
            auth=("api", config("SENDING_API_KEY")),
            data={
                "from": f"Avoberry <mailgun@{config('MAILGUN_DOMAIN')}>",
                "to": [user_email],
                "subject": "Bienvenido 🎉",
                "html": html_content,
            },
        )

        response.raise_for_status()

    except Exception as exc:
        raise self.retry(exc=exc, countdown=10)



# from celery import shared_task
# import requests
# from decouple import config
#
# @shared_task(bind=True, max_retries=3)
# def send_welcome_email(self, user_email, username):
#     try:
#         response = requests.post(
#             f"https://api.mailgun.net/v3/{config('MAILGUN_DOMAIN')}/messages",
#             auth=("api", config("SENDING_API_KEY")),
#             data={
#                 "from": f"Tu App <mailgun@{config('MAILGUN_DOMAIN')}>",
#                 "to": [user_email],
#                 "subject": "Bienvenido 🎉",
#                 "text": f"Hola {username}, bienvenido a la plataforma.",
#             },
#         )
#
#         response.raise_for_status()
#
#     except Exception as exc:
#         raise self.retry(exc=exc, countdown=10)

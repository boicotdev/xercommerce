import datetime
from users.utils.email_async import run_async
from utils.utils import send_email


@run_async
def send_welcome_email_async(user):

    context = {
        "user": user.first_name,
        "subscriber_name": user.email,
        "site_url": "https://avoberry.vercel.app/",
        "year": datetime.datetime.now().year,
    }

    send_email(
        "Bienvenido a Avoberry",
        user.email,
        [],
        context,
        "email/welcome-email.html",
    )

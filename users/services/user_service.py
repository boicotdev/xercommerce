from django.db import transaction
from users.utils.profile import create_user_profile_settings
from users.tasks.email_tasks import send_welcome_email_async


def create_user(serializer):

    with transaction.atomic():

        user = serializer.save()

        create_user_profile_settings(user.dni)

        transaction.on_commit(
            lambda: send_welcome_email_async(user)
        )

    return user

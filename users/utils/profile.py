from users.models import UserProfileSettings, User


def create_user_profile_settings(dni: str) -> bool:
    """
    Creates or retrieves a user profile settings instance based on the user's DNI.

    Args:
        dni (str): The user's national identification number.

    Returns:
        bool: True if a new UserProfileSettings was created, False if it already existed or an error occurred.
    """
    try:
        user = User.objects.filter(dni=dni).first()
        if not user:
            return False  # User not found

        _, created = UserProfileSettings.objects.get_or_create(user=user)
        return created  # True if created, False if it already existed
    except Exception:
        # Optionally log the error here
        return False


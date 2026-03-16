import uuid

from django.contrib.auth.models import BaseUserManager, AbstractUser
from django.contrib.auth.models import Group, Permission
from django.db import models
from django.utils import timezone


class CustomUserManager(BaseUserManager):
    def create_user(self, username, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Please provide an email address")
        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(
            username=username, email=email, password=password, **extra_fields
        )


class User(AbstractUser):
    """
    Represents a single user on web application
    - required_fields = (dni, email)
    - Set a referral_code to handle
    """

    dni = models.CharField(max_length=30, primary_key=True)
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=50, blank=True)
    avatar = models.ImageField(
        default="users/avatar.jpg", upload_to="users/", blank=True, null=True
    )
    phone = models.CharField(max_length=20, blank=True)
    role = models.CharField(max_length=20)
    referral_code = models.CharField(max_length=25, unique=True, blank=True)
    referred_by = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL
    )

    # Avowing conflicts on groups and user_permissions
    groups = models.ManyToManyField(Group, related_name="custom_user_set")
    user_permissions = models.ManyToManyField(
        Permission, related_name="custom_user_permissions_set"
    )
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username", "dni"]

    objects = CustomUserManager()

    def __str__(self) -> str:
        return f"{self.username}-{self.dni}"

    def save(self, *args, **kwargs):
        if not self.referral_code:
            prefix = "AVB"
            sufix = self.dni[-4:]
            self.referral_code = (
                f'{prefix}-{sufix}-{str(uuid.uuid4()).replace("-", "")[:15].upper()}'
            )
        super().save(*args, **kwargs)


# User profile settingss
class UserProfileSettings(models.Model):
    user = models.OneToOneField(
        "users.User", on_delete=models.CASCADE, related_name="profile_settings"
    )
    notifications = models.BooleanField(default=True)
    order_updates_notifications = models.BooleanField(default=True)
    monthly_newsletter = models.BooleanField(default=True)
    product_recommendation = models.BooleanField(default=False)

    def __str__(self):
        return f"Settings for {self.user.username}"

    class Meta:
        verbose_name = "User Profile Setting"
        verbose_name_plural = "User Profile Settings"


class ReferralDiscount(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    has_discount = models.BooleanField(default=False)
    expires_at = models.DateTimeField(blank=True, null=True)

    def is_valid(self):
        return (
            self.has_discount and self.expires_at and self.expires_at > timezone.now()
        )

    def __str__(self):
        return (
            f"{self.user.username} - Active = ({self.has_discount}) - {self.expires_at}"
        )


class NewsletterSubscription(models.Model):
    email = models.EmailField(unique=True)

    def __str__(self):
        return self.email

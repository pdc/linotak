"""A custom user model."""

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, UserManager, UnicodeUsernameValidator
from django.db import models
from django.utils import timezone


class Login(PermissionsMixin, AbstractBaseUser):
    """How a user authenticates themself to the system.

    Custom class to excise the needless first_name/last_name fields.
    """
    username_validator = UnicodeUsernameValidator()

    username = models.CharField(
        'username',
        max_length=150,
        unique=True,
        blank=False,
        help_text='Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.',
        validators=[username_validator],
        error_messages={
            'unique': "A user with that username already exists.",
        },
    )
    email = models.EmailField('email address', blank=False, null=False)
    is_staff = models.BooleanField(
        'staff status',
        default=False,
        help_text='Designates whether the user can log into this admin site.',
    )
    is_active = models.BooleanField(
        'active',
        default=True,
        help_text=(
            'Designates whether this user should be treated as active. '
            'Unselect this instead of deleting accounts.'
        ),
    )
    date_joined = models.DateTimeField('date joined', default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = 'username'
    EMAIL_FIELD = 'email'
    REQUIRED_FIELDS = [EMAIL_FIELD]

    class Meta:
        verbose_name = 'user'
        verbose_name_plural = 'users'

    def clean(self):
        super().clean()
        self.email = self.__class__.objects.normalize_email(self.email)

    def get_full_name(self):
        return self.username

    def get_short_name(self):
        return self.username

    def email_user(self, subject, message, from_email=None, **kwargs):
        """Send an email to this user."""
        send_mail(subject, message, from_email, [self.email], **kwargs)

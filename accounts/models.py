from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils.translation import gettext_lazy as _
from .validators import validate_egyptian_phone


class UserManager(BaseUserManager):
    """Custom user model manager where email is the unique identifier for auth."""
    
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError(_('The Email field must be set'))
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))

        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Custom User model matching the requirements."""
    username = None
    email = models.EmailField(_('Email Address'), unique=True)
    first_name = models.CharField(_('First Name'), max_length=150)
    last_name = models.CharField(_('Last Name'), max_length=150)
    mobile_phone = models.CharField(
        _('Mobile Phone'),
        max_length=20,
        validators=[validate_egyptian_phone],
        help_text=_('Egyptian phone number (e.g., 01012345678 or +201012345678)')
    )
    profile_picture = models.ImageField(
        _('Profile Picture'),
        upload_to='profiles/%Y/%m/',
        blank=True,
        null=True
    )
    # Extra optional profile fields
    birthdate = models.DateField(_('Birthdate'), blank=True, null=True)
    facebook_profile = models.URLField(_('Facebook Profile URL'), blank=True, null=True)
    country = models.CharField(_('Country'), max_length=100, blank=True, default='Egypt')

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name', 'mobile_phone']

    objects = UserManager()

    class Meta:
        verbose_name = _('User')
        verbose_name_plural = _('Users')
        ordering = ['-date_joined']

    def __str__(self):
        return f"{self.get_full_name()} ({self.email})"

    def get_full_name(self):
        full_name = f"{self.first_name} {self.last_name}".strip()
        return full_name if full_name else self.email

    @property
    def profile_image_url(self):
        if self.profile_picture and hasattr(self.profile_picture, 'url'):
            return self.profile_picture.url
        return None

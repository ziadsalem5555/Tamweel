from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
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
        blank=True,
        default='',
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
    def is_facebook_linked(self):
        return hasattr(self, 'facebook_account') and self.facebook_account is not None

    @property
    def profile_image_url(self):
        if self.profile_picture and hasattr(self.profile_picture, 'url'):
            return self.profile_picture.url
        return None


class FacebookSocialAccount(models.Model):
    """
    Links a verified Meta/Facebook identity to an existing or new Tamweel User account.
    Enforces uniqueness on facebook_id.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='facebook_account')
    facebook_id = models.CharField(_('Facebook User ID'), max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Facebook Social Account')
        verbose_name_plural = _('Facebook Social Accounts')

    def __str__(self):
        return f"{self.user.email} (FB ID: {self.facebook_id})"



class EmailOTP(models.Model):
    """
    Stores 6-digit numeric OTP for email verification during registration.
    Features:
    - Cryptographically secure 6-digit random generation
    - 10 minutes expiration
    - 60 seconds resend cooldown
    - Max 5 failed attempts protection
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='email_otps')
    email = models.EmailField(_('Email Address'))
    otp_code = models.CharField(_('OTP Code'), max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(_('Expires At'))
    attempts = models.PositiveIntegerField(default=0, help_text=_('Number of failed verification attempts'))
    last_sent_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = _('Email OTP')
        verbose_name_plural = _('Email OTPs')
        ordering = ['-created_at']

    def __str__(self):
        return f"OTP for {self.email} ({self.otp_code})"

    @classmethod
    def generate_otp_for_user(cls, user, validity_minutes=10):
        """Generates a cryptographically secure 6-digit OTP and saves or updates the active OTP record."""
        import secrets
        from django.utils import timezone
        from datetime import timedelta

        # Cryptographically secure 6-digit numeric OTP (100000 - 999999)
        code = f"{secrets.randbelow(900000) + 100000}"
        expires = timezone.now() + timedelta(minutes=validity_minutes)

        # Invalidate/delete any old OTPs for this user
        cls.objects.filter(user=user).delete()

        otp_record = cls.objects.create(
            user=user,
            email=user.email,
            otp_code=code,
            expires_at=expires,
            attempts=0
        )
        return otp_record

    def is_expired(self):
        from django.utils import timezone
        return timezone.now() > self.expires_at

    def can_resend(self, cooldown_seconds=60):
        """Checks if cooldown period has passed since last email was sent."""
        from django.utils import timezone
        from datetime import timedelta
        return timezone.now() >= self.last_sent_at + timedelta(seconds=cooldown_seconds)

    def remaining_resend_seconds(self, cooldown_seconds=60):
        from django.utils import timezone
        from datetime import timedelta
        diff = (self.last_sent_at + timedelta(seconds=cooldown_seconds)) - timezone.now()
        return max(0, int(diff.total_seconds()))

    def increment_attempts(self):
        self.attempts += 1
        self.save(update_fields=['attempts'])

    def is_locked(self, max_attempts=5):
        return self.attempts >= max_attempts



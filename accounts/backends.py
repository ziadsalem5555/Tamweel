from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

UserModel = get_user_model()

class EmailBackend(ModelBackend):
    """
    Authenticate against settings.AUTH_USER_MODEL using email.
    """
    def authenticate(self, request, username=None, password=None, email=None, **kwargs):
        # Fallback to username parameter if email not explicitly given (Django auth forms pass username)
        lookup_email = email or username or kwargs.get('email')
        if not lookup_email or not password:
            return None
        
        try:
            user = UserModel.objects.get(email__iexact=lookup_email)
        except UserModel.DoesNotExist:
            UserModel().set_password(password)
            return None
        except UserModel.MultipleObjectsReturned:
            user = UserModel.objects.filter(email__iexact=lookup_email).order_by('id').first()

        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

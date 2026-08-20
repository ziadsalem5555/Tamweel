from django.core.signing import TimestampSigner, SignatureExpired, BadSignature
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth import get_user_model

UserModel = get_user_model()
signer = TimestampSigner(salt='account-activation-salt')

# 24 hours in seconds
ACTIVATION_TOKEN_MAX_AGE = 24 * 60 * 60  # 86400 seconds

def generate_activation_token(user):
    """
    Generate a base64 encoded user id and a timestamp-signed activation token.
    """
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    # Sign user.pk and user's password hash snippet to invalidate token if password changes or user activates
    payload = f"{user.pk}:{user.is_active}:{user.password[:10]}"
    token = signer.sign(payload)
    return uidb64, token

def verify_activation_token(uidb64, token, max_age=ACTIVATION_TOKEN_MAX_AGE):
    """
    Verify the activation token and return the user if valid and not expired (within 24h).
    Returns (user, status_code) where status_code can be 'valid', 'expired', or 'invalid'.
    """
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = UserModel.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, UserModel.DoesNotExist):
        return None, 'invalid'

    try:
        unsigned_payload = signer.unsign(token, max_age=max_age)
        parts = unsigned_payload.split(':')
        if len(parts) >= 3 and parts[0] == str(user.pk):
            return user, 'valid'
        return None, 'invalid'
    except SignatureExpired:
        return user, 'expired'
    except BadSignature:
        return None, 'invalid'

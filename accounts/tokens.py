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
    Incorporates user.pk, is_active status, and password snippet so the token
    is invalidated upon activation or password change.
    """
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    payload = f"{user.pk}:{user.is_active}:{user.password[:15]}"
    token = signer.sign(payload)
    return uidb64, token


def verify_activation_token(uidb64, token, max_age=ACTIVATION_TOKEN_MAX_AGE):
    """
    Verify the activation token and return (user, status_code).
    status_code can be:
      - 'valid': valid token, user inactive, within 24h
      - 'expired': token signature timestamp is older than max_age (24h)
      - 'already_activated': user account is already active
      - 'invalid': forged, malformed, or mismatch
    """
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = UserModel.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, UserModel.DoesNotExist):
        return None, 'invalid'

    # If the user is already active, reject re-activation
    if user.is_active:
        return user, 'already_activated'

    try:
        unsigned_payload = signer.unsign(token, max_age=max_age)
        parts = unsigned_payload.split(':')
        if len(parts) >= 3 and parts[0] == str(user.pk) and parts[1] == 'False':
            if parts[2] == user.password[:15]:
                return user, 'valid'
        return None, 'invalid'
    except SignatureExpired:
        return user, 'expired'
    except BadSignature:
        return None, 'invalid'


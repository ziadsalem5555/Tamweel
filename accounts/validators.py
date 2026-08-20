import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

def validate_egyptian_phone(value):
    """
    Validates that a given phone number is a valid Egyptian mobile number.
    Valid formats:
    - 01012345678, 01112345678, 01212345678, 01512345678 (11 digits starting with 010, 011, 012, 015)
    - +201012345678, +2011..., +2012..., +2015...
    - 00201012345678, 002011..., etc.
    """
    if not value:
        return

    # Strip spaces, hyphens, and parentheses
    cleaned = re.sub(r'[\s\-\(\)]', '', str(value))
    
    # Regex pattern matching standard Egyptian mobile numbers
    pattern = r'^(?:\+20|0020)?0?1[0125][0-9]{8}$'
    
    if not re.match(pattern, cleaned):
        raise ValidationError(
            _('%(value)s is not a valid Egyptian mobile phone number. It must start with 010, 011, 012, or 015 and contain 11 digits (e.g. 01012345678 or +201012345678).'),
            params={'value': value},
        )

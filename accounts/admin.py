from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import User, FacebookSocialAccount, EmailOTP


@admin.register(FacebookSocialAccount)
class FacebookSocialAccountAdmin(admin.ModelAdmin):
    list_display = ('user', 'facebook_id', 'created_at', 'updated_at')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'facebook_id')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(EmailOTP)
class EmailOTPAdmin(admin.ModelAdmin):
    list_display = ('user', 'email', 'otp_code', 'attempts', 'created_at', 'expires_at')
    search_fields = ('user__email', 'email', 'otp_code')
    readonly_fields = ('created_at',)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'first_name', 'last_name', 'mobile_phone', 'is_facebook_linked_status', 'is_active', 'is_staff', 'date_joined')
    list_filter = ('is_active', 'is_staff', 'is_superuser', 'date_joined', 'country')
    search_fields = ('email', 'first_name', 'last_name', 'mobile_phone')
    ordering = ('-date_joined',)

    @admin.display(boolean=True, description=_('Facebook Linked'))
    def is_facebook_linked_status(self, obj):
        return obj.is_facebook_linked

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'mobile_phone', 'profile_picture', 'birthdate', 'facebook_profile', 'country')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'mobile_phone', 'password', 'is_active', 'is_staff'),
        }),
    )


from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views
from . import views
from .forms import TamweelPasswordResetForm, TamweelSetPasswordForm

app_name = 'accounts'

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('verify-otp/', views.verify_otp_view, name='verify_otp'),
    path('resend-otp/', views.resend_otp_view, name='resend_otp'),
    path('activate/<str:uidb64>/<str:token>/', views.activate_account_view, name='activate'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('dashboard/projects/<int:pk>/toggle-featured/', views.admin_toggle_featured_view, name='admin_toggle_featured'),
    path('dashboard/projects/<int:pk>/delete/', views.admin_delete_project_view, name='admin_delete_project'),
    path('dashboard/users/<int:pk>/toggle-status/', views.admin_toggle_user_status_view, name='admin_toggle_user_status'),
    path('dashboard/users/<int:pk>/delete/', views.admin_delete_user_view, name='admin_delete_user'),
    path('dashboard/users/<int:pk>/make-admin/', views.admin_make_admin_view, name='admin_make_admin'),
    path('dashboard/users/<int:pk>/remove-admin/', views.admin_remove_admin_view, name='admin_remove_admin'),
    path('dashboard/reports/<str:report_type>/<int:pk>/<str:action>/', views.admin_handle_report_view, name='admin_handle_report'),
    path('dashboard/categories/manage/', views.admin_manage_category_view, name='admin_manage_category'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/edit/', views.edit_profile_view, name='edit_profile'),
    path('profile/remove-photo/', views.remove_profile_photo_view, name='remove_profile_photo'),
    path('profile/delete/', views.delete_account_view, name='delete_account'),

    # Password Reset
    path(
        'password-reset/',
        auth_views.PasswordResetView.as_view(
            form_class=TamweelPasswordResetForm,
            template_name='accounts/password_reset.html',
            email_template_name='accounts/password_reset_email.txt',
            html_email_template_name='accounts/password_reset_email.html',
            subject_template_name='accounts/password_reset_subject.txt',
            success_url=reverse_lazy('accounts:password_reset_done')
        ),
        name='password_reset'
    ),
    path(
        'password-reset/done/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='accounts/password_reset_done.html'
        ),
        name='password_reset_done'
    ),
    path(
        'password-reset-confirm/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            form_class=TamweelSetPasswordForm,
            template_name='accounts/password_reset_confirm.html',
            success_url=reverse_lazy('accounts:password_reset_complete')
        ),
        name='password_reset_confirm'
    ),
    path(
        'password-reset-complete/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='accounts/password_reset_complete.html'
        ),
        name='password_reset_complete'
    ),

    # Meta / Facebook OAuth Login (Bonus Requirement)
    path('facebook/login/', views.facebook_login_view, name='facebook_login'),
    path('facebook/callback/', views.facebook_callback_view, name='facebook_callback'),
]



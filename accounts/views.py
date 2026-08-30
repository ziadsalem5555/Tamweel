import json
import logging
import secrets
import urllib.parse
import urllib.request
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.urls import reverse
from django.db import transaction

from .forms import UserRegistrationForm, UserLoginForm, UserProfileEditForm, AccountDeleteForm
from .models import EmailOTP, FacebookSocialAccount
from .tokens import generate_activation_token, verify_activation_token

logger = logging.getLogger(__name__)
User = get_user_model()


def send_otp_email(user, otp_code, validity_minutes=10, request=None):
    """
    Sends a verification email via configured Gmail SMTP backend containing:
    1) 6-digit OTP code (expires in 10 minutes)
    2) Direct one-click activation link (expires in 24 hours)
    Recipient is always user.email.
    """
    recipient = user.email.strip().lower()
    subject = "Verify your Tamweel account"

    # Generate 24-hour activation token & URL
    uidb64, token = generate_activation_token(user)
    activation_path = reverse('accounts:activate', kwargs={'uidb64': uidb64, 'token': token})
    if request is not None:
        activation_url = request.build_absolute_uri(activation_path)
    else:
        domain = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')
        activation_url = f"{domain.rstrip('/')}{activation_path}"

    text_content = (
        f"Welcome to Tamweel.\n\n"
        f"You can verify your account using either method:\n\n"
        f"Method 1: Your verification code:\n"
        f"{otp_code}\n"
        f"This code expires in {validity_minutes} minutes.\n\n"
        f"OR\n\n"
        f"Method 2: Click the activation link below to verify directly:\n"
        f"{activation_url}\n"
        f"This activation link expires in 24 hours.\n\n"
        f"Security Notice: Do not share your verification code or link with anyone.\n\n"
        f"---\nTamweel Team"
    )

    context = {
        'user': user,
        'otp_code': otp_code,
        'validity_minutes': validity_minutes,
        'activation_url': activation_url,
    }
    html_content = render_to_string('accounts/otp_email.html', context)

    print("\n" + "=" * 60)
    print("*** [TAMWEEL - OTP & ACTIVATION EMAIL DELIVERY] ***")
    print(f"   Recipient      : {recipient}")
    print(f"   Subject        : {subject}")
    print(f"   OTP Code       : {otp_code} ({validity_minutes} min)")
    print(f"   Activation URL : {activation_url} (24 hr)")
    print("=" * 60 + "\n")

    try:
        from_email = settings.DEFAULT_FROM_EMAIL
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_email,
            to=[recipient]
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=False)
        return True, None
    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.error("Failed to deliver OTP & activation email to %s: %s", recipient, str(e), exc_info=True)
        print(f"\n[EMAIL SEND ERROR] Could not send verification email to {recipient}: {e}\n")
        return False, str(e)



def register_view(request):
    """
    Handles new user registration:
    1. In a transaction block:
       - Creates user as inactive (is_active=False)
       - Generates 6-digit OTP
       - Sends verification email with OTP & Activation Link via Gmail SMTP
    2. If email fails:
       - Rolls back transaction so no broken unverified account is left behind
       - Logs error to terminal
       - Renders registration page with clear error
    3. If email succeeds:
       - Commits user and OTP record
       - Redirects to OTP verification page
    """
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            email_val = form.cleaned_data.get('email', '').strip().lower()
            try:
                with transaction.atomic():
                    user = form.save(commit=True)
                    user.is_active = False
                    user.save(update_fields=['is_active'])

                    # Generate 6-digit OTP and send verification email
                    otp_record = EmailOTP.generate_otp_for_user(user, validity_minutes=10)
                    email_sent, error_msg = send_otp_email(user, otp_record.otp_code, validity_minutes=10, request=request)

                    if not email_sent:
                        raise RuntimeError(error_msg or "Failed to deliver verification email via SMTP server.")

                # Transaction committed successfully on email delivery
                request.session['registration_email'] = user.email
                messages.success(
                    request,
                    f"Welcome to Tamweel! We sent a verification code and activation link to {user.email}."
                )
                return redirect(f"{reverse('accounts:verify_otp')}?email={user.email}")

            except Exception as exc:
                logger.error("Registration email error for %s: %s", email_val, str(exc), exc_info=True)
                print(f"\n[REGISTRATION ABORTED] User creation rolled back for {email_val}. Error: {exc}\n")

                # Safety cleanup in case of non-transactional artifacts
                User.objects.filter(email__iexact=email_val, is_active=False).delete()

                messages.error(
                    request,
                    f"Could not send verification email to {email_val}. Please check your email address or network connection and try again. (Details: {exc})"
                )
                return render(request, 'accounts/register.html', {'form': form})
    else:
        form = UserRegistrationForm()

    return render(request, 'accounts/register.html', {'form': form})



def verify_otp_view(request):
    """
    Validates 6-digit OTP code entered by user on the website.
    On success:
    - Verifies OTP
    - Activates account (user.is_active = True)
    - Deletes/invalidates OTP
    - Redirects user to login page
    """
    if request.user.is_authenticated:
        return redirect('home')

    email = request.POST.get('email') or request.GET.get('email') or request.session.get('registration_email', '')
    email = email.strip().lower()

    if not email:
        messages.error(request, "Session expired or invalid email. Please register again.")
        return redirect('accounts:register')

    # Find unverified user
    user = User.objects.filter(email__iexact=email).first()
    if not user:
        messages.error(request, "No account found with this email address. Please register.")
        return redirect('accounts:register')

    if user.is_active:
        messages.info(request, "Your account is already verified! Please log in.")
        return redirect('accounts:login')

    otp_record = EmailOTP.objects.filter(user=user).first()
    remaining_seconds = otp_record.remaining_resend_seconds() if otp_record else 0

    if request.method == 'POST':
        entered_code = request.POST.get('otp_code', '').strip()
        # Fallback: if separate digit inputs d1..d6 were submitted
        if not entered_code or len(entered_code) != 6:
            digits = [request.POST.get(f'd{i}', '').strip() for i in range(1, 7)]
            if all(digits):
                entered_code = "".join(digits)

        if not otp_record:
            return render(request, 'accounts/verify_otp.html', {
                'email': email,
                'error_message': 'No active verification code found. Please click "Resend Code" to receive a new code.',
                'remaining_seconds': 0,
            })

        # Check if brute-force locked (max 5 failed attempts)
        if otp_record.is_locked(max_attempts=5):
            return render(request, 'accounts/verify_otp.html', {
                'email': email,
                'error_message': 'Too many failed attempts (maximum 5). Please click "Resend Code" to get a new code.',
                'remaining_seconds': otp_record.remaining_resend_seconds(),
            })

        # Check expiration (10 minutes)
        if otp_record.is_expired():
            return render(request, 'accounts/verify_otp.html', {
                'email': email,
                'error_message': 'This verification code has expired (valid for 10 minutes). Please click "Resend Code" below.',
                'remaining_seconds': otp_record.remaining_resend_seconds(),
            })

        # Validate Code
        if entered_code == otp_record.otp_code:
            # Mark user active & verified
            user.is_active = True
            user.save(update_fields=['is_active'])

            # Invalidate/delete OTP record
            EmailOTP.objects.filter(user=user).delete()

            # Clear session email
            request.session.pop('registration_email', None)

            messages.success(
                request,
                f"🎉 Your email has been verified and your Tamweel account is now activated! Please log in to continue."
            )
            return redirect('accounts:login')
        else:
            otp_record.increment_attempts()
            remaining_attempts = max(0, 5 - otp_record.attempts)
            if remaining_attempts == 0:
                error_msg = "Maximum failed attempts reached. Please click 'Resend Code' to receive a new code."
            else:
                error_msg = f"Invalid verification code. {remaining_attempts} attempt{'s' if remaining_attempts != 1 else ''} remaining."

            return render(request, 'accounts/verify_otp.html', {
                'email': email,
                'error_message': error_msg,
                'remaining_seconds': otp_record.remaining_resend_seconds(),
            })

    return render(request, 'accounts/verify_otp.html', {
        'email': email,
        'remaining_seconds': remaining_seconds,
    })


def resend_otp_view(request):
    """
    Resends a fresh verification email with new 6-digit OTP and new activation link,
    subject to a 60-second rate-limiting cooldown.
    """
    if request.method != 'POST':
        return redirect('accounts:register')

    email = request.POST.get('email', '').strip().lower()
    user = User.objects.filter(email__iexact=email).first()

    if not user:
        messages.error(request, "Account not found.")
        return redirect('accounts:register')

    if user.is_active:
        messages.info(request, "Account is already verified. Please log in.")
        return redirect('accounts:login')

    otp_record = EmailOTP.objects.filter(user=user).first()

    # Rate limiting: 60s cooldown
    if otp_record and not otp_record.can_resend(cooldown_seconds=60):
        wait_secs = otp_record.remaining_resend_seconds(cooldown_seconds=60)
        messages.warning(request, f"Please wait {wait_secs} seconds before requesting another code.")
        return redirect(f"{reverse('accounts:verify_otp')}?email={user.email}")

    # Generate fresh OTP and send verification email with new OTP & activation link
    new_otp = EmailOTP.generate_otp_for_user(user, validity_minutes=10)
    email_sent, error_msg = send_otp_email(user, new_otp.otp_code, validity_minutes=10, request=request)

    if email_sent:
        messages.success(request, f"A fresh verification code and activation link have been sent to {user.email}.")
    else:
        messages.error(request, "Could not send verification email. Please check your connection and try again.")

    return redirect(f"{reverse('accounts:verify_otp')}?email={user.email}")


def activate_account_view(request, uidb64=None, token=None):
    """
    One-click account activation link endpoint (/accounts/activate/<uidb64>/<token>/).
    Directly activates the account if the link is valid and within the 24-hour expiration window.
    """
    if request.user.is_authenticated:
        return redirect('home')

    if not uidb64 or not token:
        return render(request, 'accounts/activation_invalid.html', {
            'error_title': 'Invalid Activation Link',
            'error_message': 'The activation link is missing required parameters.',
        })

    user, status_code = verify_activation_token(uidb64, token)

    if status_code == 'valid' and user:
        # Directly activate user account
        user.is_active = True
        user.save(update_fields=['is_active'])

        # Invalidate OTP records so they cannot be reused
        EmailOTP.objects.filter(user=user).delete()

        # Clear registration email from session
        request.session.pop('registration_email', None)

        messages.success(
            request,
            "🎉 Your Tamweel account has been successfully activated! You can now log in."
        )
        return redirect('accounts:login')

    elif status_code == 'already_activated':
        messages.info(
            request,
            "This account has already been activated. Please log in."
        )
        return redirect('accounts:login')

    elif status_code == 'expired':
        return render(request, 'accounts/activation_invalid.html', {
            'error_title': 'Activation Link Expired',
            'error_message': 'This activation link has expired (activation links are valid for 24 hours). Please click below to receive a new verification email.',
            'email': user.email if user else '',
        })

    else:  # 'invalid'
        return render(request, 'accounts/activation_invalid.html', {
            'error_title': 'Invalid Activation Link',
            'error_message': 'This activation link is no longer valid or has already been used.',
            'email': user.email if user else '',
        })


def login_view(request):
    """Handles user login with email and password, strictly blocking unverified users."""
    if request.user.is_authenticated:
        return redirect('home')

    next_url = request.GET.get('next', 'home')

    if request.method == 'POST':
        form = UserLoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data.get('email', '').strip().lower()
            password = form.cleaned_data.get('password')

            # Strict backend check: If credentials match but account is unverified/inactive, reject login
            user_obj = User.objects.filter(email__iexact=email).first()
            if user_obj and user_obj.check_password(password):
                if not user_obj.is_active:
                    messages.error(
                        request,
                        'Please verify your email before logging in. You can use the 6-digit code or activation link sent to your email.'
                    )
                    return redirect(f"{reverse('accounts:verify_otp')}?email={user_obj.email}")

            user = authenticate(request, email=email, password=password)
            if user is not None:
                if not user.is_active:
                    messages.error(
                        request,
                        'Please verify your email before logging in. You can use the 6-digit code or activation link sent to your email.'
                    )
                    return redirect(f"{reverse('accounts:verify_otp')}?email={user.email}")

                login(request, user)
                messages.success(request, f'Welcome back, {user.first_name}!')
                return redirect(next_url if next_url and next_url != 'None' else 'home')
            else:
                messages.error(request, 'Invalid email or password. Please try again.')
    else:
        form = UserLoginForm()

    return render(request, 'accounts/login.html', {'form': form})




def logout_view(request):
    """Logs out user and redirects to home."""
    if request.user.is_authenticated:
        logout(request)
        messages.info(request, 'You have been successfully logged out.')
    return redirect('home')


from functools import wraps
from decimal import Decimal
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Sum, Count, Avg, Q
from django.utils.text import slugify


def admin_required(view_func):
    """
    Decorator for views that checks that the user is logged in and has is_staff/is_superuser permission.
    - If unauthenticated -> redirects to login page.
    - If authenticated but is_staff=False -> raises PermissionDenied (403 Forbidden).
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"{reverse('accounts:login')}?next={request.path}")
        if not (request.user.is_staff or request.user.is_superuser):
            raise PermissionDenied("Access Denied: Administrator / Staff privileges required.")
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def superuser_required(view_func):
    """
    Decorator for views that checks that the user is logged in and is a superuser.
    - If unauthenticated -> redirects to login page.
    - If authenticated but is_superuser=False -> raises PermissionDenied (403 Forbidden).
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"{reverse('accounts:login')}?next={request.path}")
        if not request.user.is_superuser:
            raise PermissionDenied("Access Denied: Super Admin privileges required.")
        return view_func(request, *args, **kwargs)
    return _wrapped_view



@admin_required
def dashboard_view(request):
    """
    ADMIN-ONLY Dashboard for platform management:
    - Global Platform Statistics (Total Users, Projects, Donations, Raised, Active, Reports)
    - Project Management (View, Edit, Delete, Toggle Featured)
    - User Management (View, Search, Activation status, Role, Safe Deletion)
    - Moderation & Reports (Project & Comment Reports)
    - Category Management (Create, Edit, Delete)
    """
    from projects.models import Category, Project, Donation, ProjectReport, CommentReport

    # 1. Global Platform Statistics
    total_users = User.objects.count()
    total_projects = Project.objects.count()
    total_donations = Donation.objects.count()

    total_raised_res = Donation.objects.aggregate(total=Sum('amount'))['total']
    total_raised = total_raised_res if total_raised_res is not None else Decimal('0.00')

    active_campaigns = Project.objects.filter(status='running').count()
    pending_project_reports = ProjectReport.objects.filter(status='pending').count()
    pending_comment_reports = CommentReport.objects.filter(status='pending').count()
    pending_reports_total = pending_project_reports + pending_comment_reports

    # 2. Content Collections
    all_projects = Project.objects.select_related('category', 'creator').prefetch_related('images', 'donations', 'ratings').order_by('-created_at')
    
    # User search & pagination
    user_search_q = request.GET.get('user_q', '').strip()
    users_qs = User.objects.all().order_by('-date_joined')
    if user_search_q:
        users_qs = users_qs.filter(
            Q(first_name__icontains=user_search_q) |
            Q(last_name__icontains=user_search_q) |
            Q(email__icontains=user_search_q) |
            Q(mobile_phone__icontains=user_search_q)
        )
    users_paginator = Paginator(users_qs, 15)
    user_page = request.GET.get('user_page')
    users_page_obj = users_paginator.get_page(user_page)

    project_reports = ProjectReport.objects.select_related('reporter', 'project').order_by('-created_at')
    comment_reports = CommentReport.objects.select_related('reporter', 'comment', 'comment__project').order_by('-created_at')
    categories = Category.objects.annotate(project_count=Count('projects')).order_by('name')

    context = {
        'admin_user': request.user,
        'total_users': total_users,
        'total_projects': total_projects,
        'total_donations': total_donations,
        'total_raised': total_raised,
        'active_campaigns': active_campaigns,
        'pending_reports_total': pending_reports_total,
        'all_projects': all_projects,
        'all_users': users_page_obj,
        'user_search_q': user_search_q,
        'users_count_filtered': users_qs.count(),
        'project_reports': project_reports,
        'comment_reports': comment_reports,
        'categories': categories,
    }
    return render(request, 'accounts/dashboard.html', context)


@admin_required
def admin_delete_user_view(request, pk):
    """
    Admin-only endpoint to permanently delete a user account and associated data.
    Enforces authorization:
    - User is authenticated and has admin/staff permissions (enforced by @admin_required)
    - Target user exists
    - Protected: Prevents admin from deleting their own currently logged-in account
    - Protected: Only superusers can delete superuser accounts
    - Executes within an atomic database transaction with storage cleanup
    """
    if request.method != 'POST':
        return redirect(f"{reverse('accounts:dashboard')}?tab=users")

    target_user = get_object_or_404(User, pk=pk)

    # Protection 1: Prevent admin from deleting their own account
    if target_user == request.user:
        messages.error(request, "You cannot delete your own administrator account.")
        return redirect(f"{reverse('accounts:dashboard')}?tab=users")

    # Protection 2: Superusers cannot be deleted by non-superusers
    if target_user.is_superuser and not request.user.is_superuser:
        messages.error(request, "Only a Super Admin can delete another Super Admin account.")
        return redirect(f"{reverse('accounts:dashboard')}?tab=users")

    user_name = target_user.get_full_name()
    user_email = target_user.email

    try:
        with transaction.atomic():
            # Delete user's profile picture file from storage if exists
            if target_user.profile_picture:
                try:
                    storage = target_user.profile_picture.storage
                    name = target_user.profile_picture.name
                    if storage and name and storage.exists(name):
                        storage.delete(name)
                except Exception:
                    pass

            # Safe permanent deletion of user record (cascades associated user records)
            target_user.delete()

        messages.success(request, f'User account "{user_name}" ({user_email}) has been permanently deleted.')
    except Exception as e:
        messages.error(request, f'An error occurred while deleting user: {str(e)}')

    return redirect(f"{reverse('accounts:dashboard')}?tab=users")


@superuser_required
def admin_make_admin_view(request, pk):
    """
    Superuser-only action to promote a verified user to staff/administrator.
    Grants is_staff=True to access the Admin Dashboard.
    """
    if request.method != 'POST':
        return redirect(f"{reverse('accounts:dashboard')}?tab=users")

    target_user = get_object_or_404(User, pk=pk)

    if target_user == request.user:
        messages.info(request, "You are already a Super Administrator.")
        return redirect(f"{reverse('accounts:dashboard')}?tab=users")

    if target_user.is_staff or target_user.is_superuser:
        messages.info(request, f'User "{target_user.get_full_name()}" ({target_user.email}) is already an administrator.')
        return redirect(f"{reverse('accounts:dashboard')}?tab=users")

    target_user.is_staff = True
    target_user.save(update_fields=['is_staff'])
    messages.success(request, f'User "{target_user.get_full_name()}" promoted to administrator successfully.')
    return redirect(f"{reverse('accounts:dashboard')}?tab=users")


@superuser_required
def admin_remove_admin_view(request, pk):
    """
    Superuser-only action to revoke staff/administrator privileges from a user.
    Removes is_staff=False without modifying account data, projects, or donations.
    """
    if request.method != 'POST':
        return redirect(f"{reverse('accounts:dashboard')}?tab=users")

    target_user = get_object_or_404(User, pk=pk)

    if target_user == request.user:
        messages.error(request, "You cannot remove administrator privileges from your own active account.")
        return redirect(f"{reverse('accounts:dashboard')}?tab=users")

    if target_user.is_superuser:
        messages.error(request, "Super Administrator privileges cannot be revoked through this action.")
        return redirect(f"{reverse('accounts:dashboard')}?tab=users")

    if not target_user.is_staff:
        messages.info(request, f'User "{target_user.get_full_name()}" is already a standard user.')
        return redirect(f"{reverse('accounts:dashboard')}?tab=users")

    target_user.is_staff = False
    target_user.save(update_fields=['is_staff'])
    messages.success(request, f'Administrator access removed from "{target_user.get_full_name()}" ({target_user.email}) successfully.')
    return redirect(f"{reverse('accounts:dashboard')}?tab=users")



@admin_required
def admin_toggle_featured_view(request, pk):
    """Admin action to toggle project featured status."""
    if request.method == 'POST':
        from projects.models import Project
        project = get_object_or_404(Project, pk=pk)
        project.is_featured = not project.is_featured
        project.save(update_fields=['is_featured'])

        status_text = "featured" if project.is_featured else "unmarked as featured"
        messages.success(request, f'Project "{project.title}" is now {status_text}.')
    return redirect('accounts:dashboard')


@admin_required
def admin_delete_project_view(request, pk):
    """Admin action to delete or cancel a project."""
    if request.method == 'POST':
        from projects.models import Project
        project = get_object_or_404(Project, pk=pk)
        title = project.title
        project.delete()
        messages.success(request, f'Project "{title}" has been deleted by administrator.')
    return redirect('accounts:dashboard')


@admin_required
def admin_toggle_user_status_view(request, pk):
    """Admin action to activate or deactivate a user account."""
    if request.method == 'POST':
        target_user = get_object_or_404(User, pk=pk)
        if target_user == request.user:
            messages.error(request, "You cannot deactivate your own administrator account.")
        else:
            target_user.is_active = not target_user.is_active
            target_user.save(update_fields=['is_active'])
            status_text = "activated" if target_user.is_active else "deactivated"
            messages.success(request, f'User account {target_user.email} has been {status_text}.')
    return redirect(f"{reverse('accounts:dashboard')}?tab=users")



@admin_required
def admin_handle_report_view(request, report_type, pk, action):
    """Admin action to resolve or reject reported projects or comments."""
    if request.method == 'POST':
        from projects.models import ProjectReport, CommentReport
        if report_type == 'project':
            report = get_object_or_404(ProjectReport, pk=pk)
            if action in ['resolved', 'rejected']:
                report.status = action
                report.save(update_fields=['status'])
                messages.success(request, f'Project report #{report.id} marked as {action}.')
        elif report_type == 'comment':
            report = get_object_or_404(CommentReport, pk=pk)
            if action == 'delete_comment':
                if report.comment:
                    report.comment.delete()
                report.status = 'resolved'
                report.save(update_fields=['status'])
                messages.success(request, f'Reported comment deleted and report #{report.id} resolved.')
            elif action in ['resolved', 'rejected']:
                report.status = action
                report.save(update_fields=['status'])
                messages.success(request, f'Comment report #{report.id} marked as {action}.')
    return redirect('accounts:dashboard')


@admin_required
def admin_manage_category_view(request):
    """Admin action to create, edit, or safely delete categories."""
    if request.method == 'POST':
        from projects.models import Category
        action = request.POST.get('action')
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        category_id = request.POST.get('category_id')

        if action == 'create':
            if not name:
                messages.error(request, "Category name cannot be empty.")
            elif Category.objects.filter(name__iexact=name).exists():
                messages.error(request, f'A category named "{name}" already exists.')
            else:
                Category.objects.create(name=name, slug=slugify(name), description=description)
                messages.success(request, f'Category "{name}" created successfully.')

        elif action == 'edit' and category_id:
            category = get_object_or_404(Category, pk=category_id)
            if not name:
                messages.error(request, "Category name cannot be empty.")
            else:
                category.name = name
                category.slug = slugify(name)
                category.description = description
                category.save()
                messages.success(request, f'Category "{name}" updated successfully.')

        elif action == 'delete' and category_id:
            category = get_object_or_404(Category, pk=category_id)
            if category.projects.exists():
                messages.error(
                    request,
                    f'Cannot delete category "{category.name}" because it contains {category.projects.count()} project(s). Reassign or delete those projects first.'
                )
            else:
                cat_name = category.name
                category.delete()
                messages.success(request, f'Category "{cat_name}" has been deleted.')

    return redirect('accounts:dashboard')



@login_required
def profile_view(request):
    """User profile displaying personal info, their projects, and their donations."""
    user = request.user
    user_projects = user.projects.all().order_by('-created_at')
    user_donations = user.donations.select_related('project').order_by('-created_at')

    context = {
        'profile_user': user,
        'user_projects': user_projects,
        'user_donations': user_donations,
    }
    return render(request, 'accounts/profile.html', context)


@login_required
def edit_profile_view(request):
    """Allows user to edit all profile fields EXCEPT email."""
    user = request.user

    if request.method == 'POST':
        form = UserProfileEditForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your profile has been updated successfully!')
            return redirect('accounts:profile')
    else:
        form = UserProfileEditForm(instance=user)

    return render(request, 'accounts/edit_profile.html', {'form': form, 'user_obj': user})


@login_required
def delete_account_view(request):
    """Allows user to delete their account with password confirmation."""
    user = request.user

    if request.method == 'POST':
        form = AccountDeleteForm(user=user, data=request.POST)
        if form.is_valid():
            logout(request)
            user.delete()
            messages.success(request, 'Your account has been deleted successfully. We are sorry to see you go.')
            return redirect('home')
    else:
        form = AccountDeleteForm(user=user)

    return render(request, 'accounts/delete_account.html', {'form': form})


@login_required
def remove_profile_photo_view(request):
    """
    Allows the authenticated user to remove their own profile photo.
    Deletes the physical image file from storage and clears the profile_picture field.
    """
    if request.method == 'POST':
        user = request.user
        if user.profile_picture:
            try:
                storage = user.profile_picture.storage
                name = user.profile_picture.name
                if storage and name and storage.exists(name):
                    storage.delete(name)
            except Exception:
                pass
            user.profile_picture = None
            user.save(update_fields=['profile_picture'])
            messages.success(request, 'Profile photo removed successfully.')
        else:
            messages.info(request, 'You do not have a profile photo to remove.')

    referer = request.META.get('HTTP_REFERER')
    if referer and ('edit' in referer or 'profile' in referer):
        return redirect(referer)
    return redirect('accounts:profile')


def facebook_login_view(request):
    """
    Initiates Meta / Facebook OAuth 2.0 authorization flow:
    1. Generates secure random state parameter for CSRF protection.
    2. Builds Meta authorization URL with required email & public_profile scopes.
    3. Redirects user to Facebook Login dialog.
    """
    app_id = getattr(settings, 'FACEBOOK_APP_ID', '').strip()
    if not app_id:
        messages.error(request, 'Facebook Login is currently not configured on this server.')
        return redirect('accounts:login')

    # Cryptographically secure random state
    state = secrets.token_urlsafe(32)
    request.session['facebook_oauth_state'] = state

    redirect_uri = getattr(settings, 'FACEBOOK_REDIRECT_URI', '').strip()
    if not redirect_uri:
        redirect_uri = request.build_absolute_uri(reverse('accounts:facebook_callback'))

    api_version = getattr(settings, 'FACEBOOK_API_VERSION', 'v20.0')
    params = {
        'client_id': app_id,
        'redirect_uri': redirect_uri,
        'state': state,
        'scope': 'email,public_profile',
        'response_type': 'code',
    }
    fb_auth_url = f"https://www.facebook.com/{api_version}/dialog/oauth?{urllib.parse.urlencode(params)}"
    return redirect(fb_auth_url)


def facebook_callback_view(request):
    """
    Handles Meta / Facebook OAuth 2.0 callback:
    1. Handles authorization cancellation/denial gracefully.
    2. Enforces state token verification (anti-CSRF protection).
    3. Exchanges authorization code for access token.
    4. Retrieves verified identity & profile data from Meta Graph API.
    5. Links to existing Tamweel user or securely creates new user without passwords.
    6. Logs the user in and redirects to home.
    """
    # 1. Check for cancellation or errors from Facebook
    error = request.GET.get('error')
    if error:
        error_desc = request.GET.get('error_description', 'Facebook authentication was cancelled.')
        logger.warning("Facebook OAuth error returned: %s (%s)", error, error_desc)
        messages.info(request, 'Facebook login was cancelled or denied.')
        return redirect('accounts:login')

    # 2. Validate cryptographic state
    state = request.GET.get('state')
    saved_state = request.session.pop('facebook_oauth_state', None)
    if not state or not saved_state or not secrets.compare_digest(state, saved_state):
        logger.error("Facebook OAuth state mismatch: received=%s, expected=%s", state, saved_state)
        messages.error(request, 'Security validation failed (OAuth state mismatch). Please try logging in again.')
        return redirect('accounts:login')

    code = request.GET.get('code')
    if not code:
        messages.error(request, 'No authorization code received from Facebook.')
        return redirect('accounts:login')

    app_id = getattr(settings, 'FACEBOOK_APP_ID', '').strip()
    app_secret = getattr(settings, 'FACEBOOK_APP_SECRET', '').strip()
    redirect_uri = getattr(settings, 'FACEBOOK_REDIRECT_URI', '').strip()
    if not redirect_uri:
        redirect_uri = request.build_absolute_uri(reverse('accounts:facebook_callback'))

    api_version = getattr(settings, 'FACEBOOK_API_VERSION', 'v20.0')

    # 3. Exchange code for access token
    token_url = f"https://graph.facebook.com/{api_version}/oauth/access_token"
    token_params = {
        'client_id': app_id,
        'client_secret': app_secret,
        'redirect_uri': redirect_uri,
        'code': code,
    }

    try:
        req = urllib.request.Request(
            f"{token_url}?{urllib.parse.urlencode(token_params)}",
            headers={'User-Agent': 'Tamweel-Crowdfunding-Platform'}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            token_data = json.loads(response.read().decode('utf-8'))
            access_token = token_data.get('access_token')

        if not access_token:
            messages.error(request, 'Failed to obtain access token from Facebook.')
            return redirect('accounts:login')

        # 4. Fetch user profile from Graph API
        me_url = f"https://graph.facebook.com/{api_version}/me"
        me_params = {
            'fields': 'id,first_name,last_name,name,email,picture.type(large)',
            'access_token': access_token
        }
        me_req = urllib.request.Request(
            f"{me_url}?{urllib.parse.urlencode(me_params)}",
            headers={'User-Agent': 'Tamweel-Crowdfunding-Platform'}
        )
        with urllib.request.urlopen(me_req, timeout=10) as me_response:
            fb_user_data = json.loads(me_response.read().decode('utf-8'))

    except Exception as e:
        logger.error("Facebook API error during OAuth callback: %s", e, exc_info=True)
        messages.error(request, 'Could not communicate with Facebook. Please try again or use normal login.')
        return redirect('accounts:login')

    fb_id = fb_user_data.get('id')
    if not fb_id:
        messages.error(request, 'Facebook identity information is incomplete.')
        return redirect('accounts:login')

    fb_email = fb_user_data.get('email', '').strip().lower()
    raw_name = fb_user_data.get('name', '').strip()
    name_parts = raw_name.split() if raw_name else []
    first_name = fb_user_data.get('first_name') or (name_parts[0] if name_parts else 'Facebook')
    last_name = fb_user_data.get('last_name') or (' '.join(name_parts[1:]) if len(name_parts) > 1 else 'User')

    # 5. Account matching & linking logic
    # Scenario A: Facebook Social Account already linked
    social_account = FacebookSocialAccount.objects.filter(facebook_id=fb_id).select_related('user').first()
    if social_account:
        user = social_account.user
        if not user.is_active:
            user.is_active = True
            user.save(update_fields=['is_active'])
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        messages.success(request, f'Welcome back, {user.get_full_name()}!')
        return redirect('home')

    # Scenario B: Existing user with the same email
    if fb_email:
        existing_user = User.objects.filter(email__iexact=fb_email).first()
        if existing_user:
            # Link this Facebook account to existing user
            FacebookSocialAccount.objects.create(user=existing_user, facebook_id=fb_id)
            if not existing_user.is_active:
                existing_user.is_active = True
                existing_user.save(update_fields=['is_active'])
            login(request, existing_user, backend='django.contrib.auth.backends.ModelBackend')
            messages.success(request, 'Successfully connected and logged in with your Facebook account.')
            return redirect('home')

    # Scenario C: Brand new user
    account_email = fb_email if fb_email else f"fb_{fb_id}@facebook.tamweel.com"
    new_user = User.objects.create_user(
        email=account_email,
        first_name=first_name,
        last_name=last_name,
        is_active=True,
        password=None
    )
    FacebookSocialAccount.objects.create(user=new_user, facebook_id=fb_id)
    login(request, new_user, backend='django.contrib.auth.backends.ModelBackend')
    messages.success(request, f'Welcome to Tamweel, {new_user.first_name}! Your account was created with Facebook.')
    return redirect('home')




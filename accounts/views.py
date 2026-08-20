from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.urls import reverse

from .forms import UserRegistrationForm, UserLoginForm, UserProfileEditForm, AccountDeleteForm
from .tokens import generate_activation_token, verify_activation_token

User = get_user_model()


def register_view(request):
    """Handles new user registration and sends 24h activation email."""
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            uidb64, token = generate_activation_token(user)
            activation_link = request.build_absolute_uri(
                reverse('accounts:activate', kwargs={'uidb64': uidb64, 'token': token})
            )

            # Send activation email
            subject = 'Activate Your CrowdFund Egypt Account'
            context = {
                'user': user,
                'activation_link': activation_link,
            }
            html_content = render_to_string('accounts/activation_email.html', context)
            text_content = strip_tags(html_content)

            try:
                msg = EmailMultiAlternatives(
                    subject=subject,
                    body=text_content,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[user.email]
                )
                msg.attach_alternative(html_content, "text/html")
                msg.send(fail_silently=False)
            except Exception as e:
                # Log email error if needed; in development console backend works flawlessly
                pass

            return render(request, 'accounts/activation_sent.html', {'email': user.email})
    else:
        form = UserRegistrationForm()

    return render(request, 'accounts/register.html', {'form': form})


def activate_account_view(request, uidb64, token):
    """Activates user account if token is valid and under 24 hours old."""
    user, status = verify_activation_token(uidb64, token)

    if status == 'valid' and user is not None:
        user.is_active = True
        user.save()
        messages.success(request, 'Your account has been successfully activated! You can now log in.')
        return render(request, 'accounts/activation_success.html', {'user': user})
    elif status == 'expired':
        return render(request, 'accounts/activation_invalid.html', {
            'error_title': 'Activation Link Expired',
            'error_message': 'This activation link has expired (links are valid for 24 hours). Please contact support or re-register.'
        })
    else:
        return render(request, 'accounts/activation_invalid.html', {
            'error_title': 'Invalid Activation Link',
            'error_message': 'This activation link is invalid or has already been used.'
        })


def login_view(request):
    """Handles user login with email and password."""
    if request.user.is_authenticated:
        return redirect('home')

    next_url = request.GET.get('next', 'home')

    if request.method == 'POST':
        form = UserLoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data.get('email')
            password = form.cleaned_data.get('password')

            # Check if user exists but inactive
            try:
                user_obj = User.objects.get(email__iexact=email)
                if not user_obj.is_active:
                    messages.error(
                        request,
                        'Your account is not activated yet. Please check your email for the 24-hour activation link.'
                    )
                    return render(request, 'accounts/login.html', {'form': form})
            except User.DoesNotExist:
                pass

            user = authenticate(request, email=email, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'Welcome back, {user.first_name}!')
                return redirect(next_url if next_url else 'home')
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

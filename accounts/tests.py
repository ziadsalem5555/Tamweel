from decimal import Decimal
from datetime import timedelta
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core import mail
from django.utils import timezone

from accounts.validators import validate_egyptian_phone
from accounts.models import EmailOTP

User = get_user_model()


class EgyptianPhoneValidationTests(TestCase):
    def test_valid_egyptian_phones(self):
        valid_numbers = [
            '01012345678',
            '01112345678',
            '01212345678',
            '01512345678',
            '+201012345678',
            '+201123456789',
            '00201234567890',
            '010 1234 5678',
            '011-2345-6789',
        ]
        for num in valid_numbers:
            try:
                validate_egyptian_phone(num)
            except ValidationError:
                self.fail(f"validate_egyptian_phone raised ValidationError unexpectedly for valid number {num}")

    def test_invalid_egyptian_phones(self):
        invalid_numbers = [
            '01312345678',  # 013 is not valid mobile prefix
            '01412345678',  # 014 is not valid mobile prefix
            '1234567',      # Too short
            '010123456789', # Too long
            'abcdefghijk',  # Non numeric
            '0223456789',   # Landline
        ]
        for num in invalid_numbers:
            with self.assertRaises(ValidationError):
                validate_egyptian_phone(num)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class AccountOTPRegistrationTests(TestCase):
    def setUp(self):
        self.client = Client()
        mail.outbox.clear()

    def test_registration_creates_inactive_user_generates_otp_and_sends_email(self):
        url = reverse('accounts:register')
        data = {
            'first_name': 'Ahmed',
            'last_name': 'Ali',
            'email': 'ahmed@example.com',
            'mobile_phone': '01012345678',
            'password': 'StrongPassword123!',
            'confirm_password': 'StrongPassword123!',
        }
        response = self.client.post(url, data)
        # Should redirect to OTP verification page
        self.assertRedirects(response, f"{reverse('accounts:verify_otp')}?email=ahmed@example.com")

        # Check user creation and inactive status
        user = User.objects.get(email='ahmed@example.com')
        self.assertFalse(user.is_active, "Newly registered user must be inactive until verification")
        self.assertEqual(user.first_name, 'Ahmed')
        self.assertEqual(user.mobile_phone, '01012345678')

        # Check OTP record created in DB
        otp_record = EmailOTP.objects.filter(user=user).first()
        self.assertIsNotNone(otp_record, "OTP record must exist in DB")
        self.assertEqual(len(otp_record.otp_code), 6, "OTP code must be 6 digits")
        self.assertTrue(otp_record.otp_code.isdigit(), "OTP code must be numeric")

        # Verify email delivery contains BOTH OTP and Activation Link
        self.assertEqual(len(mail.outbox), 1, "Exactly one email should be sent upon registration")
        sent_email = mail.outbox[0]
        self.assertEqual(sent_email.to, ['ahmed@example.com'])
        self.assertIn("Verify your Tamweel account", sent_email.subject)
        self.assertIn(otp_record.otp_code, sent_email.body)
        self.assertIn("Welcome to Tamweel.", sent_email.body)
        self.assertIn("This code expires in 10 minutes.", sent_email.body)
        self.assertIn("accounts/activate/", sent_email.body)
        self.assertIn("This activation link expires in 24 hours.", sent_email.body)

    def test_correct_otp_verification_activates_user_and_redirects_to_login(self):
        user = User.objects.create_user(
            email='test_verify@example.com',
            password='Password123!',
            first_name='Test',
            last_name='User',
            mobile_phone='01011112222',
            is_active=False
        )
        otp = EmailOTP.generate_otp_for_user(user, validity_minutes=10)

        verify_url = reverse('accounts:verify_otp')
        response = self.client.post(verify_url, {
            'email': user.email,
            'otp_code': otp.otp_code
        })

        # Should redirect to login page
        self.assertRedirects(response, reverse('accounts:login'))

        user.refresh_from_db()
        self.assertTrue(user.is_active, "User must be active after entering correct OTP")

        # OTP should be deleted / invalidated
        self.assertFalse(EmailOTP.objects.filter(user=user).exists(), "OTP record must be invalidated on success")

        # User can now successfully login
        login_resp = self.client.post(reverse('accounts:login'), {
            'email': user.email,
            'password': 'Password123!'
        })
        self.assertRedirects(login_resp, reverse('home'))
        self.assertIn('_auth_user_id', self.client.session)

    def test_activation_link_directly_activates_user_and_invalidates_otp(self):
        from accounts.tokens import generate_activation_token
        user = User.objects.create_user(
            email='link_user@example.com',
            password='Password123!',
            first_name='Link',
            last_name='User',
            mobile_phone='01066778899',
            is_active=False
        )
        otp = EmailOTP.generate_otp_for_user(user, validity_minutes=10)
        self.assertTrue(EmailOTP.objects.filter(user=user).exists())

        uidb64, token = generate_activation_token(user)
        activate_url = reverse('accounts:activate', kwargs={'uidb64': uidb64, 'token': token})

        # Visiting valid activation link activates account directly
        response = self.client.get(activate_url)
        self.assertRedirects(response, reverse('accounts:login'))

        user.refresh_from_db()
        self.assertTrue(user.is_active, "Account must be active after clicking valid activation link")

        # OTP must be invalidated
        self.assertFalse(EmailOTP.objects.filter(user=user).exists(), "OTP must be invalidated after link activation")

        # User can now login
        login_resp = self.client.post(reverse('accounts:login'), {
            'email': user.email,
            'password': 'Password123!'
        })
        self.assertRedirects(login_resp, reverse('home'))
        self.assertIn('_auth_user_id', self.client.session)

    def test_used_activation_link_cannot_re_activate(self):
        from accounts.tokens import generate_activation_token
        user = User.objects.create_user(
            email='already_active@example.com',
            password='Password123!',
            first_name='Already',
            last_name='Active',
            mobile_phone='01066778800',
            is_active=False
        )
        uidb64, token = generate_activation_token(user)
        activate_url = reverse('accounts:activate', kwargs={'uidb64': uidb64, 'token': token})

        # 1st activation succeeds
        resp1 = self.client.get(activate_url)
        self.assertRedirects(resp1, reverse('accounts:login'))
        user.refresh_from_db()
        self.assertTrue(user.is_active)

        # 2nd activation via same link reports already activated and redirects to login
        resp2 = self.client.get(activate_url)
        self.assertRedirects(resp2, reverse('accounts:login'))

    def test_expired_activation_link_fails_and_does_not_activate(self):
        from accounts.tokens import generate_activation_token
        user = User.objects.create_user(
            email='expired_link@example.com',
            password='Password123!',
            first_name='Expired',
            last_name='Link',
            mobile_phone='01066778811',
            is_active=False
        )
        uidb64, token = generate_activation_token(user)
        activate_url = reverse('accounts:activate', kwargs={'uidb64': uidb64, 'token': token})

        # Advance beyond 24 hours (86400 seconds) by calling verify with max_age=0 or checking expired template
        from accounts.tokens import verify_activation_token
        _, status_code = verify_activation_token(uidb64, token, max_age=-1)
        self.assertEqual(status_code, 'expired')

        # Test request with expired token
        from unittest.mock import patch
        with patch('accounts.views.verify_activation_token', return_value=(user, 'expired')):
            response = self.client.get(activate_url)
            self.assertEqual(response.status_code, 200)
            self.assertTemplateUsed(response, 'accounts/activation_invalid.html')
            self.assertContains(response, 'expired')
            self.assertContains(response, 'Resend Verification Email')

        user.refresh_from_db()
        self.assertFalse(user.is_active, "Expired activation link must not activate user")

    def test_resend_verification_generates_new_otp_and_activation_email(self):
        user = User.objects.create_user(
            email='test_resend_dual@example.com',
            password='Password123!',
            first_name='Resend',
            last_name='Dual',
            mobile_phone='01055557777',
            is_active=False
        )
        otp = EmailOTP.generate_otp_for_user(user, validity_minutes=10)
        old_code = otp.otp_code

        # Advance last_sent_at past 60s cooldown
        otp.last_sent_at = timezone.now() - timedelta(seconds=65)
        otp.save()

        resend_url = reverse('accounts:resend_otp')
        mail.outbox.clear()

        response = self.client.post(resend_url, {'email': user.email})
        self.assertRedirects(response, f"{reverse('accounts:verify_otp')}?email={user.email}")
        self.assertEqual(len(mail.outbox), 1, "Should send exactly one new email with OTP + activation link")

        sent_email = mail.outbox[0]
        new_otp = EmailOTP.objects.get(user=user)
        self.assertNotEqual(new_otp.otp_code, old_code, "Old OTP must be replaced")
        self.assertIn(new_otp.otp_code, sent_email.body)
        self.assertIn("accounts/activate/", sent_email.body)




class UserProfileTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='profile_test@example.com',
            password='Password123!',
            first_name='Mona',
            last_name='Zaki',
            mobile_phone='01011112222',
            is_active=True,
            country='Egypt'
        )
        self.client.force_login(self.user)

    def test_profile_view_accessible(self):
        url = reverse('accounts:profile')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Mona Zaki')
        self.assertContains(response, '01011112222')

    def test_edit_profile_cannot_change_email(self):
        url = reverse('accounts:edit_profile')
        edit_data = {
            'first_name': 'Mona Updated',
            'last_name': 'Zaki Updated',
            'mobile_phone': '01033334444',
            'country': 'Egypt',
            'email': 'hacked_email@example.com',  # Should be ignored because not in UserProfileEditForm
        }
        response = self.client.post(url, edit_data)
        self.assertEqual(response.status_code, 302)

        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Mona Updated')
        self.assertEqual(self.user.mobile_phone, '01033334444')
        self.assertEqual(self.user.email, 'profile_test@example.com', "User email must remain unchanged")

    def test_delete_account_with_password(self):
        url = reverse('accounts:delete_account')
        
        # Wrong password -> fails
        bad_response = self.client.post(url, {'password': 'WrongPassword!'})
        self.assertEqual(bad_response.status_code, 200)
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

        # Correct password -> deletes account
        good_response = self.client.post(url, {'password': 'Password123!'})
        self.assertEqual(good_response.status_code, 302)
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())


class AdminDashboardTests(TestCase):
    def setUp(self):
        from projects.models import Category, Project, Donation
        self.client = Client()
        # Normal user
        self.normal_user = User.objects.create_user(
            email='normal_user@example.com',
            password='Password123!',
            first_name='Normal',
            last_name='User',
            mobile_phone='01012345678',
            is_active=True,
            is_staff=False,
            country='Egypt'
        )
        # Admin / Staff user
        self.admin_user = User.objects.create_user(
            email='staff_admin@example.com',
            password='Password123!',
            first_name='Admin',
            last_name='Manager',
            mobile_phone='01199887766',
            is_active=True,
            is_staff=True,
            is_superuser=True
        )
        self.category = Category.objects.create(name='Technology', slug='technology')
        self.project = Project.objects.create(
            title='AI Health Assistant',
            details='Deep learning healthcare solution for Egypt',
            category=self.category,
            creator=self.normal_user,
            total_target=Decimal('50000.00'),
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(days=30),
            status='running'
        )
        Donation.objects.create(
            project=self.project,
            user=self.admin_user,
            amount=Decimal('5000.00')
        )

    def test_unauthenticated_user_redirected_to_login(self):
        url = reverse('accounts:dashboard')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response.get('Location'))

    def test_normal_user_blocked_with_403_forbidden(self):
        """Normal registered users must NOT be able to access the admin dashboard."""
        self.client.force_login(self.normal_user)
        url = reverse('accounts:dashboard')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403, "Normal user must receive 403 Forbidden")

    def test_normal_user_blocked_from_admin_actions(self):
        """Normal user cannot toggle featured or manage categories."""
        self.client.force_login(self.normal_user)
        toggle_url = reverse('accounts:admin_toggle_featured', kwargs={'pk': self.project.pk})
        resp = self.client.post(toggle_url)
        self.assertEqual(resp.status_code, 403)

    def test_admin_user_can_access_dashboard_and_stats(self):
        """Admin/staff user can view dashboard, statistics, and tables."""
        self.client.force_login(self.admin_user)
        url = reverse('accounts:dashboard')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/dashboard.html')

        # Check content and greeting
        self.assertContains(response, 'Admin Dashboard')
        self.assertContains(response, 'AI Health Assistant')

        # Check calculated statistics
        self.assertEqual(response.context['total_users'], 2)
        self.assertEqual(response.context['total_projects'], 1)
        self.assertEqual(response.context['total_donations'], 1)
        self.assertEqual(response.context['total_raised'], Decimal('5000.00'))

    def test_admin_can_toggle_featured_project(self):
        self.client.force_login(self.admin_user)
        self.assertFalse(self.project.is_featured)

        toggle_url = reverse('accounts:admin_toggle_featured', kwargs={'pk': self.project.pk})
        response = self.client.post(toggle_url)
        self.assertEqual(response.status_code, 302)

        self.project.refresh_from_db()
        self.assertTrue(self.project.is_featured, "Project must now be marked as featured")

    def test_admin_can_view_user_management_and_search(self):
        """Admin can view user list and search users by name/email."""
        self.client.force_login(self.admin_user)
        url = reverse('accounts:dashboard') + '?tab=users&user_q=Normal'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'User Management')
        self.assertContains(response, 'Normal')
        self.assertContains(response, 'normal_user@example.com')

    def test_admin_can_delete_normal_user_permanently(self):
        """Admin can delete a normal user account and its database records."""
        self.client.force_login(self.admin_user)
        user_to_delete = User.objects.create_user(
            email='delete_me@example.com',
            password='Password123!',
            first_name='Delete',
            last_name='Me',
            mobile_phone='01055554444',
            is_active=True
        )

        delete_url = reverse('accounts:admin_delete_user', kwargs={'pk': user_to_delete.pk})
        response = self.client.post(delete_url)
        self.assertEqual(response.status_code, 302)

        # Confirm user is removed from database
        self.assertFalse(User.objects.filter(pk=user_to_delete.pk).exists())

    def test_admin_cannot_delete_own_account(self):
        """Admin is prevented from deleting their own currently logged-in account."""
        self.client.force_login(self.admin_user)
        delete_url = reverse('accounts:admin_delete_user', kwargs={'pk': self.admin_user.pk})
        response = self.client.post(delete_url)
        self.assertEqual(response.status_code, 302)

        # Admin must still exist
        self.assertTrue(User.objects.filter(pk=self.admin_user.pk).exists())

    def test_normal_user_blocked_from_deleting_users_403(self):
        """Normal user calling admin_delete_user endpoint receives 403 Forbidden."""
        self.client.force_login(self.normal_user)
        victim = User.objects.create_user(
            email='victim@example.com',
            password='Password123!',
            first_name='Victim',
            last_name='User',
            mobile_phone='01033332222',
            is_active=True
        )
        delete_url = reverse('accounts:admin_delete_user', kwargs={'pk': victim.pk})
        response = self.client.post(delete_url)
        self.assertEqual(response.status_code, 403, "Normal user must be forbidden from calling admin delete")
        self.assertTrue(User.objects.filter(pk=victim.pk).exists())

    def test_superuser_can_promote_and_demote_admin(self):
        """Superuser promotes normal user to staff/admin, then revokes admin access."""
        # 1. Promote to Admin
        self.client.force_login(self.admin_user)
        make_admin_url = reverse('accounts:admin_make_admin', kwargs={'pk': self.normal_user.pk})
        resp_promote = self.client.post(make_admin_url)
        self.assertEqual(resp_promote.status_code, 302)

        self.normal_user.refresh_from_db()
        self.assertTrue(self.normal_user.is_staff, "User must now have is_staff=True")

        # 2. Promoted user can now access the admin dashboard
        self.client.force_login(self.normal_user)
        dashboard_resp = self.client.get(reverse('accounts:dashboard'))
        self.assertEqual(dashboard_resp.status_code, 200, "Promoted user should access dashboard")

        # 3. Staff user cannot promote others (only superusers can)
        other_user = User.objects.create_user(
            email='other@example.com',
            password='Password123!',
            first_name='Other',
            last_name='Person',
            mobile_phone='01044445555',
            is_active=True
        )
        resp_staff_promote = self.client.post(reverse('accounts:admin_make_admin', kwargs={'pk': other_user.pk}))
        self.assertEqual(resp_staff_promote.status_code, 403, "Non-superuser staff cannot promote others")

        # 4. Superuser revokes admin privileges
        self.client.force_login(self.admin_user)
        remove_admin_url = reverse('accounts:admin_remove_admin', kwargs={'pk': self.normal_user.pk})
        resp_demote = self.client.post(remove_admin_url)
        self.assertEqual(resp_demote.status_code, 302)

        self.normal_user.refresh_from_db()
        self.assertFalse(self.normal_user.is_staff, "User must now have is_staff=False")

        # 5. Demoted user can no longer access dashboard
        self.client.force_login(self.normal_user)
        dashboard_blocked = self.client.get(reverse('accounts:dashboard'))
        self.assertEqual(dashboard_blocked.status_code, 403, "Demoted user must receive 403 Forbidden")

    def test_normal_user_cannot_call_make_or_remove_admin_endpoints(self):
        """Normal unprivileged user calling make-admin or remove-admin receives 403 Forbidden."""
        self.client.force_login(self.normal_user)
        resp1 = self.client.post(reverse('accounts:admin_make_admin', kwargs={'pk': self.admin_user.pk}))
        self.assertEqual(resp1.status_code, 403)

        resp2 = self.client.post(reverse('accounts:admin_remove_admin', kwargs={'pk': self.admin_user.pk}))
        self.assertEqual(resp2.status_code, 403)


class ProfilePhotoManagementTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='photouser@example.com',
            password='Password123!',
            first_name='Photo',
            last_name='User',
            mobile_phone='01077778888',
            is_active=True
        )

    def test_user_can_remove_profile_photo_and_cleans_up_storage(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        # Attach a dummy image file
        img_content = b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\x05\x04\x04\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b'
        upload = SimpleUploadedFile('test_avatar.gif', img_content, content_type='image/gif')
        self.user.profile_picture = upload
        self.user.save()

        self.assertTrue(bool(self.user.profile_picture))
        photo_path = self.user.profile_picture.name
        storage = self.user.profile_picture.storage
        self.assertTrue(storage.exists(photo_path))

        # Login and post to remove_profile_photo
        self.client.force_login(self.user)
        remove_url = reverse('accounts:remove_profile_photo')
        response = self.client.post(remove_url)
        self.assertEqual(response.status_code, 302)

        # Refresh from database
        self.user.refresh_from_db()
        self.assertFalse(bool(self.user.profile_picture))
        self.assertFalse(storage.exists(photo_path), "Image file must be removed from storage")

    def test_unauthenticated_user_redirected_to_login(self):
        remove_url = reverse('accounts:remove_profile_photo')
        response = self.client.post(remove_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response.get('Location'))


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class PasswordResetTests(TestCase):
    def setUp(self):
        self.client = Client()
        mail.outbox.clear()
        self.user = User.objects.create_user(
            email='sarah.reset@example.com',
            password='OldPassword123!',
            first_name='Sarah',
            last_name='Reset',
            mobile_phone='01022223333',
            is_active=True
        )

    def test_password_reset_request_sends_email_with_secure_link(self):
        reset_url = reverse('accounts:password_reset')
        resp = self.client.post(reset_url, {'email': 'sarah.reset@example.com'})
        self.assertRedirects(resp, reverse('accounts:password_reset_done'))

        # Check email in outbox
        self.assertEqual(len(mail.outbox), 1)
        sent_email = mail.outbox[0]
        self.assertIn('sarah.reset@example.com', sent_email.to)
        self.assertEqual(sent_email.subject.strip(), 'Reset your Tamweel password')
        self.assertIn('password-reset-confirm', sent_email.body)

    def test_complete_password_reset_flow_updates_password(self):
        # 1. Request reset
        self.client.post(reverse('accounts:password_reset'), {'email': 'sarah.reset@example.com'})
        self.assertEqual(len(mail.outbox), 1)
        sent_email = mail.outbox[0]

        # Extract reset link from email
        import re
        match = re.search(r'/accounts/password-reset-confirm/([^/]+)/([^/\s]+)/', sent_email.body)
        self.assertIsNotNone(match, "Reset link pattern must exist in email body")
        uidb64, token = match.group(1), match.group(2)

        confirm_url = reverse('accounts:password_reset_confirm', kwargs={'uidb64': uidb64, 'token': token})

        # 2. Open confirmation page (follows redirect to session-based set-password URL)
        resp_confirm_get = self.client.get(confirm_url, follow=True)
        self.assertEqual(resp_confirm_get.status_code, 200)
        self.assertContains(resp_confirm_get, 'Reset Password')

        # 3. Submit new password
        resp_confirm_post = self.client.post(resp_confirm_get.request['PATH_INFO'], {
            'new_password1': 'BrandNewPassword123!',
            'new_password2': 'BrandNewPassword123!',
        })
        self.assertRedirects(resp_confirm_post, reverse('accounts:password_reset_complete'))

        # 4. Old password must fail
        self.assertFalse(self.client.login(email='sarah.reset@example.com', password='OldPassword123!'))

        # 5. New password must succeed
        self.assertTrue(self.client.login(email='sarah.reset@example.com', password='BrandNewPassword123!'))

        # 6. Reusing old reset link must now fail because password hash changed
        resp_reuse = self.client.get(confirm_url, follow=True)
        self.assertContains(resp_reuse, 'invalid or has already expired')


    def test_unregistered_email_shows_generic_response_and_does_not_send_email(self):
        reset_url = reverse('accounts:password_reset')
        resp = self.client.post(reset_url, {'email': 'nonexistent_user@example.com'})
        self.assertRedirects(resp, reverse('accounts:password_reset_done'))
        # No email sent, preventing account enumeration
        self.assertEqual(len(mail.outbox), 0)

    def test_invalid_or_corrupt_token_rejected(self):
        from django.utils.http import urlsafe_base64_encode
        from django.utils.encoding import force_bytes
        uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))
        invalid_url = reverse('accounts:password_reset_confirm', kwargs={'uidb64': uidb64, 'token': 'invalid-token-12345'})
        resp = self.client.get(invalid_url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'invalid or has already expired')


@override_settings(
    FACEBOOK_APP_ID='test_fb_app_id_123',
    FACEBOOK_APP_SECRET='test_fb_app_secret_456',
    FACEBOOK_REDIRECT_URI='http://testserver/accounts/facebook/callback/'
)
class FacebookOAuthLoginTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_login_page_renders_continue_with_facebook_button(self):
        resp = self.client.get(reverse('accounts:login'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Continue with Facebook')
        self.assertContains(resp, reverse('accounts:facebook_login'))

    def test_facebook_login_initiates_oauth_redirect_and_stores_state(self):
        resp = self.client.get(reverse('accounts:facebook_login'))
        self.assertEqual(resp.status_code, 302)
        redirect_target = resp.get('Location')
        self.assertIn('facebook.com', redirect_target)
        self.assertIn('client_id=test_fb_app_id_123', redirect_target)
        self.assertIn('scope=email%2Cpublic_profile', redirect_target)
        self.assertIn('state=', redirect_target)
        self.assertIn('facebook_oauth_state', self.client.session)

    def test_facebook_login_unconfigured_redirects_with_message(self):
        with override_settings(FACEBOOK_APP_ID=''):
            resp = self.client.get(reverse('accounts:facebook_login'))
            self.assertRedirects(resp, reverse('accounts:login'))

    def test_facebook_callback_cancelled_by_user_handled_gracefully(self):
        session = self.client.session
        session['facebook_oauth_state'] = 'test_valid_state'
        session.save()

        callback_url = reverse('accounts:facebook_callback') + '?error=access_denied&error_description=User+cancelled'
        resp = self.client.get(callback_url)
        self.assertRedirects(resp, reverse('accounts:login'))

    def test_facebook_callback_state_mismatch_rejected(self):
        session = self.client.session
        session['facebook_oauth_state'] = 'valid_state_123'
        session.save()

        callback_url = reverse('accounts:facebook_callback') + '?code=auth_code_123&state=tampered_state'
        resp = self.client.get(callback_url)
        self.assertRedirects(resp, reverse('accounts:login'))

    def test_facebook_callback_new_user_creates_account_and_logs_in(self):
        from unittest.mock import patch, MagicMock

        token_resp = MagicMock()
        token_resp.read.return_value = b'{"access_token": "mock_eaab_token_123", "token_type": "bearer"}'
        token_resp.__enter__.return_value = token_resp

        profile_resp = MagicMock()
        profile_resp.read.return_value = b'{"id": "100200300400", "first_name": "Tariq", "last_name": "Zaki", "email": "tariq.zaki@facebook-test.com"}'
        profile_resp.__enter__.return_value = profile_resp

        with patch('urllib.request.urlopen', side_effect=[token_resp, profile_resp]):
            session = self.client.session
            session['facebook_oauth_state'] = 'good_state_abc'
            session.save()

            callback_url = reverse('accounts:facebook_callback') + '?code=good_code_xyz&state=good_state_abc'
            resp = self.client.get(callback_url)
            self.assertRedirects(resp, reverse('home'))

            # Check DB: User created and linked
            user = User.objects.get(email='tariq.zaki@facebook-test.com')
            self.assertEqual(user.first_name, 'Tariq')
            self.assertEqual(user.last_name, 'Zaki')
            self.assertTrue(user.is_active)
            self.assertTrue(user.is_facebook_linked)
            self.assertEqual(user.facebook_account.facebook_id, '100200300400')

            # Check user is logged in
            self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)

    def test_facebook_callback_existing_email_user_links_account(self):
        from unittest.mock import patch, MagicMock

        # Create existing local user
        existing_user = User.objects.create_user(
            email='existing.donor@example.com',
            password='SecretPassword123!',
            first_name='Mona',
            last_name='Fahmy',
            mobile_phone='01066667777',
            is_active=True
        )
        self.assertFalse(existing_user.is_facebook_linked)

        token_resp = MagicMock()
        token_resp.read.return_value = b'{"access_token": "mock_token_456"}'
        token_resp.__enter__.return_value = token_resp

        profile_resp = MagicMock()
        profile_resp.read.return_value = b'{"id": "9988776655", "first_name": "Mona", "last_name": "Fahmy", "email": "existing.donor@example.com"}'
        profile_resp.__enter__.return_value = profile_resp

        with patch('urllib.request.urlopen', side_effect=[token_resp, profile_resp]):
            session = self.client.session
            session['facebook_oauth_state'] = 'link_state_123'
            session.save()

            callback_url = reverse('accounts:facebook_callback') + '?code=link_code_789&state=link_state_123'
            resp = self.client.get(callback_url)
            self.assertRedirects(resp, reverse('home'))

            # No duplicate user created
            self.assertEqual(User.objects.filter(email='existing.donor@example.com').count(), 1)
            existing_user.refresh_from_db()
            self.assertTrue(existing_user.is_facebook_linked)
            self.assertEqual(existing_user.facebook_account.facebook_id, '9988776655')

    def test_facebook_callback_existing_linked_user_logs_in_without_duplicate(self):
        from unittest.mock import patch, MagicMock

        user = User.objects.create_user(
            email='linked.user@example.com',
            password='Password123!',
            first_name='Karim',
            last_name='Nabil',
            is_active=True
        )
        from accounts.models import FacebookSocialAccount
        FacebookSocialAccount.objects.create(user=user, facebook_id='5544332211')

        token_resp = MagicMock()
        token_resp.read.return_value = b'{"access_token": "token_repeat"}'
        token_resp.__enter__.return_value = token_resp

        profile_resp = MagicMock()
        profile_resp.read.return_value = b'{"id": "5544332211", "name": "Karim Nabil", "email": "linked.user@example.com"}'
        profile_resp.__enter__.return_value = profile_resp

        with patch('urllib.request.urlopen', side_effect=[token_resp, profile_resp]):
            session = self.client.session
            session['facebook_oauth_state'] = 'repeat_state'
            session.save()

            callback_url = reverse('accounts:facebook_callback') + '?code=repeat_code&state=repeat_state'
            resp = self.client.get(callback_url)
            self.assertRedirects(resp, reverse('home'))

            self.assertEqual(User.objects.filter(email='linked.user@example.com').count(), 1)
            self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)









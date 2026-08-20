from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from accounts.validators import validate_egyptian_phone
from accounts.tokens import generate_activation_token, verify_activation_token

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


class AccountAuthAndActivationTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_registration_creates_inactive_user(self):
        url = reverse('accounts:register')
        data = {
            'first_name': 'Hossam',
            'last_name': 'Farouk',
            'email': 'hossam@example.com',
            'mobile_phone': '01012345678',
            'password': 'StrongPassword123!',
            'confirm_password': 'StrongPassword123!',
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/activation_sent.html')

        user = User.objects.get(email='hossam@example.com')
        self.assertFalse(user.is_active, "Registered user must be inactive until email activation")
        self.assertEqual(user.first_name, 'Hossam')
        self.assertEqual(user.mobile_phone, '01012345678')

    def test_activation_token_validation_and_expiration(self):
        user = User.objects.create_user(
            email='testuser@example.com',
            password='TestPassword123!',
            first_name='Test',
            last_name='User',
            mobile_phone='01123456789',
            is_active=False
        )
        uidb64, token = generate_activation_token(user)

        # 1. Valid token within max_age
        retrieved_user, status = verify_activation_token(uidb64, token, max_age=86400)
        self.assertEqual(status, 'valid')
        self.assertEqual(retrieved_user.pk, user.pk)

        # 2. Expired token (simulating max_age=0)
        expired_user, exp_status = verify_activation_token(uidb64, token, max_age=0)
        self.assertEqual(exp_status, 'expired')

        # 3. Invalid token
        inv_user, inv_status = verify_activation_token(uidb64, 'tampered_token')
        self.assertEqual(inv_status, 'invalid')

    def test_activation_view_activates_user(self):
        user = User.objects.create_user(
            email='activate_me@example.com',
            password='Password123!',
            first_name='Karim',
            last_name='Nabil',
            mobile_phone='01234567890',
            is_active=False
        )
        uidb64, token = generate_activation_token(user)

        url = reverse('accounts:activate', kwargs={'uidb64': uidb64, 'token': token})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        user.refresh_from_db()
        self.assertTrue(user.is_active, "User must be active after visiting valid activation link")

    def test_inactive_user_cannot_login(self):
        user = User.objects.create_user(
            email='inactive@example.com',
            password='Password123!',
            first_name='Inactive',
            last_name='User',
            mobile_phone='01512345678',
            is_active=False
        )

        login_url = reverse('accounts:login')
        response = self.client.post(login_url, {'email': 'inactive@example.com', 'password': 'Password123!'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Your account is not activated yet')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_active_user_login_and_logout(self):
        user = User.objects.create_user(
            email='active@example.com',
            password='Password123!',
            first_name='Active',
            last_name='User',
            mobile_phone='01098765432',
            is_active=True
        )

        # Login
        login_url = reverse('accounts:login')
        response = self.client.post(login_url, {'email': 'active@example.com', 'password': 'Password123!'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)

        # Logout
        logout_url = reverse('accounts:logout')
        response = self.client.get(logout_url)
        self.assertEqual(response.status_code, 302)
        self.assertNotIn('_auth_user_id', self.client.session)


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
            'email': 'hacked_email@example.com', # Should be ignored because not in UserProfileEditForm
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

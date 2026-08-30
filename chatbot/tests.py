"""
Unit and integration tests for the Tamweel AI Chatbot app.
All external Google Gemini API interactions are mocked; no live network calls are made during automated tests.
"""

import json
from unittest.mock import patch, MagicMock, call
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.cache import cache

from chatbot.services import (
    generate_chat_response,
    is_arabic_text,
    get_fallback_message,
    DEFAULT_FALLBACK_MESSAGE_EN,
    DEFAULT_FALLBACK_MESSAGE_AR,
    PRIMARY_MODEL,
    FALLBACK_MODEL,
)

User = get_user_model()


class ChatbotAPITests(TestCase):
    """Test suite for /chatbot/api/message/ endpoint and service layer."""

    def setUp(self):
        self.client = Client()
        self.api_url = reverse('chatbot:message_api')
        cache.clear()

        # Create a test user for auth testing
        self.user = User.objects.create_user(
            email='chatbot_tester@example.com',
            password='TestPassword123!',
            first_name='Ziad',
            last_name='Salem',
            mobile_phone='01012345678',
            is_active=True
        )

    def tearDown(self):
        cache.clear()

    # 1. Method verification
    def test_get_method_rejected_with_405(self):
        """GET requests must be rejected with HTTP 405 Method Not Allowed."""
        response = self.client.get(self.api_url)
        self.assertEqual(response.status_code, 405)

    def test_put_method_rejected_with_405(self):
        """PUT requests must be rejected with HTTP 405."""
        response = self.client.put(self.api_url, data='{}', content_type='application/json')
        self.assertEqual(response.status_code, 405)

    # 2. Input Validation Tests
    def test_empty_request_body_returns_400(self):
        """Empty request body returns HTTP 400."""
        response = self.client.post(self.api_url, data='', content_type='application/json')
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data.get('status'), 'error')

    def test_invalid_json_format_returns_400(self):
        """Malformed JSON string returns HTTP 400."""
        response = self.client.post(
            self.api_url,
            data='{invalid_json: true,}',
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data.get('status'), 'error')

    def test_missing_message_field_returns_400(self):
        """Missing 'message' key in JSON object returns HTTP 400."""
        payload = json.dumps({'query': 'How to donate?'})
        response = self.client.post(self.api_url, data=payload, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data.get('status'), 'error')

    def test_empty_message_returns_400(self):
        """Empty string message returns HTTP 400."""
        payload = json.dumps({'message': ''})
        response = self.client.post(self.api_url, data=payload, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data.get('status'), 'error')

    def test_whitespace_only_message_returns_400(self):
        """Whitespace-only message returns HTTP 400."""
        payload = json.dumps({'message': '     \n\t   '})
        response = self.client.post(self.api_url, data=payload, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data.get('status'), 'error')

    def test_message_exceeding_500_chars_returns_400(self):
        """Message exceeding maximum length of 500 characters returns HTTP 400."""
        long_message = 'A' * 501
        payload = json.dumps({'message': long_message})
        response = self.client.post(self.api_url, data=payload, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data.get('status'), 'error')
        self.assertIn('500 characters', data.get('error', ''))

    # 3. Successful Mocked Gemini API Calls
    @patch('chatbot.services.get_gemini_api_key', return_value='test-gemini-key')
    @patch('google.genai.Client')
    def test_successful_primary_gemini_generate_content_call(self, mock_client_cls, mock_get_key):
        """When primary model succeeds, only the primary model is called and returns HTTP 200."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.text = "To create a project on Tamweel, click 'Create Project' in the navigation bar."
        mock_client.models.generate_content.return_value = mock_response

        payload = json.dumps({'message': 'How do I create a project campaign?'})
        response = self.client.post(self.api_url, data=payload, content_type='application/json')

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get('status'), 'success')
        self.assertEqual(data.get('reply'), "To create a project on Tamweel, click 'Create Project' in the navigation bar.")
        self.assertIn('timestamp', data)

        # Only 1 call made to primary model (gemini-flash-lite-latest)
        mock_client.models.generate_content.assert_called_once()
        call_kwargs = mock_client.models.generate_content.call_args.kwargs
        self.assertEqual(call_kwargs['model'], 'gemini-flash-lite-latest')
        self.assertEqual(PRIMARY_MODEL, 'gemini-flash-lite-latest')
        self.assertEqual(FALLBACK_MODEL, 'gemini-flash-latest')

    # 4. 429/503 Recoverable Auto-Fallback Behavior
    @patch('chatbot.services.get_gemini_api_key', return_value='test-gemini-key')
    @patch('google.genai.Client')
    def test_primary_429_triggers_fallback_model_success(self, mock_client_cls, mock_get_key):
        """When primary model returns 429 RESOURCE_EXHAUSTED, fallback model is called once and succeeds."""
        from google.genai.errors import ClientError

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        fallback_response = MagicMock()
        fallback_response.text = "Here is the answer from the fallback model."

        # First call (primary Lite) raises 429, second call (fallback Flash) succeeds
        mock_client.models.generate_content.side_effect = [
            ClientError(429, {"error": {"code": 429, "message": "RESOURCE_EXHAUSTED"}}),
            fallback_response
        ]

        payload = json.dumps({'message': 'How do I donate?'})
        response = self.client.post(self.api_url, data=payload, content_type='application/json')

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get('status'), 'success')
        self.assertEqual(data.get('reply'), "Here is the answer from the fallback model.")

        # Exactly 2 calls made: first to PRIMARY_MODEL (Lite), second to FALLBACK_MODEL (Flash)
        self.assertEqual(mock_client.models.generate_content.call_count, 2)
        first_call_kwargs = mock_client.models.generate_content.call_args_list[0].kwargs
        second_call_kwargs = mock_client.models.generate_content.call_args_list[1].kwargs
        self.assertEqual(first_call_kwargs['model'], 'gemini-flash-lite-latest')
        self.assertEqual(second_call_kwargs['model'], 'gemini-flash-latest')

    @patch('chatbot.services.get_gemini_api_key', return_value='test-gemini-key')
    @patch('google.genai.Client')
    def test_primary_503_triggers_fallback_model_success(self, mock_client_cls, mock_get_key):
        """When primary Lite model returns 503 ServerError, fallback Flash model is called once and succeeds."""
        from google.genai.errors import ServerError

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        fallback_response = MagicMock()
        fallback_response.text = "Here is the answer from the fallback model after 503."

        # First call (primary Lite) raises 503 ServerError, second call (fallback Flash) succeeds
        mock_client.models.generate_content.side_effect = [
            ServerError(503, {"error": {"code": 503, "message": "Service Unavailable"}}),
            fallback_response
        ]

        payload = json.dumps({'message': 'How do I donate?'})
        response = self.client.post(self.api_url, data=payload, content_type='application/json')

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get('status'), 'success')
        self.assertEqual(data.get('reply'), "Here is the answer from the fallback model after 503.")

        # Exactly 2 calls made: first to Lite, second to Flash
        self.assertEqual(mock_client.models.generate_content.call_count, 2)
        first_call_kwargs = mock_client.models.generate_content.call_args_list[0].kwargs
        second_call_kwargs = mock_client.models.generate_content.call_args_list[1].kwargs
        self.assertEqual(first_call_kwargs['model'], 'gemini-flash-lite-latest')
        self.assertEqual(second_call_kwargs['model'], 'gemini-flash-latest')

    @patch('chatbot.services.get_gemini_api_key', return_value='test-gemini-key')
    @patch('google.genai.Client')
    def test_primary_429_and_fallback_failure_returns_friendly_fallback(self, mock_client_cls, mock_get_key):
        """When primary returns 429 and fallback model also fails, returns safe fallback message."""
        from google.genai.errors import ClientError

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        # Both primary and fallback raise 429
        mock_client.models.generate_content.side_effect = [
            ClientError(429, {"error": {"code": 429, "message": "RESOURCE_EXHAUSTED"}}),
            ClientError(429, {"error": {"code": 429, "message": "RESOURCE_EXHAUSTED"}})
        ]

        payload = json.dumps({'message': 'How do I donate?'})
        response = self.client.post(self.api_url, data=payload, content_type='application/json')

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get('status'), 'success')
        self.assertIn('temporarily unavailable', data.get('reply'))
        self.assertEqual(mock_client.models.generate_content.call_count, 2)

    # 5. Non-429 API Errors & Missing Key
    @patch('chatbot.services.get_gemini_api_key', return_value='')
    def test_missing_api_key_returns_friendly_fallback(self, mock_get_key):
        """When GEMINI_API_KEY is not configured, returns clean friendly message without crashing."""
        payload = json.dumps({'message': 'How do I donate?'})
        response = self.client.post(self.api_url, data=payload, content_type='application/json')

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get('status'), 'success')
        self.assertIn('temporarily unavailable', data.get('reply'))

    @patch('chatbot.services.get_gemini_api_key', return_value='test-key')
    @patch('google.genai.Client')
    def test_gemini_non_429_api_error_returns_friendly_fallback(self, mock_client_cls, mock_get_key):
        """When Gemini raises a non-429 error (e.g. 400 Bad Request), returns friendly fallback without retrying."""
        from google.genai.errors import ClientError
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.side_effect = ClientError(
            400,
            {"error": {"code": 400, "message": "INVALID_ARGUMENT"}}
        )

        payload = json.dumps({'message': 'How does OTP verification work?'})
        response = self.client.post(self.api_url, data=payload, content_type='application/json')

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get('status'), 'success')
        self.assertIn('temporarily unavailable', data.get('reply'))
        # Should NOT retry fallback for non-429/503 errors
        self.assertEqual(mock_client.models.generate_content.call_count, 1)

    # 6. Language Detection and Localization Helpers
    def test_arabic_text_detection_and_fallback(self):
        """Arabic queries correctly detect language and return Arabic fallback."""
        arabic_query = "إزاي أعمل حملة تبرع جديدة؟"
        self.assertTrue(is_arabic_text(arabic_query))
        self.assertEqual(get_fallback_message(arabic_query), DEFAULT_FALLBACK_MESSAGE_AR)

        english_query = "How to cancel a project?"
        self.assertFalse(is_arabic_text(english_query))
        self.assertEqual(get_fallback_message(english_query), DEFAULT_FALLBACK_MESSAGE_EN)

    # 7. Django Rate Limiting Tests (10 req/min)
    @patch('chatbot.services.get_gemini_api_key', return_value='test-key')
    @patch('google.genai.Client')
    def test_django_rate_limiting_triggers_after_10_requests(self, mock_client_cls, mock_get_key):
        """Making more than 10 requests within a minute triggers HTTP 429 from Django endpoint."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.text = "Test reply"
        mock_client.models.generate_content.return_value = mock_response

        payload = json.dumps({'message': 'Hello Tamweel'})

        # First 10 requests should succeed
        for i in range(10):
            res = self.client.post(self.api_url, data=payload, content_type='application/json')
            self.assertEqual(res.status_code, 200, f"Request {i+1} failed")

        # 11th request must return 429 Too Many Requests
        rate_limited_res = self.client.post(self.api_url, data=payload, content_type='application/json')
        self.assertEqual(rate_limited_res.status_code, 429)
        data = rate_limited_res.json()
        self.assertEqual(data.get('status'), 'error')
        self.assertIn('Too many requests', data.get('error', ''))

    # 8. Anonymous & Authenticated User Access
    @patch('chatbot.services.get_gemini_api_key', return_value='test-key')
    @patch('google.genai.Client')
    def test_anonymous_user_can_access_endpoint(self, mock_client_cls, mock_get_key):
        """Anonymous guests can query the chatbot API without being redirected to login."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.text = "Tamweel is an Egyptian crowdfunding platform."
        mock_client.models.generate_content.return_value = mock_response

        payload = json.dumps({'message': 'What is Tamweel?'})
        response = self.client.post(self.api_url, data=payload, content_type='application/json')
        self.assertEqual(response.status_code, 200)

    @patch('chatbot.services.get_gemini_api_key', return_value='test-key')
    @patch('google.genai.Client')
    def test_authenticated_user_can_access_endpoint(self, mock_client_cls, mock_get_key):
        """Authenticated users can query the chatbot API smoothly."""
        self.client.force_login(self.user)
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.text = "You can view your projects in your Profile page."
        mock_client.models.generate_content.return_value = mock_response

        payload = json.dumps({'message': 'Where can I see my projects?'})
        response = self.client.post(self.api_url, data=payload, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get('status'), 'success')

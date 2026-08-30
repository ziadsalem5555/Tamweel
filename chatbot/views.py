"""
API Views for Tamweel AI Chatbot.
Provides lightweight, stateless, rate-limited JSON endpoints.
"""

import json
from django.http import JsonResponse
from django.utils import timezone
from django.core.cache import cache
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt

from .services import generate_chat_response

# Rate limiting configuration: 10 requests per 60-second window
RATE_LIMIT_REQUESTS = 10
RATE_LIMIT_WINDOW_SECONDS = 60
MAX_MESSAGE_LENGTH = 500


def get_client_identifier(request) -> str:
    """Derive a unique client identifier using User ID, Session Key, or IP."""
    if request.user.is_authenticated:
        return f"user_{request.user.pk}"
    if request.session.session_key:
        return f"session_{request.session.session_key}"
    
    # Fallback to IP address
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
    return f"ip_{ip}"


def is_rate_limited(client_id: str) -> bool:
    """Check if the client has exceeded the allowed message rate limit."""
    cache_key = f"tamweel_chatbot_rate_{client_id}"
    current_count = cache.get(cache_key, 0)
    
    if current_count >= RATE_LIMIT_REQUESTS:
        return True
    
    if current_count == 0:
        cache.set(cache_key, 1, timeout=RATE_LIMIT_WINDOW_SECONDS)
    else:
        try:
            cache.incr(cache_key)
        except ValueError:
            cache.set(cache_key, current_count + 1, timeout=RATE_LIMIT_WINDOW_SECONDS)
            
    return False


@csrf_exempt
@require_http_methods(["POST"])
def chatbot_message_api(request):
    """
    POST /chatbot/api/message/
    Processes natural-language questions about the Tamweel crowdfunding platform.
    
    Input JSON:
        {"message": "How do I create a campaign?"}
        
    Output JSON (200):
        {
            "status": "success",
            "reply": "To create a project campaign on Tamweel...",
            "timestamp": "2026-08-27T08:00:00.000Z"
        }
    """
    # 1. Rate Limiting Check
    client_id = get_client_identifier(request)
    if is_rate_limited(client_id):
        return JsonResponse({
            'status': 'error',
            'error': 'Too many requests. Maximum 10 messages per minute allowed.'
        }, status=429)

    # 2. JSON Body Parsing
    try:
        if not request.body:
            return JsonResponse({
                'status': 'error',
                'error': 'Request body cannot be empty.'
            }, status=400)
        data = json.loads(request.body.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({
            'status': 'error',
            'error': 'Invalid JSON format in request body.'
        }, status=400)

    if not isinstance(data, dict):
        return JsonResponse({
            'status': 'error',
            'error': 'Request payload must be a JSON object.'
        }, status=400)

    # 3. Message Validation
    raw_message = data.get('message')
    if raw_message is None or not isinstance(raw_message, str):
        return JsonResponse({
            'status': 'error',
            'error': 'The "message" field is required and must be a string.'
        }, status=400)

    message = raw_message.strip()
    if not message:
        return JsonResponse({
            'status': 'error',
            'error': 'Message cannot be empty.'
        }, status=400)

    if len(message) > MAX_MESSAGE_LENGTH:
        return JsonResponse({
            'status': 'error',
            'error': f'Message exceeds maximum length of {MAX_MESSAGE_LENGTH} characters.'
        }, status=400)

    # 4. Generate AI Response via Service Layer
    result = generate_chat_response(message)

    # 5. Return Clean JSON Response
    return JsonResponse({
        'status': 'success',
        'reply': result['reply'],
        'timestamp': timezone.now().isoformat()
    }, status=200)

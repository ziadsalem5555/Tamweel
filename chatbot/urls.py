"""
URL configuration for the Tamweel AI Chatbot app.
"""

from django.urls import path
from .views import chatbot_message_api

app_name = 'chatbot'

urlpatterns = [
    path('api/message/', chatbot_message_api, name='message_api'),
]

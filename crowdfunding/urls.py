"""
URL configuration for crowdfunding project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from projects.views import home_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home_view, name='home'),
    path('accounts/', include('accounts.urls')),
    path('projects/', include('projects.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Custom admin site branding
admin.site.site_header = "CrowdFund Egypt Administration"
admin.site.site_title = "CrowdFund Egypt Admin Portal"
admin.site.index_title = "Welcome to CrowdFund Egypt Management"

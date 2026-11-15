"""
URL configuration for Gigframe project.
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, include
from users.views import DashboardRouter

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', DashboardRouter.as_view(), name='home'),
    path('', include('support.urls')),  # Contact & About pages
    path('auth/', include('users.urls')),
    path('gigs/', include('gigs.urls')),
    path('jobs/', include('jobs.urls')),
    path('notifications/', include('notifications.urls')),
    path('messages/', include('chat.urls')),
    path('contracts/', include('contracts.urls')),
    path('control-panel/', include('admin_panel.urls')),  # custom-built Admin Interface

    path('auth/password-reset/',
         auth_views.PasswordResetView.as_view(template_name='users/password_reset.html'),
         name='password_reset'),
    path('auth/password-reset/done/',
         auth_views.PasswordResetDoneView.as_view(template_name='users/password_reset_done.html'),
         name='password_reset_done'),
    path('auth/reset/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(template_name='users/password_reset_confirm.html'),
         name='password_reset_confirm'),
    path('auth/reset/done/',
         auth_views.PasswordResetCompleteView.as_view(template_name='users/password_reset_complete.html'),
         name='password_reset_complete'),

]

# Serve user-uploaded media files (chat attachments, contract deliverables, profile pictures) in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
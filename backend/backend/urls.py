"""
URL configuration for backend project.
"""

from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy
from django.views.generic.base import RedirectView
from tasks import views


urlpatterns = [
    path(
        'admin/password_reset/',
        RedirectView.as_view(
            pattern_name='password-reset',
            permanent=False
        ),
        name='admin-password-reset-redirect',
    ),

    path('admin/', admin.site.urls),

    path('', views.login_page, name='login'),

    path('login/', views.login_page, name='login-page'),

    path(
        'login-page/<path:filename>',
        views.login_asset,
        name='login-asset'
    ),

    path(
        'api/login/',
        views.login_api,
        name='login-api'
    ),

    path(
        'api/logout/',
        views.logout_api,
        name='logout-api'
    ),

    path(
        'api/session/',
        views.session_api,
        name='session-api'
    ),

    path(
        'dashboard/',
        views.dashboard,
        name='dashboard'
    ),

    # Add Income
    path(
        'income/add/',
        views.add_income,
        name='add_income'
    ),

    path(
        'password-reset/',
        auth_views.PasswordResetView.as_view(
            template_name='tasks/password_reset/form.html',
            email_template_name='tasks/password_reset/email.txt',
            subject_template_name='tasks/password_reset/subject.txt',
            success_url=reverse_lazy('password-reset-done'),
        ),
        name='password-reset',
    ),

    path(
        'password-reset/done/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='tasks/password_reset/done.html',
        ),
        name='password-reset-done',
    ),

    path(
        'reset/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='tasks/password_reset/confirm.html',
            success_url=reverse_lazy('password-reset-complete'),
        ),
        name='password-reset-confirm',
    ),

    path(
        'reset/done/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='tasks/password_reset/complete.html',
        ),
        name='password-reset-complete',
    ),
]
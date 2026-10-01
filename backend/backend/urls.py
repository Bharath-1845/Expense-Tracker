"""
URL configuration for backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy
from django.views.generic.base import RedirectView
from tasks import views

urlpatterns = [
    path(
        'admin/password_reset/',
        RedirectView.as_view(pattern_name='password-reset', permanent=False),
        name='admin-password-reset-redirect',
    ),
    path('admin/', admin.site.urls),
    path('', views.login_page, name='login'),
    path('login/', views.login_page, name='login-page'),
    path('login-page/<path:filename>', views.login_asset, name='login-asset'),
    path('api/login/', views.login_api, name='login-api'),
    path('api/logout/', views.logout_api, name='logout-api'),
    path('api/session/', views.session_api, name='session-api'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path(
    'expense-summary/',
    views.expense_summary,
    name='expense-summary'
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

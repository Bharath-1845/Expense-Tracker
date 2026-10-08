from django.urls import path
from . import views


urlpatterns = [
    path(
        'monthly-spending/',
        views.monthly_spending_analysis,
        name='monthly_spending_analysis'
    ),
]
import json

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST
from django.db.models import Sum
from .models import Transaction


DASHBOARD_PAGE = settings.BASE_DIR / 'login-page' / 'dashboard.html'


@require_GET
@ensure_csrf_cookie
def login_page(request):
	if request.user.is_authenticated:
		return redirect('dashboard')
	return render(request, 'registration/login.html')


@require_GET
def login_asset(request, filename):
	if filename not in {'style.css', 'script.js'}:
		return JsonResponse({'error': 'Not found.'}, status=404)
	asset_root = (settings.BASE_DIR / 'login-page').resolve()
	asset_path = (asset_root / filename).resolve()
	if asset_root not in asset_path.parents or not asset_path.is_file():
		return JsonResponse({'error': 'Not found.'}, status=404)
	return FileResponse(asset_path.open('rb'))


@require_POST
def login_api(request):
	try:
		payload = json.loads(request.body)
	except (json.JSONDecodeError, UnicodeDecodeError):
		return JsonResponse({'error': 'Invalid request data.'}, status=400)

	if not isinstance(payload, dict):
		return JsonResponse({'error': 'Invalid request data.'}, status=400)

	email = payload.get('email', '')
	password = payload.get('password', '')
	if not isinstance(email, str) or not isinstance(password, str):
		return JsonResponse({'error': 'Email and password are required.'}, status=400)

	email = email.strip()
	if not email or not password:
		return JsonResponse({'error': 'Email and password are required.'}, status=400)

	user_model = get_user_model()
	matching_user = user_model.objects.filter(email__iexact=email).first()
	username = matching_user.get_username() if matching_user else email
	user = authenticate(request, username=username, password=password)

	if user is None:
		return JsonResponse({'error': 'Invalid email or password.'}, status=401)

	login(request, user)
	request.session.set_expiry(1209600 if payload.get('remember') is True else 0)
	return JsonResponse({'message': 'Login successful.', 'redirect': '/dashboard/'})


@require_POST
def logout_api(request):
	logout(request)
	return JsonResponse({'message': 'You have been logged out.'})


@require_GET
@login_required(login_url='/')
def dashboard(request):
	return FileResponse(DASHBOARD_PAGE.open('rb'))


@require_GET
@login_required(login_url='/')
def session_api(request):
	return JsonResponse({'username': request.user.get_username(), 'email': request.user.email})



@login_required(login_url='/')
def expense_summary(request):
    total_income = Transaction.objects.filter(
        user=request.user,
        transaction_type='income'
    ).aggregate(
        total=Sum('amount')
    )['total'] or 0

    total_expenses = Transaction.objects.filter(
        user=request.user,
        transaction_type='expense'
    ).aggregate(
        total=Sum('amount')
    )['total'] or 0

    remaining_balance = total_income - total_expenses

    return render(
        request,
        'tasks/expense_summary.html',
        {
            'total_income': total_income,
            'total_expenses': total_expenses,
            'remaining_balance': remaining_balance,
        }
    )

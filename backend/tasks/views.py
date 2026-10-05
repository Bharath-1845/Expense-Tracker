from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import json

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.http import FileResponse, JsonResponse
from django.shortcuts import redirect
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from .models import MonthlyBudget, Expense


LOGIN_PAGE = settings.BASE_DIR / 'login-page' / 'index.html'
DASHBOARD_PAGE = settings.BASE_DIR / 'login-page' / 'dashboard.html'


@require_GET
@ensure_csrf_cookie
def login_page(request):
	if request.user.is_authenticated:
		return redirect('dashboard')
	return FileResponse(LOGIN_PAGE.open('rb'))


@require_GET
def login_asset(request, filename):
	if filename not in {'style.css', 'script.js', 'dashboard.js'}:
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
@ensure_csrf_cookie
def dashboard(request):
	return FileResponse(DASHBOARD_PAGE.open('rb'))


@require_GET
@login_required(login_url='/')
def session_api(request):
	return JsonResponse({'username': request.user.get_username(), 'email': request.user.email})


@require_http_methods(['GET', 'POST'])
def budget_api(request):
	if not request.user.is_authenticated:
		return JsonResponse({'error': 'Authentication required.'}, status=401)

	today = date.today()

	if request.method == 'GET':
		try:
			year = int(request.GET.get('year', today.year))
			month = int(request.GET.get('month', today.month))
			if not (1 <= month <= 12 and 1900 <= year <= 2200):
				return JsonResponse({'error': 'Invalid year or month.'}, status=400)
		except (ValueError, TypeError):
			return JsonResponse({'error': 'Invalid year or month.'}, status=400)

		budget_obj = MonthlyBudget.objects.filter(
			user=request.user, year=year, month=month
		).first()
		budget_amount = budget_obj.amount if budget_obj else Decimal('0.00')

		expense_qs = Expense.objects.filter(
			user=request.user,
			date__year=year,
			date__month=month
		)
		total_expenses = expense_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
		remaining_balance = budget_amount - total_expenses
		expenses_count = expense_qs.count()

		if budget_amount > Decimal('0.00'):
			percentage_used = round(float((total_expenses / budget_amount) * 100), 1)
		else:
			percentage_used = 0.0

		return JsonResponse({
			'year': year,
			'month': month,
			'budget': float(budget_amount),
			'total_expenses': float(total_expenses),
			'remaining_balance': float(remaining_balance),
			'percentage_used': percentage_used,
			'is_over_budget': total_expenses > budget_amount and budget_amount > Decimal('0.00'),
			'expenses_count': expenses_count,
		})

	# POST request: set/update monthly budget
	try:
		payload = json.loads(request.body)
	except (json.JSONDecodeError, UnicodeDecodeError):
		return JsonResponse({'error': 'Invalid request data.'}, status=400)

	if not isinstance(payload, dict):
		return JsonResponse({'error': 'Invalid request data.'}, status=400)

	try:
		year = int(payload.get('year', today.year))
		month = int(payload.get('month', today.month))
		if not (1 <= month <= 12 and 1900 <= year <= 2200):
			return JsonResponse({'error': 'Invalid year or month.'}, status=400)
	except (ValueError, TypeError):
		return JsonResponse({'error': 'Invalid year or month.'}, status=400)

	raw_amount = payload.get('amount')
	if raw_amount is None:
		return JsonResponse({'error': 'Budget amount is required.'}, status=400)

	try:
		amount = Decimal(str(raw_amount))
		if amount < Decimal('0.00'):
			return JsonResponse({'error': 'Budget amount cannot be negative.'}, status=400)
	except (InvalidOperation, TypeError, ValueError):
		return JsonResponse({'error': 'Invalid budget amount.'}, status=400)

	budget_obj, _ = MonthlyBudget.objects.update_or_create(
		user=request.user,
		year=year,
		month=month,
		defaults={'amount': amount}
	)

	expense_qs = Expense.objects.filter(
		user=request.user,
		date__year=year,
		date__month=month
	)
	total_expenses = expense_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
	remaining_balance = amount - total_expenses
	if amount > Decimal('0.00'):
		percentage_used = round(float((total_expenses / amount) * 100), 1)
	else:
		percentage_used = 0.0

	return JsonResponse({
		'message': 'Monthly budget updated successfully.',
		'year': year,
		'month': month,
		'budget': float(amount),
		'total_expenses': float(total_expenses),
		'remaining_balance': float(remaining_balance),
		'percentage_used': percentage_used,
		'is_over_budget': total_expenses > amount and amount > Decimal('0.00'),
		'expenses_count': expense_qs.count(),
	})


@require_http_methods(['GET', 'POST'])
def expenses_api(request):
	if not request.user.is_authenticated:
		return JsonResponse({'error': 'Authentication required.'}, status=401)

	today = date.today()

	if request.method == 'GET':
		qs = Expense.objects.filter(user=request.user)

		year_param = request.GET.get('year')
		month_param = request.GET.get('month')
		if year_param and month_param:
			try:
				year = int(year_param)
				month = int(month_param)
				if 1 <= month <= 12:
					qs = qs.filter(date__year=year, date__month=month)
			except (ValueError, TypeError):
				pass

		category_param = request.GET.get('category')
		if category_param and category_param != 'All':
			qs = qs.filter(category=category_param)

		search_param = request.GET.get('search')
		if search_param:
			qs = qs.filter(title__icontains=search_param.strip())

		expenses_list = [
			{
				'id': exp.id,
				'title': exp.title,
				'amount': float(exp.amount),
				'category': exp.category,
				'date': exp.date.strftime('%Y-%m-%d'),
				'notes': exp.notes,
			}
			for exp in qs
		]

		return JsonResponse({'expenses': expenses_list})

	# POST request: create new expense
	try:
		payload = json.loads(request.body)
	except (json.JSONDecodeError, UnicodeDecodeError):
		return JsonResponse({'error': 'Invalid request data.'}, status=400)

	if not isinstance(payload, dict):
		return JsonResponse({'error': 'Invalid request data.'}, status=400)

	title = str(payload.get('title', '')).strip()
	if not title:
		return JsonResponse({'error': 'Expense description is required.'}, status=400)
	if len(title) > 200:
		return JsonResponse({'error': 'Expense description is too long (max 200 characters).'}, status=400)

	raw_amount = payload.get('amount')
	if raw_amount is None:
		return JsonResponse({'error': 'Expense amount is required.'}, status=400)

	try:
		amount = Decimal(str(raw_amount))
		if amount <= Decimal('0.00'):
			return JsonResponse({'error': 'Expense amount must be greater than zero.'}, status=400)
	except (InvalidOperation, TypeError, ValueError):
		return JsonResponse({'error': 'Invalid expense amount.'}, status=400)

	category = str(payload.get('category', 'Other')).strip()
	if not category:
		category = 'Other'

	date_str = payload.get('date')
	if not date_str:
		expense_date = today
	else:
		try:
			expense_date = datetime.strptime(str(date_str), '%Y-%m-%d').date()
		except ValueError:
			return JsonResponse({'error': 'Invalid date format. Use YYYY-MM-DD.'}, status=400)

	notes = str(payload.get('notes', '')).strip()

	expense = Expense.objects.create(
		user=request.user,
		title=title,
		amount=amount,
		category=category,
		date=expense_date,
		notes=notes
	)

	return JsonResponse({
		'message': 'Expense added successfully.',
		'expense': {
			'id': expense.id,
			'title': expense.title,
			'amount': float(expense.amount),
			'category': expense.category,
			'date': expense.date.strftime('%Y-%m-%d'),
			'notes': expense.notes,
		}
	}, status=201)


@require_http_methods(['GET', 'PUT', 'PATCH', 'POST', 'DELETE'])
def expense_detail_api(request, expense_id):
	if not request.user.is_authenticated:
		return JsonResponse({'error': 'Authentication required.'}, status=401)

	expense = Expense.objects.filter(id=expense_id, user=request.user).first()
	if not expense:
		return JsonResponse({'error': 'Expense not found.'}, status=404)

	if request.method == 'GET':
		return JsonResponse({
			'expense': {
				'id': expense.id,
				'title': expense.title,
				'amount': float(expense.amount),
				'category': expense.category,
				'date': expense.date.strftime('%Y-%m-%d'),
				'notes': expense.notes,
			}
		})

	if request.method == 'DELETE':
		expense.delete()
		return JsonResponse({'message': 'Expense deleted successfully.'})

	# Handle PUT, PATCH, or POST (for editing/updating)
	try:
		payload = json.loads(request.body)
	except (json.JSONDecodeError, UnicodeDecodeError):
		return JsonResponse({'error': 'Invalid request data.'}, status=400)

	if not isinstance(payload, dict):
		return JsonResponse({'error': 'Invalid request data.'}, status=400)

	if request.method == 'POST' and payload.get('action') == 'delete':
		expense.delete()
		return JsonResponse({'message': 'Expense deleted successfully.'})

	title = str(payload.get('title', expense.title)).strip()
	if not title:
		return JsonResponse({'error': 'Expense description is required.'}, status=400)
	if len(title) > 200:
		return JsonResponse({'error': 'Expense description is too long (max 200 characters).'}, status=400)

	raw_amount = payload.get('amount')
	if raw_amount is None:
		amount = expense.amount
	else:
		try:
			amount = Decimal(str(raw_amount))
			if amount <= Decimal('0.00'):
				return JsonResponse({'error': 'Expense amount must be greater than zero.'}, status=400)
		except (InvalidOperation, TypeError, ValueError):
			return JsonResponse({'error': 'Invalid expense amount.'}, status=400)

	category = str(payload.get('category', expense.category)).strip()
	if not category:
		category = 'Other'

	date_str = payload.get('date')
	if date_str:
		try:
			expense_date = datetime.strptime(str(date_str), '%Y-%m-%d').date()
		except ValueError:
			return JsonResponse({'error': 'Invalid date format. Use YYYY-MM-DD.'}, status=400)
	else:
		expense_date = expense.date

	notes = str(payload.get('notes', expense.notes)).strip()

	expense.title = title
	expense.amount = amount
	expense.category = category
	expense.date = expense_date
	expense.notes = notes
	expense.save()

	return JsonResponse({
		'message': 'Expense updated successfully.',
		'expense': {
			'id': expense.id,
			'title': expense.title,
			'amount': float(expense.amount),
			'category': expense.category,
			'date': expense.date.strftime('%Y-%m-%d'),
			'notes': expense.notes,
		}
	})



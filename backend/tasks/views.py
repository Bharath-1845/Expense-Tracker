from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import json

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Q
from django.http import FileResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .models import MonthlyBudget, Expense, Income


LOGIN_PAGE = settings.BASE_DIR / 'login-page' / 'index.html'
DASHBOARD_PAGE = settings.BASE_DIR / 'login-page' / 'dashboard.html'

LEDGER_TEMPLATES = {
    'dashboard': 'ledger/dashboard.html',
    'expense_add': 'ledger/expense_add.html',
    'expenses': 'ledger/expenses.html',
    'income_add': 'ledger/income_add.html',
    'incomes': 'ledger/incomes.html',
    'reports': 'ledger/reports.html',
}

EXPENSE_CATEGORIES = [
    'Food',
    'Food & Dining',
    'Transportation',
    'Utilities & Bills',
    'Shopping',
    'Entertainment',
    'Healthcare',
    'Education',
    'Other',
]


@require_GET
@ensure_csrf_cookie
def login_page(request):
	if request.user.is_authenticated:
		return redirect('dashboard')
	login_template = settings.BASE_DIR / 'tasks' / 'templates' / 'registration' / 'login.html'
	if login_template.is_file():
		return render(request, 'registration/login.html')
	if LOGIN_PAGE.is_file():
		return FileResponse(LOGIN_PAGE.open('rb'))
	return render(request, 'registration/login.html')


@require_GET
def login_asset(request, filename):
	if filename not in {'style.css', 'script.js', 'dashboard.js', 'ledger.js', 'login.js'}:
		return JsonResponse({'error': 'Not found.'}, status=404)
	asset_root = (settings.BASE_DIR / 'login-page').resolve()
	asset_path = (asset_root / filename).resolve()
	if asset_root in asset_path.parents and asset_path.is_file():
		return FileResponse(asset_path.open('rb'))

	static_root = (settings.BASE_DIR / 'tasks' / 'static' / 'tasks').resolve()
	static_path = (static_root / filename).resolve()
	if static_root in static_path.parents and static_path.is_file():
		return FileResponse(static_path.open('rb'))

	return JsonResponse({'error': 'Not found.'}, status=404)


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
	if DASHBOARD_PAGE.is_file():
		return FileResponse(DASHBOARD_PAGE.open('rb'))
	return render(request, 'ledger/dashboard.html', {'active_page': 'dashboard'})


@require_GET
@login_required(login_url='/')
def session_api(request):
	return JsonResponse({'username': request.user.get_username(), 'email': request.user.email})


def _read_json_payload(request):
	try:
		payload = json.loads(request.body)
	except (json.JSONDecodeError, UnicodeDecodeError):
		return None, {'error': 'Invalid request data.'}
	if not isinstance(payload, dict):
		return None, {'error': 'Invalid request data.'}
	return payload, None


def _serialize_expense(expense):
	return {
		'id': expense.pk,
		'title': expense.title or expense.description or expense.category,
		'category': expense.category,
		'amount': format(expense.amount, '.2f'),
		'date': expense.date.isoformat(),
		'description': expense.description or expense.notes or expense.title,
		'notes': expense.notes or expense.description,
	}


def _serialize_income(income):
	return {
		'id': income.pk,
		'source': income.source,
		'amount': format(income.amount, '.2f'),
		'date': income.date.isoformat(),
		'description': income.description,
	}


@ensure_csrf_cookie
@require_GET
def ledger_page(request, page='dashboard'):
	template = LEDGER_TEMPLATES.get(page)
	if template is None:
		return JsonResponse({'error': 'Not found.'}, status=404)
	return render(request, template, {'active_page': page})


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
	today = date.today()

	if request.method == 'GET':
		if request.user.is_authenticated:
			qs = Expense.objects.filter(Q(user=request.user) | Q(user__isnull=True))
		else:
			qs = Expense.objects.all()

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
			qs = qs.filter(
				Q(title__icontains=search_param.strip()) |
				Q(description__icontains=search_param.strip()) |
				Q(notes__icontains=search_param.strip())
			)

		categories = set(EXPENSE_CATEGORIES)
		categories.update(Expense.objects.values_list('category', flat=True).distinct())

		expenses_list = [_serialize_expense(exp) for exp in qs]

		return JsonResponse({
			'expenses': expenses_list,
			'categories': sorted(categories, key=str.casefold),
		})

	# POST request: create new expense
	payload, error = _read_json_payload(request)
	if error:
		return JsonResponse(error, status=400)

	errors = {}
	title = str(payload.get('title', '')).strip()
	description = str(payload.get('description', '')).strip()
	category = str(payload.get('category', '')).strip()

	if not category:
		if title:
			category = 'Other'
		else:
			errors['category'] = 'Enter a category.'
	elif len(category) > 50:
		errors['category'] = 'Category must be 50 characters or fewer.'

	if not title and description:
		title = description[:200]
	elif not title and not description:
		title = category

	raw_amount = payload.get('amount')
	if raw_amount is None:
		errors['amount'] = 'Expense amount is required.'
		amount = None
	else:
		try:
			if isinstance(raw_amount, bool):
				raise InvalidOperation
			amount = Decimal(str(raw_amount))
			if amount <= Decimal('0.00') or not amount.is_finite() or amount > Decimal('99999999.99'):
				raise InvalidOperation
			if amount.as_tuple().exponent < -2:
				raise InvalidOperation
		except (InvalidOperation, TypeError, ValueError):
			errors['amount'] = 'Enter an amount greater than zero with at most two decimal places.'
			amount = None

	date_val = payload.get('date')
	if not date_val:
		expense_date = today
	elif isinstance(date_val, datetime):
		expense_date = date_val.date()
	elif isinstance(date_val, date):
		expense_date = date_val
	else:
		date_str = str(date_val).strip()
		try:
			if 'T' in date_str:
				expense_date = datetime.fromisoformat(date_str.replace('Z', '+00:00')).date()
			else:
				expense_date = datetime.strptime(date_str, '%Y-%m-%d').date()
		except (ValueError, TypeError):
			errors['date'] = 'Enter a valid date.'
			expense_date = None

	notes = str(payload.get('notes', '')).strip()
	if not description and notes:
		description = notes

	if errors:
		first_err = next(iter(errors.values()))
		return JsonResponse({'error': first_err, 'errors': errors}, status=400)

	user = request.user if request.user.is_authenticated else None

	try:
		expense = Expense.objects.create(
			user=user,
			title=title,
			amount=amount,
			category=category,
			date=expense_date,
			description=description,
			notes=notes
		)
	except Exception as exc:
		return JsonResponse({'error': f'Failed to add expense: {str(exc)}'}, status=500)

	return JsonResponse({
		'message': 'Expense added successfully.',
		'expense': _serialize_expense(expense)
	}, status=201)


@require_http_methods(['GET', 'PUT', 'PATCH', 'POST', 'DELETE'])
def expense_detail_api(request, expense_id):
	expense = get_object_or_404(Expense, pk=expense_id)

	# If expense belongs to a user and authenticated user is different, deny access
	if request.user.is_authenticated and expense.user and expense.user != request.user:
		return JsonResponse({'error': 'Expense not found.'}, status=404)

	if request.method == 'GET':
		return JsonResponse({'expense': _serialize_expense(expense)})

	if request.method == 'DELETE':
		expense.delete()
		return JsonResponse({'message': 'Expense deleted.'})

	# Handle PUT, PATCH, or POST (for editing/updating)
	payload, error = _read_json_payload(request)
	if error:
		return JsonResponse(error, status=400)

	if request.method == 'POST' and payload.get('action') == 'delete':
		expense.delete()
		return JsonResponse({'message': 'Expense deleted.'})

	errors = {}
	title = payload.get('title')
	category = payload.get('category')
	description = payload.get('description')
	notes = payload.get('notes')

	if 'title' in payload:
		title_str = str(title).strip()
		if not title_str:
			errors['title'] = 'Expense description is required.'
		elif len(title_str) > 200:
			errors['title'] = 'Expense description is too long (max 200 characters).'
		else:
			expense.title = title_str

	if 'category' in payload:
		cat_str = str(category).strip()
		if not cat_str:
			errors['category'] = 'Enter a category.'
		elif len(cat_str) > 50:
			errors['category'] = 'Category must be 50 characters or fewer.'
		else:
			expense.category = cat_str

	if 'description' in payload:
		desc_str = str(description).strip()
		if len(desc_str) > 1000:
			errors['description'] = 'Description must be 1000 characters or fewer.'
		else:
			expense.description = desc_str

	if 'notes' in payload:
		expense.notes = str(notes).strip()

	if 'amount' in payload:
		raw_amount = payload['amount']
		try:
			if isinstance(raw_amount, bool):
				raise InvalidOperation
			amt = Decimal(str(raw_amount))
			if amt <= Decimal('0.00') or not amt.is_finite() or amt > Decimal('99999999.99'):
				raise InvalidOperation
			if amt.as_tuple().exponent < -2:
				raise InvalidOperation
			expense.amount = amt
		except (InvalidOperation, TypeError, ValueError):
			errors['amount'] = 'Enter an amount greater than zero with at most two decimal places.'

	if 'date' in payload:
		date_val = payload['date']
		if isinstance(date_val, datetime):
			expense.date = date_val.date()
		elif isinstance(date_val, date):
			expense.date = date_val
		else:
			d_str = str(date_val).strip()
			try:
				if 'T' in d_str:
					expense.date = datetime.fromisoformat(d_str.replace('Z', '+00:00')).date()
				else:
					expense.date = datetime.strptime(d_str, '%Y-%m-%d').date()
			except (ValueError, TypeError):
				errors['date'] = 'Enter a valid date.'

	if errors:
		first_err = next(iter(errors.values()))
		return JsonResponse({'error': first_err, 'errors': errors}, status=400)

	expense.save()

	return JsonResponse({
		'message': 'Expense updated successfully.',
		'expense': _serialize_expense(expense)
	})


@require_http_methods(['GET', 'POST'])
def incomes_api(request):
	if request.method == 'GET':
		incomes = Income.objects.all()
		sources = sorted(set(Income.objects.values_list('source', flat=True)), key=str.casefold)
		return JsonResponse({
			'incomes': [_serialize_income(income) for income in incomes],
			'sources': sources,
		})

	payload, error = _read_json_payload(request)
	if error:
		return JsonResponse(error, status=400)

	errors = {}
	source = payload.get('source')
	if not isinstance(source, str) or not source.strip():
		errors['source'] = 'Enter a source.'
	elif len(source.strip()) > 50:
		errors['source'] = 'Source must be 50 characters or fewer.'

	raw_amount = payload.get('amount')
	try:
		if isinstance(raw_amount, bool):
			raise InvalidOperation
		amount = Decimal(str(raw_amount))
		if amount <= Decimal('0.00') or not amount.is_finite() or amount > Decimal('99999999.99'):
			raise InvalidOperation
		if amount.as_tuple().exponent < -2:
			raise InvalidOperation
	except (InvalidOperation, TypeError, ValueError):
		errors['amount'] = 'Enter an amount greater than zero with at most two decimal places.'
		amount = None

	date_val = payload.get('date')
	try:
		if isinstance(date_val, date):
			parsed_date = date_val
		elif isinstance(date_val, str):
			parsed_date = date.fromisoformat(date_val)
		else:
			raise ValueError
	except (TypeError, ValueError):
		errors['date'] = 'Enter a valid date.'
		parsed_date = None

	description = payload.get('description', '')
	if not isinstance(description, str):
		errors['description'] = 'Description must be text.'
	elif len(description) > 1000:
		errors['description'] = 'Description must be 1000 characters or fewer.'

	if errors:
		first_err = next(iter(errors.values()))
		return JsonResponse({'error': first_err, 'errors': errors}, status=400)

	income = Income.objects.create(
		source=source.strip(),
		amount=amount,
		date=parsed_date,
		description=description
	)
	return JsonResponse({'income': _serialize_income(income)}, status=201)


@require_http_methods(['GET', 'PATCH', 'DELETE'])
def income_detail_api(request, income_id):
	income = get_object_or_404(Income, pk=income_id)
	if request.method == 'GET':
		return JsonResponse({'income': _serialize_income(income)})
	if request.method == 'DELETE':
		income.delete()
		return JsonResponse({'message': 'Income deleted.'})

	payload, error = _read_json_payload(request)
	if error:
		return JsonResponse(error, status=400)

	errors = {}
	if 'source' in payload:
		source = payload['source']
		if not isinstance(source, str) or not source.strip():
			errors['source'] = 'Enter a source.'
		elif len(source.strip()) > 50:
			errors['source'] = 'Source must be 50 characters or fewer.'
		else:
			income.source = source.strip()

	if 'amount' in payload:
		try:
			raw_amount = payload['amount']
			if isinstance(raw_amount, bool):
				raise InvalidOperation
			amount = Decimal(str(raw_amount))
			if amount <= Decimal('0.00') or not amount.is_finite() or amount > Decimal('99999999.99'):
				raise InvalidOperation
			if amount.as_tuple().exponent < -2:
				raise InvalidOperation
			income.amount = amount
		except (InvalidOperation, TypeError, ValueError):
			errors['amount'] = 'Enter an amount greater than zero with at most two decimal places.'

	if 'date' in payload:
		try:
			date_val = payload['date']
			if isinstance(date_val, date):
				income.date = date_val
			elif isinstance(date_val, str):
				income.date = date.fromisoformat(date_val)
			else:
				raise ValueError
		except (TypeError, ValueError):
			errors['date'] = 'Enter a valid date.'

	if 'description' in payload:
		desc = payload['description']
		if not isinstance(desc, str):
			errors['description'] = 'Description must be text.'
		elif len(desc) > 1000:
			errors['description'] = 'Description must be 1000 characters or fewer.'
		else:
			income.description = desc

	if errors:
		first_err = next(iter(errors.values()))
		return JsonResponse({'error': first_err, 'errors': errors}, status=400)

	income.save()
	return JsonResponse({'income': _serialize_income(income)})

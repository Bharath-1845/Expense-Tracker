import json
from datetime import date
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods, require_POST
#from django.views.generic.base import RedirectView
from .models import Expense, Income


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

@require_GET
@ensure_csrf_cookie
def login_page(request):
	if request.user.is_authenticated:
		return redirect('dashboard')
	return render(request, 'registration/login.html')


@require_GET
def login_asset(request, filename):
	if filename not in {'style.css', 'script.js', 'ledger.js'}:
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


def _validate_transaction_payload(payload, instance=None, label_field='category'):
	allowed_fields = {label_field, 'amount', 'date', 'description'}
	if set(payload) - allowed_fields:
		return None, {'error': 'Unsupported transaction field.'}

	values = {
		label_field: getattr(instance, label_field) if instance else None,
		'amount': instance.amount if instance else None,
		'date': instance.date if instance else None,
		'description': instance.description if instance else '',
	}
	values.update(payload)
	errors = {}

	label = values[label_field]
	if not isinstance(label, str) or not label.strip():
		errors[label_field] = f'Enter a {label_field}.'
	elif len(label.strip()) > 50:
		errors[label_field] = f'{label_field.title()} must be 50 characters or fewer.'
	else:
		values[label_field] = label.strip()

	try:
		if isinstance(values['amount'], bool):
			raise InvalidOperation
		amount = Decimal(str(values['amount']))
		if not amount.is_finite() or amount <= 0 or amount > Decimal('99999999.99'):
			raise InvalidOperation
		if amount.as_tuple().exponent < -2:
			raise InvalidOperation
		values['amount'] = amount
	except (InvalidOperation, TypeError, ValueError):
		errors['amount'] = 'Enter an amount greater than zero with at most two decimal places.'

	try:
		if isinstance(values['date'], date):
			parsed_date = values['date']
		elif isinstance(values['date'], str):
			parsed_date = date.fromisoformat(values['date'])
		else:
			raise ValueError
		values['date'] = parsed_date
	except (TypeError, ValueError):
		errors['date'] = 'Enter a valid date.'

	description = values['description']
	if not isinstance(description, str):
		errors['description'] = 'Description must be text.'
	elif len(description) > 1000:
		errors['description'] = 'Description must be 1000 characters or fewer.'

	if errors:
		return None, errors
	return values, None


def _validate_expense_payload(payload, instance=None):
	return _validate_transaction_payload(payload, instance)


def _validate_income_payload(payload, instance=None):
	return _validate_transaction_payload(payload, instance, label_field='source')


def _serialize_expense(expense):
	return {
		'id': expense.pk,
		'category': expense.category,
		'amount': format(expense.amount, '.2f'),
		'date': expense.date.isoformat(),
		'description': expense.description,
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
def expenses_api(request):
	if request.method == 'GET':
		expenses = Expense.objects.all()
		categories = set(EXPENSE_CATEGORIES)
		categories.update(Expense.objects.values_list('category', flat=True).distinct())
		return JsonResponse({
			'expenses': [_serialize_expense(expense) for expense in expenses],
			'categories': sorted(categories, key=str.casefold),
		})

	payload, error = _read_json_payload(request)
	if error:
		return JsonResponse(error, status=400)
	values, errors = _validate_expense_payload(payload)
	if errors:
		return JsonResponse({'errors': errors}, status=400)
	expense = Expense.objects.create(**values)
	return JsonResponse({'expense': _serialize_expense(expense)}, status=201)


@require_http_methods(['GET', 'PATCH', 'DELETE'])
def expense_detail_api(request, expense_id):
	expense = get_object_or_404(Expense, pk=expense_id)
	if request.method == 'GET':
		return JsonResponse({'expense': _serialize_expense(expense)})
	if request.method == 'DELETE':
		expense.delete()
		return JsonResponse({'message': 'Expense deleted.'})

	payload, error = _read_json_payload(request)
	if error:
		return JsonResponse(error, status=400)
	values, errors = _validate_expense_payload(payload, instance=expense)
	if errors:
		return JsonResponse({'errors': errors}, status=400)
	for field, value in values.items():
		setattr(expense, field, value)
	expense.save(update_fields=[*values.keys()])
	return JsonResponse({'expense': _serialize_expense(expense)})


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
	values, errors = _validate_income_payload(payload)
	if errors:
		return JsonResponse({'errors': errors}, status=400)
	income = Income.objects.create(**values)
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
	values, errors = _validate_income_payload(payload, instance=income)
	if errors:
		return JsonResponse({'errors': errors}, status=400)
	for field, value in values.items():
		setattr(income, field, value)
	income.save(update_fields=[*values.keys()])
	return JsonResponse({'income': _serialize_income(income)})

import json

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, JsonResponse, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from .forms import IncomeForm


DASHBOARD_PAGE = settings.BASE_DIR / 'login-page' / 'dashboard.html'


@require_GET
@ensure_csrf_cookie
def login_page(request):
    # Always show the login page when opening /
    return render(request, 'registration/login.html')


@require_GET
def login_asset(request, filename):
    if filename not in {'style.css', 'script.js'}:
        return JsonResponse(
            {'error': 'Not found.'},
            status=404
        )

    asset_root = (settings.BASE_DIR / 'login-page').resolve()
    asset_path = (asset_root / filename).resolve()

    if asset_root not in asset_path.parents or not asset_path.is_file():
        return JsonResponse(
            {'error': 'Not found.'},
            status=404
        )

    return FileResponse(asset_path.open('rb'))


@require_POST
def login_api(request):
    try:
        payload = json.loads(request.body)

    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse(
            {'error': 'Invalid request data.'},
            status=400
        )

    if not isinstance(payload, dict):
        return JsonResponse(
            {'error': 'Invalid request data.'},
            status=400
        )

    email = payload.get('email', '')
    password = payload.get('password', '')

    if not isinstance(email, str) or not isinstance(password, str):
        return JsonResponse(
            {'error': 'Email and password are required.'},
            status=400
        )

    email = email.strip()

    if not email or not password:
        return JsonResponse(
            {'error': 'Email and password are required.'},
            status=400
        )

    user_model = get_user_model()

    matching_user = user_model.objects.filter(
        email__iexact=email
    ).first()

    username = (
        matching_user.get_username()
        if matching_user
        else email
    )

    user = authenticate(
        request,
        username=username,
        password=password
    )

    if user is None:
        return JsonResponse(
            {'error': 'Invalid email or password.'},
            status=401
        )

    login(request, user)

    request.session.set_expiry(
        1209600 if payload.get('remember') is True else 0
    )

    return JsonResponse({
        'message': 'Login successful.',
        'redirect': '/dashboard/'
    })


@require_POST
def logout_api(request):
    logout(request)

    return JsonResponse({
        'message': 'You have been logged out.'
    })


@require_GET
@login_required(login_url='/')
def dashboard(request):

    # If dashboard.html exists, open it
    if DASHBOARD_PAGE.is_file():
        return FileResponse(
            DASHBOARD_PAGE.open('rb')
        )

    # Temporary dashboard if dashboard.html does not exist
    return HttpResponse("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Expense Manager Dashboard</title>
            <style>
                body {
                    margin: 0;
                    font-family: Arial, sans-serif;
                    background: #f4f6f8;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    min-height: 100vh;
                }

                .dashboard {
                    background: white;
                    padding: 40px;
                    border-radius: 15px;
                    text-align: center;
                    box-shadow: 0 10px 30px rgba(0,0,0,0.15);
                }

                h1 {
                    color: #667eea;
                }

                p {
                    color: #666;
                }

                a {
                    display: inline-block;
                    margin-top: 20px;
                    padding: 12px 20px;
                    background: #667eea;
                    color: white;
                    text-decoration: none;
                    border-radius: 8px;
                }

                a:hover {
                    background: #5568d9;
                }
            </style>
        </head>

        <body>

            <div class="dashboard">

                <h1>Welcome to Expense Manager</h1>

                <p>You are successfully logged in.</p>

                <a href="/income/add/">
                    Add Income
                </a>

            </div>

        </body>
        </html>
    """)


@require_GET
@login_required(login_url='/')
def session_api(request):
    return JsonResponse({
        'username': request.user.get_username(),
        'email': request.user.email
    })


@login_required(login_url='/')
def add_income(request):

    if request.method == 'POST':

        form = IncomeForm(request.POST)

        if form.is_valid():

            form.save()

            return render(
                request,
                'tasks/add_income.html',
                {
                    'form': IncomeForm(),
                    'success': 'Your income has been added successfully!'
                }
            )

    else:

        form = IncomeForm()

    return render(
        request,
        'tasks/add_income.html',
        {'form': form}
    )
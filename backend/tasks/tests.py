import json
import re
from urllib.parse import urlsplit

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .models import Expense, Income


class LoginFlowTests(TestCase):
	def setUp(self):
		self.email = 'person@example.com'
		self.password = 'correct-horse-battery'
		self.user = get_user_model().objects.create_user(
			username=self.email,
			email=self.email,
			password=self.password,
		)

	def post_login(self, payload):
		return self.client.post(
			reverse('login-api'),
			data=json.dumps(payload),
			content_type='application/json',
		)

	def test_valid_login_creates_session_and_returns_dashboard_redirect(self):
		response = self.post_login({
			'email': self.email,
			'password': self.password,
			'remember': True,
		})

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json()['redirect'], '/dashboard/')
		self.assertEqual(self.client.session.get_expiry_age(), 1209600)
		self.assertEqual(self.client.get(reverse('session-api')).status_code, 200)

	def test_invalid_credentials_return_generic_error(self):
		response = self.post_login({'email': self.email, 'password': 'wrong-password'})

		self.assertEqual(response.status_code, 401)
		self.assertEqual(response.json()['error'], 'Invalid email or password.')

	def test_missing_fields_are_rejected(self):
		response = self.post_login({'email': self.email, 'password': ''})

		self.assertEqual(response.status_code, 400)
		self.assertEqual(response.json()['error'], 'Email and password are required.')

	def test_malformed_json_is_rejected(self):
		response = self.client.post(reverse('login-api'), data='{', content_type='application/json')

		self.assertEqual(response.status_code, 400)

	def test_dashboard_opens_without_login_and_shows_expense_form(self):
		response = self.client.get('/')

		self.assertEqual(response.status_code, 200)
		dashboard_html = response.content.decode()
		self.assertIn('id="totalIncome"', dashboard_html)
		self.assertIn('id="recentTransactions"', dashboard_html)
		self.assertIn('href="/expenses/add/"', dashboard_html)
		self.assertNotIn('id="loginForm"', dashboard_html)

	def test_major_functions_open_dedicated_pages(self):
		page_expectations = {
			'expense-add': 'id="expenseForm"',
			'expense-list': 'id="expenseListRows"',
			'income-add': 'id="incomeForm"',
			'income-list': 'id="incomeListRows"',
			'reports': 'id="categoryReport"',
		}
		for route_name, expected_marker in page_expectations.items():
			with self.subTest(route=route_name):
				response = self.client.get(reverse(route_name))
				self.assertEqual(response.status_code, 200)
				self.assertContains(response, expected_marker)

	def test_logout_clears_session(self):
		self.client.force_login(self.user)

		response = self.client.post(reverse('logout-api'))

		self.assertEqual(response.status_code, 200)
		self.assertNotIn('_auth_user_id', self.client.session)

	def test_login_page_sets_csrf_cookie(self):
		csrf_client = Client(enforce_csrf_checks=True)

		response = csrf_client.get(reverse('login-page'))

		self.assertEqual(response.status_code, 200)
		self.assertIn('csrftoken', response.cookies)

	def test_login_requires_csrf_token(self):
		csrf_client = Client(enforce_csrf_checks=True)
		csrf_client.get('/')

		response = csrf_client.post(
			reverse('login-api'),
			data=json.dumps({'email': self.email, 'password': self.password}),
			content_type='application/json',
		)

		self.assertEqual(response.status_code, 403)

	def test_login_accepts_valid_csrf_token(self):
		csrf_client = Client(enforce_csrf_checks=True)
		csrf_client.get('/')
		csrf_token = csrf_client.cookies['csrftoken'].value

		response = csrf_client.post(
			reverse('login-api'),
			data=json.dumps({'email': self.email, 'password': self.password}),
			content_type='application/json',
			HTTP_X_CSRFTOKEN=csrf_token,
		)

		self.assertEqual(response.status_code, 200)

	def test_dashboard_html_is_not_a_public_asset(self):
		response = self.client.get('/login-page/dashboard.html')

		self.assertEqual(response.status_code, 404)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class PasswordResetFlowTests(TestCase):
	def setUp(self):
		self.user = get_user_model().objects.create_user(
			username='reset-person',
			email='reset@example.com',
			password='old-password-123',
		)

	def test_known_email_receives_reset_link_and_can_change_password(self):
		response = self.client.post(
			reverse('password-reset'),
			{'email': self.user.email},
		)

		self.assertRedirects(response, reverse('password-reset-done'))
		self.assertEqual(len(mail.outbox), 1)
		reset_url = next(
			line for line in mail.outbox[0].body.splitlines()
			if line.startswith('http://testserver/reset/')
		)
		reset_path = urlsplit(reset_url).path

		response = self.client.get(reset_path, follow=True)
		self.assertEqual(response.status_code, 200)
		set_password_url = response.redirect_chain[-1][0]
		new_password = 'A-new-secret-9482!'
		response = self.client.post(
			set_password_url,
			{'new_password1': new_password, 'new_password2': new_password},
			follow=True,
		)

		self.assertRedirects(response, reverse('password-reset-complete'))
		self.user.refresh_from_db()
		self.assertTrue(self.user.check_password(new_password))

	def test_unknown_email_gets_same_confirmation_without_sending_email(self):
		response = self.client.post(
			reverse('password-reset'),
			{'email': 'unknown@example.com'},
		)

		self.assertRedirects(response, reverse('password-reset-done'))
		self.assertEqual(len(mail.outbox), 0)

	def test_reset_form_uses_project_template(self):
		response = self.client.get(reverse('password-reset'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Password Reset')
		self.assertContains(response, 'Expense Manager')
		self.assertContains(response, '/static/tasks/app.css')
		self.assertNotContains(response, 'Django administration')

	def test_admin_password_reset_link_redirects_to_project_form(self):
		response = self.client.get('/admin/password_reset/')

		self.assertRedirects(response, reverse('password-reset'), fetch_redirect_response=False)

	def test_login_page_links_to_password_reset(self):
		response = self.client.get(reverse('login-page'))

		self.assertContains(response, 'href="/password-reset/"')

	def test_reset_page_rejects_malformed_email(self):
		response = self.client.post(
			reverse('password-reset'),
			{'email': 'not-an-email'},
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Enter a valid email address.')


class ExpenseApiTests(TestCase):
	def setUp(self):
		self.payload = {
			'amount': '1200.00',
			'category': 'Shopping',
			'date': '2025-06-01',
			'description': 'Groceries and household items',
		}

	def post_expense(self, payload):
		return self.client.post(
			reverse('expenses-api'),
			data=json.dumps(payload),
			content_type='application/json',
		)

	def test_create_and_edit_expense_persists_only_submitted_changes(self):
		create_response = self.post_expense(self.payload)

		self.assertEqual(create_response.status_code, 201)
		expense_id = create_response.json()['expense']['id']
		update_response = self.client.patch(
			reverse('expense-detail-api', args=[expense_id]),
			data=json.dumps({
				'amount': '1250.50',
				'category': 'Food',
				'description': 'Updated household items',
			}),
			content_type='application/json',
		)

		self.assertEqual(update_response.status_code, 200)
		self.assertEqual(update_response.json()['expense']['category'], 'Food')
		self.assertEqual(update_response.json()['expense']['date'], '2025-06-01')
		self.assertEqual(update_response.json()['expense']['amount'], '1250.50')
		expense = Expense.objects.get(pk=expense_id)
		self.assertEqual(expense.description, 'Updated household items')

	def test_expense_list_is_available_without_sign_in(self):
		self.post_expense(self.payload)

		response = self.client.get(reverse('expenses-api'))

		self.assertEqual(response.status_code, 200)
		self.assertEqual(len(response.json()['expenses']), 1)
		self.assertEqual(response.json()['expenses'][0]['category'], 'Shopping')
		self.assertIn('Shopping', response.json()['categories'])
		self.assertIn('Food', response.json()['categories'])

	def test_invalid_expense_fields_are_rejected(self):
		response = self.post_expense({
			**self.payload,
			'amount': '-4',
			'date': 'not-a-date',
		})

		self.assertEqual(response.status_code, 400)
		self.assertEqual(set(response.json()['errors']), {'amount', 'date'})
		self.assertEqual(Expense.objects.count(), 0)

	def test_delete_removes_only_the_selected_expense(self):
		first_id = self.post_expense(self.payload).json()['expense']['id']
		second_payload = {**self.payload, 'category': 'Food', 'amount': '500.00'}
		second_id = self.post_expense(second_payload).json()['expense']['id']

		response = self.client.delete(reverse('expense-detail-api', args=[first_id]))

		self.assertEqual(response.status_code, 200)
		self.assertFalse(Expense.objects.filter(pk=first_id).exists())
		self.assertTrue(Expense.objects.filter(pk=second_id).exists())

	def test_malformed_json_is_rejected(self):
		response = self.client.post(reverse('expenses-api'), data='{', content_type='application/json')

		self.assertEqual(response.status_code, 400)
		self.assertEqual(Expense.objects.count(), 0)


class IncomeApiTests(TestCase):
	def setUp(self):
		self.payload = {
			'amount': '3000.00',
			'source': 'Salary',
			'date': '2026-10-01',
			'description': 'Monthly pay',
		}

	def post_income(self, payload):
		return self.client.post(
			reverse('incomes-api'),
			data=json.dumps(payload),
			content_type='application/json',
		)

	def test_income_create_edit_and_delete_remain_separate_from_expenses(self):
		expense = Expense.objects.create(
			category='Food',
			amount='500.00',
			date='2026-10-02',
		)
		create_response = self.post_income(self.payload)

		self.assertEqual(create_response.status_code, 201)
		income_id = create_response.json()['income']['id']
		update_response = self.client.patch(
			reverse('income-detail-api', args=[income_id]),
			data=json.dumps({'amount': '3500.00', 'source': 'Freelance'}),
			content_type='application/json',
		)

		self.assertEqual(update_response.status_code, 200)
		self.assertEqual(update_response.json()['income']['source'], 'Freelance')
		self.assertEqual(update_response.json()['income']['date'], '2026-10-01')
		self.assertEqual(update_response.json()['income']['amount'], '3500.00')
		self.assertEqual(Income.objects.count(), 1)
		self.assertEqual(Expense.objects.count(), 1)
		delete_response = self.client.delete(reverse('income-detail-api', args=[income_id]))
		self.assertEqual(delete_response.status_code, 200)
		self.assertFalse(Income.objects.filter(pk=income_id).exists())
		self.assertTrue(Expense.objects.filter(pk=expense.pk).exists())

	def test_income_validation_rejects_invalid_values(self):
		response = self.post_income({**self.payload, 'source': ' ', 'amount': '0', 'date': 'bad-date'})

		self.assertEqual(response.status_code, 400)
		self.assertEqual(set(response.json()['errors']), {'source', 'amount', 'date'})
		self.assertEqual(Income.objects.count(), 0)

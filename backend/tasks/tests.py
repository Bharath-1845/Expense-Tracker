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

	def test_dashboard_js_is_served_as_asset(self):
		response = self.client.get('/login-page/dashboard.js')

		self.assertEqual(response.status_code, 200)

	def test_dashboard_renders_budget_and_expense_features(self):
		self.client.force_login(self.user)
		response = self.client.get(reverse('dashboard'))

		self.assertEqual(response.status_code, 200)
		content = b"".join(response.streaming_content).decode('utf-8')
		self.assertIn('Set Monthly Budget', content)
		self.assertIn('Add Expense', content)
		self.assertIn('Monthly Budget', content)
		self.assertIn('Total Expenses', content)
		self.assertIn('Remaining Balance', content)
		self.assertIn('Edit Expense', content)
		self.assertIn('editExpenseModal', content)
		self.assertIn('editExpenseForm', content)



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


class DashboardBudgetAndExpenseTests(TestCase):
	def setUp(self):
		user_model = get_user_model()
		self.user1 = user_model.objects.create_user(
			username='alice@example.com',
			email='alice@example.com',
			password='password123',
		)
		self.user2 = user_model.objects.create_user(
			username='bob@example.com',
			email='bob@example.com',
			password='password456',
		)

	def test_budget_api_requires_auth(self):
		response = self.client.get(reverse('budget-api'))
		self.assertEqual(response.status_code, 401)

		response = self.client.post(reverse('budget-api'), data='{}', content_type='application/json')
		self.assertEqual(response.status_code, 401)

	def test_set_monthly_budget_and_query(self):
		self.client.force_login(self.user1)

		# Set budget for 2026-10
		post_resp = self.client.post(
			reverse('budget-api'),
			data=json.dumps({'year': 2026, 'month': 10, 'amount': 25000.50}),
			content_type='application/json',
		)
		self.assertEqual(post_resp.status_code, 200)
		post_data = post_resp.json()
		self.assertEqual(post_data['budget'], 25000.50)
		self.assertEqual(post_data['remaining_balance'], 25000.50)

		# Query via GET
		get_resp = self.client.get(reverse('budget-api'), {'year': 2026, 'month': 10})
		self.assertEqual(get_resp.status_code, 200)
		get_data = get_resp.json()
		self.assertEqual(get_data['budget'], 25000.50)
		self.assertEqual(get_data['total_expenses'], 0)
		self.assertEqual(get_data['remaining_balance'], 25000.50)
		self.assertFalse(get_data['is_over_budget'])

	def test_set_budget_rejects_negative_amount(self):
		self.client.force_login(self.user1)

		response = self.client.post(
			reverse('budget-api'),
			data=json.dumps({'year': 2026, 'month': 10, 'amount': -500}),
			content_type='application/json',
		)
		self.assertEqual(response.status_code, 400)
		self.assertIn('cannot be negative', response.json()['error'])

	def test_add_expense_and_retrieve_list(self):
		self.client.force_login(self.user1)

		# Add expense
		add_resp = self.client.post(
			reverse('expenses-api'),
			data=json.dumps({
				'title': 'Groceries',
				'amount': 1500.00,
				'category': 'Food & Dining',
				'date': '2026-10-04',
				'notes': 'Supermarket run',
			}),
			content_type='application/json',
		)
		self.assertEqual(add_resp.status_code, 201)
		exp_id = add_resp.json()['expense']['id']

		# Retrieve expenses for 2026-10
		get_resp = self.client.get(reverse('expenses-api'), {'year': 2026, 'month': 10})
		self.assertEqual(get_resp.status_code, 200)
		expenses = get_resp.json()['expenses']
		self.assertEqual(len(expenses), 1)
		self.assertEqual(expenses[0]['title'], 'Groceries')
		self.assertEqual(float(expenses[0]['amount']), 1500.00)
		self.assertEqual(expenses[0]['category'], 'Food & Dining')

	def test_add_expense_validation(self):
		self.client.force_login(self.user1)

		# Missing title and description
		resp = self.client.post(
			reverse('expenses-api'),
			data=json.dumps({'title': '', 'amount': 100, 'date': '2026-10-01'}),
			content_type='application/json',
		)
		self.assertEqual(resp.status_code, 400)

		# Non-positive amount
		resp = self.client.post(
			reverse('expenses-api'),
			data=json.dumps({'title': 'Coffee', 'amount': -10, 'date': '2026-10-01'}),
			content_type='application/json',
		)
		self.assertEqual(resp.status_code, 400)

		# Invalid date
		resp = self.client.post(
			reverse('expenses-api'),
			data=json.dumps({'title': 'Coffee', 'amount': 100, 'date': 'invalid-date'}),
			content_type='application/json',
		)
		self.assertEqual(resp.status_code, 400)

	def test_budget_and_expenses_integration_and_over_budget(self):
		self.client.force_login(self.user1)

		# Set budget of 2000
		self.client.post(
			reverse('budget-api'),
			data=json.dumps({'year': 2026, 'month': 10, 'amount': 2000.00}),
			content_type='application/json',
		)

		# Add expense of 1500
		self.client.post(
			reverse('expenses-api'),
			data=json.dumps({
				'title': 'Dinner',
				'amount': 1500.00,
				'category': 'Food & Dining',
				'date': '2026-10-02',
			}),
			content_type='application/json',
		)

		# Budget check
		summary = self.client.get(reverse('budget-api'), {'year': 2026, 'month': 10}).json()
		self.assertEqual(summary['budget'], 2000.00)
		self.assertEqual(summary['total_expenses'], 1500.00)
		self.assertEqual(summary['remaining_balance'], 500.00)
		self.assertEqual(summary['percentage_used'], 75.0)
		self.assertFalse(summary['is_over_budget'])

		# Add second expense of 1000 (total 2500, exceeds budget of 2000)
		self.client.post(
			reverse('expenses-api'),
			data=json.dumps({
				'title': 'Shopping',
				'amount': 1000.00,
				'category': 'Shopping',
				'date': '2026-10-03',
			}),
			content_type='application/json',
		)

		summary_after = self.client.get(reverse('budget-api'), {'year': 2026, 'month': 10}).json()
		self.assertEqual(summary_after['total_expenses'], 2500.00)
		self.assertEqual(summary_after['remaining_balance'], -500.00)
		self.assertTrue(summary_after['is_over_budget'])

	def test_delete_expense(self):
		self.client.force_login(self.user1)

		add_resp = self.client.post(
			reverse('expenses-api'),
			data=json.dumps({
				'title': 'Taxi',
				'amount': 300.00,
				'date': '2026-10-05',
			}),
			content_type='application/json',
		)
		exp_id = add_resp.json()['expense']['id']

		# Delete expense
		del_resp = self.client.delete(reverse('expense-detail-api', args=[exp_id]))
		self.assertEqual(del_resp.status_code, 200)

		# Confirm deleted
		get_resp = self.client.get(reverse('expenses-api'), {'year': 2026, 'month': 10})
		self.assertEqual(len(get_resp.json()['expenses']), 0)

	def test_multi_user_isolation(self):
		self.client.force_login(self.user1)
		# User1 creates budget and expense
		self.client.post(
			reverse('budget-api'),
			data=json.dumps({'year': 2026, 'month': 10, 'amount': 10000.00}),
			content_type='application/json',
		)
		exp_resp = self.client.post(
			reverse('expenses-api'),
			data=json.dumps({
				'title': 'User1 Expense',
				'amount': 500.00,
				'date': '2026-10-05',
			}),
			content_type='application/json',
		)
		user1_exp_id = exp_resp.json()['expense']['id']

		# Switch to User2
		self.client.force_login(self.user2)

		# User2 should see 0 budget and 0 expenses
		user2_budget = self.client.get(reverse('budget-api'), {'year': 2026, 'month': 10}).json()
		self.assertEqual(user2_budget['budget'], 0.0)
		self.assertEqual(user2_budget['total_expenses'], 0.0)

		# User2 cannot delete User1's expense
		del_resp = self.client.delete(reverse('expense-detail-api', args=[user1_exp_id]))
		self.assertEqual(del_resp.status_code, 404)

		# User2 cannot edit User1's expense
		edit_resp = self.client.put(
			reverse('expense-detail-api', args=[user1_exp_id]),
			data=json.dumps({'title': 'Hacked Title', 'amount': 999.00}),
			content_type='application/json',
		)
		self.assertEqual(edit_resp.status_code, 404)

	def test_get_single_expense_detail(self):
		self.client.force_login(self.user1)

		add_resp = self.client.post(
			reverse('expenses-api'),
			data=json.dumps({
				'title': 'Coffee',
				'amount': 150.00,
				'category': 'Food & Dining',
				'date': '2026-10-03',
				'notes': 'Cafe visit',
			}),
			content_type='application/json',
		)
		exp_id = add_resp.json()['expense']['id']

		get_resp = self.client.get(reverse('expense-detail-api', args=[exp_id]))
		self.assertEqual(get_resp.status_code, 200)
		exp_data = get_resp.json()['expense']
		self.assertEqual(exp_data['id'], exp_id)
		self.assertEqual(exp_data['title'], 'Coffee')
		self.assertEqual(float(exp_data['amount']), 150.00)
		self.assertEqual(exp_data['category'], 'Food & Dining')
		self.assertEqual(exp_data['date'], '2026-10-03')
		self.assertEqual(exp_data['notes'], 'Cafe visit')

	def test_edit_expense_success(self):
		self.client.force_login(self.user1)

		add_resp = self.client.post(
			reverse('expenses-api'),
			data=json.dumps({
				'title': 'Original Item',
				'amount': 250.00,
				'category': 'Shopping',
				'date': '2026-10-01',
				'notes': 'Initial notes',
			}),
			content_type='application/json',
		)
		exp_id = add_resp.json()['expense']['id']

		# Edit expense
		edit_resp = self.client.put(
			reverse('expense-detail-api', args=[exp_id]),
			data=json.dumps({
				'title': 'Updated Item',
				'amount': 450.75,
				'category': 'Entertainment',
				'date': '2026-10-02',
				'notes': 'Updated notes',
			}),
			content_type='application/json',
		)
		self.assertEqual(edit_resp.status_code, 200)
		edit_data = edit_resp.json()
		self.assertEqual(edit_data['message'], 'Expense updated successfully.')
		self.assertEqual(edit_data['expense']['title'], 'Updated Item')
		self.assertEqual(float(edit_data['expense']['amount']), 450.75)
		self.assertEqual(edit_data['expense']['category'], 'Entertainment')
		self.assertEqual(edit_data['expense']['date'], '2026-10-02')
		self.assertEqual(edit_data['expense']['notes'], 'Updated notes')

		# Verify in DB
		get_resp = self.client.get(reverse('expenses-api'), {'year': 2026, 'month': 10})
		expenses = get_resp.json()['expenses']
		self.assertEqual(len(expenses), 1)
		self.assertEqual(expenses[0]['title'], 'Updated Item')
		self.assertEqual(float(expenses[0]['amount']), 450.75)
		self.assertEqual(expenses[0]['category'], 'Entertainment')

	def test_edit_expense_validation(self):
		self.client.force_login(self.user1)

		add_resp = self.client.post(
			reverse('expenses-api'),
			data=json.dumps({
				'title': 'Book',
				'amount': 500.00,
				'date': '2026-10-01',
			}),
			content_type='application/json',
		)
		exp_id = add_resp.json()['expense']['id']

		# Empty title
		resp = self.client.put(
			reverse('expense-detail-api', args=[exp_id]),
			data=json.dumps({'title': '', 'amount': 200, 'date': '2026-10-01'}),
			content_type='application/json',
		)
		self.assertEqual(resp.status_code, 400)
		self.assertIn('description is required', resp.json()['error'])

		# Non-positive amount
		resp = self.client.put(
			reverse('expense-detail-api', args=[exp_id]),
			data=json.dumps({'title': 'Book', 'amount': -50, 'date': '2026-10-01'}),
			content_type='application/json',
		)
		self.assertEqual(resp.status_code, 400)
		self.assertIn('greater than zero', resp.json()['error'])

		# Invalid date
		resp = self.client.put(
			reverse('expense-detail-api', args=[exp_id]),
			data=json.dumps({'title': 'Book', 'amount': 200, 'date': 'invalid-date'}),
			content_type='application/json',
		)
		self.assertEqual(resp.status_code, 400)
		self.assertIn('valid date', resp.json()['error'])

		# Malformed JSON
		resp = self.client.put(
			reverse('expense-detail-api', args=[exp_id]),
			data='{invalid_json',
			content_type='application/json',
		)
		self.assertEqual(resp.status_code, 400)

	def test_edit_expense_updates_budget_totals(self):
		self.client.force_login(self.user1)

		# Set budget of 5000
		self.client.post(
			reverse('budget-api'),
			data=json.dumps({'year': 2026, 'month': 10, 'amount': 5000.00}),
			content_type='application/json',
		)

		# Add expense of 1000
		add_resp = self.client.post(
			reverse('expenses-api'),
			data=json.dumps({
				'title': 'Gadget',
				'amount': 1000.00,
				'date': '2026-10-02',
			}),
			content_type='application/json',
		)
		exp_id = add_resp.json()['expense']['id']

		summary_before = self.client.get(reverse('budget-api'), {'year': 2026, 'month': 10}).json()
		self.assertEqual(summary_before['total_expenses'], 1000.00)
		self.assertEqual(summary_before['remaining_balance'], 4000.00)

		# Edit expense to 2500
		self.client.put(
			reverse('expense-detail-api', args=[exp_id]),
			data=json.dumps({
				'title': 'Gadget Pro',
				'amount': 2500.00,
				'date': '2026-10-02',
			}),
			content_type='application/json',
		)

		summary_after = self.client.get(reverse('budget-api'), {'year': 2026, 'month': 10}).json()
		self.assertEqual(summary_after['total_expenses'], 2500.00)
		self.assertEqual(summary_after['remaining_balance'], 2500.00)
		self.assertEqual(summary_after['percentage_used'], 50.0)


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

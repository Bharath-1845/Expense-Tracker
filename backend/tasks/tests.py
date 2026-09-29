import json
import re
from urllib.parse import urlsplit

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse


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

	def test_dashboard_requires_authentication(self):
		response = self.client.get(reverse('dashboard'))

		self.assertEqual(response.status_code, 302)
		self.assertEqual(response.url, '/?next=/dashboard/')

	def test_logout_clears_session(self):
		self.client.force_login(self.user)

		response = self.client.post(reverse('logout-api'))

		self.assertEqual(response.status_code, 200)
		self.assertNotIn('_auth_user_id', self.client.session)

	def test_login_page_sets_csrf_cookie(self):
		csrf_client = Client(enforce_csrf_checks=True)

		response = csrf_client.get('/')

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

	def test_login_page_links_to_password_reset(self):
		response = self.client.get('/')

		self.assertContains(response, 'href="/password-reset/"')

	def test_reset_page_rejects_malformed_email(self):
		response = self.client.post(
			reverse('password-reset'),
			{'email': 'not-an-email'},
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Enter a valid email address.')

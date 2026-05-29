import unittest
from unittest.mock import patch, MagicMock
import json
import jwt
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.config import Config

class WelcomeEmailTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        # Generate a valid JWT token for testing (role: hr)
        self.token = jwt.encode(
            {
                "user_id": 1,
                "username": "hr@altzor.com",
                "role": "hr",
                "employee_name": "Shruti Jadhav",
                "password_change_required": False
            },
            Config.JWT_SECRET,
            algorithm="HS256"
        )
        self.headers = {
            "Authorization": f"Bearer {self.token}"
        }

    @patch('app.api.routes.welcome_email_routes.execute_query')
    def test_get_pending_welcome_emails(self, mock_execute_query):
        # Mock database response for pending emails
        mock_execute_query.return_value = [
            {"id": 10, "name": "Rahul Sharma", "email": "rahul.sharma@example.com"},
            {"id": 11, "name": "Sunita Patel", "email": "sunita.patel@example.com"}
        ]
        
        # We mock the blacklisted token check in authentication middleware
        with patch('app.api.middleware.auth.execute_single', return_value=None):
            resp = self.client.get('/pending-welcome-emails', headers=self.headers)
            
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertTrue(data['success'])
        self.assertEqual(data['count'], 2)
        self.assertEqual(data['pending_emails'][0]['id'], 10)
        self.assertEqual(data['pending_emails'][0]['firstName'], "Rahul")
        self.assertEqual(data['pending_emails'][0]['fullName'], "Rahul Sharma")
        self.assertEqual(data['pending_emails'][1]['firstName'], "Sunita")

    @patch('app.api.routes.welcome_email_routes.execute_single')
    @patch('app.api.routes.welcome_email_routes.threading.Thread')
    def test_send_welcome_emails(self, mock_thread, mock_execute_single):
        # Mock finding the pending employee
        mock_execute_single.return_value = {
            "id": 10,
            "name": "Rahul Sharma",
            "email": "rahul.sharma@example.com"
        }
        
        payload = {
            "employee_ids": [10],
            "subject": "Welcome {{Employee Full Name}}!",
            "body": "Hi {{Employee First Name}}, welcome!"
        }
        
        with patch('app.api.middleware.auth.execute_single', return_value=None):
            resp = self.client.post('/send-welcome-emails', json=payload, headers=self.headers)
            
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertTrue(data['success'])
        self.assertIn("Successfully queued", data['message'])
        self.assertTrue(mock_thread.called)

    @patch('app.api.routes.welcome_email_routes.execute_query')
    @patch('app.api.routes.welcome_email_routes._smtp_send')
    @patch('app.api.routes.welcome_email_routes._log_notification')
    def test_send_welcome_email_worker_success(self, mock_log, mock_smtp_send, mock_execute_query):
        from app.api.routes.welcome_email_routes import send_welcome_email_worker
        
        # Run worker directly to test synchronous operations
        send_welcome_email_worker(
            employee_id=10,
            email="rahul.sharma@example.com",
            full_name="Rahul Sharma",
            first_name="Rahul",
            subject="Welcome {{Employee Full Name}}!",
            body="Hi {{Employee First Name}}, welcome!"
        )
        
        # Verify SMTP send was called with correctly replaced/rendered templates
        mock_smtp_send.assert_called_once()
        args = mock_smtp_send.call_args[0]
        self.assertEqual(args[0], "rahul.sharma@example.com")
        self.assertEqual(args[1], "Welcome Rahul Sharma!")
        self.assertIn("Hi Rahul, welcome!", args[2])
        
        # Verify DB delete query was executed
        mock_execute_query.assert_called_once_with(
            "DELETE FROM pending_welcome_emails WHERE employee_id = %s",
            (10,),
            commit=True
        )
        # Verify audit log helper
        mock_log.assert_called_once_with("welcome_email", "rahul.sharma@example.com", "Rahul Sharma", None, sent=True)

    @patch('app.api.routes.welcome_email_routes.execute_query')
    @patch('app.api.routes.welcome_email_routes._smtp_send')
    @patch('app.api.routes.welcome_email_routes._log_notification')
    def test_send_welcome_email_worker_failure(self, mock_log, mock_smtp_send, mock_execute_query):
        from app.api.routes.welcome_email_routes import send_welcome_email_worker
        
        # Mock SMTP raising connection or auth exception
        mock_smtp_send.side_effect = Exception("SMTP connection timed out")
        
        # Run worker directly
        send_welcome_email_worker(
            employee_id=10,
            email="rahul.sharma@example.com",
            full_name="Rahul Sharma",
            first_name="Rahul",
            subject="Welcome {{Employee Full Name}}!",
            body="Hi {{Employee First Name}}, welcome!"
        )
        
        # Verify that the deletion was NOT called (employee remains pending)
        mock_execute_query.assert_not_called()
        
        # Verify failure is logged in database
        mock_log.assert_called_once()
        args = mock_log.call_args[0]
        kwargs = mock_log.call_args[1]
        self.assertEqual(args[0], "welcome_email")
        self.assertEqual(args[1], "rahul.sharma@example.com")
        self.assertEqual(args[2], "Rahul Sharma")
        self.assertFalse(kwargs.get('sent'))
        self.assertEqual(kwargs.get('error_message'), "SMTP connection timed out")

if __name__ == '__main__':
    unittest.main()

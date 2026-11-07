import smtplib
from unittest.mock import patch
import pytest
from backend import email_delivery

ENV = {'GMAIL_USER':'sender@gmail.com','GMAIL_APP_PASSWORD':'test only password','PUBLIC_APP_URL':'https://playoff.example'}

@pytest.mark.parametrize('purpose', ['verify-email','reset-password'])
def test_gmail_message_uses_tls_and_keeps_token_out_of_query_string(purpose):
    with patch.dict('os.environ',ENV), patch('backend.email_delivery.smtplib.SMTP_SSL') as smtp:
        smtp.return_value.__enter__.return_value.send_message.return_value={}
        email_delivery.send_link('player@example.com','A'*43,purpose)
        smtp.assert_called_once()
        assert smtp.call_args.args==('smtp.gmail.com',465)
        transport=smtp.return_value.__enter__.return_value
        transport.login.assert_called_once_with('sender@gmail.com','testonlypassword')
        message=transport.send_message.call_args.args[0]
        assert message['To']=='player@example.com'
        assert f'https://playoff.example/{purpose}#token=' in message.get_content()
        assert '?token=' not in message.get_content()

def test_gmail_failure_does_not_expose_provider_response():
    with patch.dict('os.environ',ENV), patch('backend.email_delivery.smtplib.SMTP_SSL',side_effect=smtplib.SMTPAuthenticationError(535,b'sensitive provider response')):
        with pytest.raises(email_delivery.DeliveryError,match='Email delivery failed') as error:
            email_delivery.send_link('player@example.com','A'*43,'reset-password')
        assert 'sensitive' not in str(error.value)

@pytest.mark.parametrize('url',['http://evil.example','https://user:secret@playoff.example','https://playoff.example/path','https://playoff.example?next=evil'])
def test_links_require_an_explicit_safe_origin(url):
    with patch.dict('os.environ',dict(ENV,PUBLIC_APP_URL=url)):
        with pytest.raises(email_delivery.DeliveryError):
            email_delivery.settings()

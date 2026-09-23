"""Telegram transport failures remain actionable without leaking credentials."""
import io
import json
from pathlib import Path
import socket
import ssl
import sys
import unittest
import urllib.error
from unittest.mock import MagicMock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import telegram_notifications as telegram


class TransportTests(unittest.TestCase):
    token='123456789:'+'x'*30

    def failure(self,method,status,body):
        error=urllib.error.HTTPError('https://api.telegram.org/bot'+self.token+'/'+method,status,self.token,{},io.BytesIO(body))
        with patch('urllib.request.build_opener') as opener:
            opener.return_value.open.side_effect=error
            with self.assertRaises(RuntimeError) as caught:telegram.request(self.token,method)
        message=str(caught.exception)
        self.assertNotIn(self.token,message)
        return message

    def test_network_filter_html_is_not_mislabeled_as_bad_token(self):
        for status,body in [(404,b'<pre>Cannot POST /bot'+self.token.encode()+b'/getMe</pre>'),(403,b'<title>Website Filtered</title>')]:
            with self.subTest(status=status):
                message=self.failure('getMe',status,body)
                self.assertIn('web filter',message)
                self.assertNotIn('Chat ID',message)
                self.assertNotIn('rejected the bot token',message)

    def test_api_errors_distinguish_token_chat_permissions_and_rate_limits(self):
        cases=[('getMe',401,'Unauthorized','bot token'),('getMe',404,'Not Found','bot token'),
               ('sendMessage',400,'Bad Request: chat not found','Chat ID'),
               ('sendMessage',403,'Forbidden: bot was blocked by the user','Unblock'),
               ('sendMessage',403,'Forbidden: bot is not a member','group permissions'),
               ('getMe',429,'Too Many Requests','too many requests'),('getMe',502,'Bad Gateway','temporarily unavailable')]
        for method,status,description,expected in cases:
            with self.subTest(method=method,status=status,description=description):
                message=self.failure(method,status,json.dumps({'ok':False,'error_code':status,'description':description+' '+self.token}).encode())
                self.assertIn(expected,message)
                if method=='getMe':self.assertNotIn('Chat ID',message)

    def test_success_and_malformed_success_body(self):
        for body,valid in [(json.dumps({'ok':True,'result':{'username':'fixture_bot'}}).encode(),True),
                           (b'<title>Website Filtered</title>',False),(b'[]',False),(b'{}',False)]:
            with self.subTest(body=body),patch('urllib.request.build_opener') as opener:
                response=MagicMock();response.status=200;response.read.return_value=body
                opener.return_value.open.return_value.__enter__.return_value=response
                if valid:self.assertEqual(telegram.request(self.token,'getMe'),{'username':'fixture_bot'})
                else:
                    with self.assertRaisesRegex(RuntimeError,'web filter'):telegram.request(self.token,'getMe')

    def test_connection_failures_do_not_echo_exception_url(self):
        for reason,expected in [(TimeoutError(self.token),'8 seconds'),(socket.gaierror(self.token),'DNS'),
                                (ssl.SSLCertVerificationError(self.token),'certificate'),(OSError(self.token),'network')]:
            with self.subTest(reason=type(reason).__name__),patch('urllib.request.build_opener') as opener:
                opener.return_value.open.side_effect=urllib.error.URLError(reason)
                with self.assertRaisesRegex(RuntimeError,expected) as caught:telegram.request(self.token,'getMe')
                self.assertNotIn(self.token,str(caught.exception))

    def test_failed_verification_never_saves_credentials(self):
        import session_secrets
        from studio import Problem
        with patch.object(telegram,'request',side_effect=RuntimeError('Network blocked')),patch.object(session_secrets,'put') as save:
            with self.assertRaisesRegex(Problem,'Network blocked'):
                telegram.configure('fixture',{'token':self.token,'chatId':'12345','_credentialSession':'fixture:tab'})
            save.assert_not_called()

    def test_disconnect_cannot_remove_a_replacement_tabs_connection(self):
        import session_secrets as vault
        key = telegram.key('disconnect-race-fixture')
        self.addCleanup(vault.remove, key)
        vault.put(key, {'bot': 'old_bot'}, 'old-tab')
        original_get, original_remove = vault.get, vault.remove

        def replace_before_remove(*args, **kwargs):
            # A new tab connects just before the old disconnect mutates storage.
            vault.put(key, {'bot': 'new_bot'}, 'new-tab')
            return original_remove(*args, **kwargs)

        with patch.object(vault, 'remove', side_effect=replace_before_remove):
            result = telegram.configure('disconnect-race-fixture', {'_credentialSession': 'old-tab', 'disconnect': True})
        self.assertFalse(result['connected'])
        self.assertEqual(original_get(key, 'new-tab').get('bot'), 'new_bot')
        telegram.configure('disconnect-race-fixture', {'_credentialSession': 'new-tab', 'disconnect': True})
        self.assertFalse(original_get(key))


if __name__=='__main__':unittest.main()

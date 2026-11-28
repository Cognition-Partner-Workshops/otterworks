import http.client
import unittest
from unittest.mock import patch

with patch.dict("os.environ", {"LP_ROUTES": "test=/api/test=http://fn-test:8080"}):
    import gateway


class InvokeTest(unittest.TestCase):
    def test_non_success_emulator_status_is_not_a_lambda_result(self):
        with patch.object(gateway.http.client, "HTTPConnection") as connect:
            connection = connect.return_value
            response = connection.getresponse.return_value
            response.status = 500
            response.read.return_value = b'{"statusCode":200,"body":"not a valid invocation"}'
            with self.assertRaisesRegex(http.client.HTTPException, "HTTP 500"):
                gateway.invoke(gateway.DEFAULT, {})
            connection.close.assert_called_once()

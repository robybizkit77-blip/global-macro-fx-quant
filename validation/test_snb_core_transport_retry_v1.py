import http.client, io, json, unittest, urllib.error
from unittest.mock import patch, MagicMock
from validation.sources.chf_snb_official_core import fetch_json
URL="https://data.snb.ch/api/cube/plkopr/data/json/en"
def response(body=b'{"timeseries": []}',ctype="application/json"):
    r=MagicMock()
    r.status=200
    r.headers={"Content-Type":ctype}
    r.read.return_value=body
    r.__enter__.return_value=r
    return r
class Tests(unittest.TestCase):
    @patch("validation.sources.chf_snb_official_core.time.sleep")
    @patch("validation.sources.chf_snb_official_core.urllib.request.urlopen")
    def test_disconnect_then_success(self,open_,sleep):
        open_.side_effect=[http.client.RemoteDisconnected("closed"),response()]
        self.assertEqual(fetch_json(URL),{"timeseries":[]})
        self.assertEqual(open_.call_count,2);sleep.assert_called_once_with(2)
    @patch("validation.sources.chf_snb_official_core.time.sleep")
    @patch("validation.sources.chf_snb_official_core.urllib.request.urlopen")
    def test_bounded_failure(self,open_,sleep):
        open_.side_effect=http.client.RemoteDisconnected("closed")
        with self.assertRaises(http.client.RemoteDisconnected):fetch_json(URL)
        self.assertEqual(open_.call_count,3);self.assertEqual(sleep.call_count,2)
    @patch("validation.sources.chf_snb_official_core.time.sleep")
    @patch("validation.sources.chf_snb_official_core.urllib.request.urlopen")
    def test_fail_closed_without_retry(self,open_,sleep):
        for code in (401,403,429):
            open_.reset_mock();open_.side_effect=urllib.error.HTTPError(URL,code,"error",{},None)
            with self.assertRaises(urllib.error.HTTPError):fetch_json(URL)
            self.assertEqual(open_.call_count,1)
        open_.side_effect=None;open_.return_value=response(b"not json","text/html");open_.reset_mock()
        with self.assertRaises(ValueError):fetch_json(URL)
        self.assertEqual(open_.call_count,1);sleep.assert_not_called()
if __name__=="__main__":unittest.main()

#!/usr/bin/env python3
"""Offline regression: temporary publisher failures can recover, invalid data never does."""
import io
import unittest
import urllib.error
from unittest.mock import patch

from validation.fetch_rates_eur_gbp import get


class OfficialRatesTransportRetryTests(unittest.TestCase):
    url = 'https://data-api.ecb.europa.eu/service/data/YC/test'

    def http_error(self, code):
        return urllib.error.HTTPError(self.url, code, 'publisher failure', {}, None)

    @patch('validation.fetch_rates_eur_gbp.time.sleep')
    @patch('validation.fetch_rates_eur_gbp.urllib.request.urlopen')
    def test_temporary_504_then_valid_response(self, urlopen, sleep):
        urlopen.side_effect = [self.http_error(504), io.BytesIO(b'official-rate-csv')]
        self.assertEqual(get(self.url), b'official-rate-csv')
        self.assertEqual(urlopen.call_count, 2)
        sleep.assert_called_once_with(2)

    @patch('validation.fetch_rates_eur_gbp.time.sleep')
    @patch('validation.fetch_rates_eur_gbp.urllib.request.urlopen')
    def test_temporary_network_failure_then_valid_response(self, urlopen, sleep):
        urlopen.side_effect = [urllib.error.URLError('temporary connection loss'), io.BytesIO(b'csv')]
        self.assertEqual(get(self.url), b'csv')
        self.assertEqual(urlopen.call_count, 2)
        sleep.assert_called_once_with(2)

    @patch('validation.fetch_rates_eur_gbp.time.sleep')
    @patch('validation.fetch_rates_eur_gbp.urllib.request.urlopen')
    def test_persistent_504_fails_closed_after_three_attempts(self, urlopen, sleep):
        urlopen.side_effect = [self.http_error(504)] * 3
        with self.assertRaises(urllib.error.HTTPError):
            get(self.url)
        self.assertEqual(urlopen.call_count, 3)
        self.assertEqual([x.args[0] for x in sleep.call_args_list], [2, 4])

    @patch('validation.fetch_rates_eur_gbp.time.sleep')
    @patch('validation.fetch_rates_eur_gbp.urllib.request.urlopen')
    def test_403_never_bypasses_source_access(self, urlopen, sleep):
        urlopen.side_effect = self.http_error(403)
        with self.assertRaises(urllib.error.HTTPError):
            get(self.url)
        self.assertEqual(urlopen.call_count, 1)
        sleep.assert_not_called()

    @patch('validation.fetch_rates_eur_gbp.time.sleep')
    @patch('validation.fetch_rates_eur_gbp.urllib.request.urlopen')
    def test_404_does_not_fabricate_or_retry(self, urlopen, sleep):
        urlopen.side_effect = self.http_error(404)
        with self.assertRaises(urllib.error.HTTPError):
            get(self.url)
        self.assertEqual(urlopen.call_count, 1)
        sleep.assert_not_called()


if __name__ == '__main__':
    unittest.main()

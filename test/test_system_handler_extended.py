import unittest
from unittest.mock import patch, MagicMock
from modules.system_handler import validate_strftime, has_internet, sync_time, COMMON_TIMEZONES


class TestValidateStrftime(unittest.TestCase):

    def test_valid_date_format(self):
        valid, err = validate_strftime('%A')
        self.assertTrue(valid)
        self.assertEqual(err, '')

    def test_valid_time_format(self):
        valid, err = validate_strftime('%H:%M:%S')
        self.assertTrue(valid)
        self.assertEqual(err, '')

    def test_valid_combined_format(self):
        valid, err = validate_strftime('%A %d.%m.%Y %H:%M')
        self.assertTrue(valid)
        self.assertEqual(err, '')

    def test_valid_percent_escape(self):
        valid, err = validate_strftime('100%%')
        self.assertTrue(valid)
        self.assertEqual(err, '')

    def test_invalid_format_code(self):
        valid, err = validate_strftime('%Q')
        self.assertFalse(valid)
        self.assertIn('%Q', err)

    def test_invalid_format_code_lower(self):
        valid, err = validate_strftime('%k')
        self.assertFalse(valid)
        self.assertIn('%k', err)

    def test_empty_format(self):
        valid, err = validate_strftime('')
        self.assertTrue(valid)
        self.assertEqual(err, '')

    def test_no_percent_codes(self):
        valid, err = validate_strftime('hello world')
        self.assertTrue(valid)
        self.assertEqual(err, '')

    def test_valid_all_common_codes(self):
        common = '%A %a %B %b %c %d %D %f %F %g %G %h %H %I %j %m %M %n %p %R %S %t %T %u %U %V %w %W %x %X %y %Y %z %Z %%'
        valid, err = validate_strftime(common)
        self.assertTrue(valid, f"Unexpected error: {err}")


class TestHasInternet(unittest.TestCase):

    @patch('modules.system_handler.urllib.request.urlopen')
    def test_has_internet_success(self, mock_urlopen):
        mock_urlopen.return_value = MagicMock()
        self.assertTrue(has_internet())
        mock_urlopen.assert_called_once()

    @patch('modules.system_handler.urllib.request.urlopen')
    def test_has_internet_failure(self, mock_urlopen):
        mock_urlopen.side_effect = Exception("Connection failed")
        self.assertFalse(has_internet())

    @patch('modules.system_handler.urllib.request.urlopen')
    def test_has_internet_timeout(self, mock_urlopen):
        import urllib.error
        mock_urlopen.side_effect = urllib.error.URLError("timed out")
        self.assertFalse(has_internet())


class TestSyncTime(unittest.TestCase):

    @patch('modules.system_handler.shutil.which')
    @patch('modules.system_handler.subprocess.Popen')
    def test_sync_time_with_ntpdate(self, mock_popen, mock_which):
        import modules.system_handler as sh
        sh._ntpdate_available = None
        mock_which.return_value = '/usr/sbin/ntpdate'

        result = sync_time()

        self.assertEqual(result, "Time synchronization triggered")
        mock_popen.assert_called_once()
        args = mock_popen.call_args[0][0]
        self.assertIn('ntpdate', args)

    @patch('modules.system_handler.shutil.which')
    @patch('modules.system_handler.subprocess.Popen')
    def test_sync_time_without_ntpdate(self, mock_popen, mock_which):
        import modules.system_handler as sh
        sh._ntpdate_available = None
        mock_which.return_value = None

        result = sync_time()

        self.assertEqual(result, "Time synchronization triggered")
        self.assertEqual(mock_popen.call_count, 2)

    @patch('modules.system_handler.shutil.which')
    @patch('modules.system_handler.subprocess.Popen')
    def test_sync_time_ntpdate_cached(self, mock_popen, mock_which):
        import modules.system_handler as sh
        sh._ntpdate_available = True

        result = sync_time()

        self.assertEqual(result, "Time synchronization triggered")
        mock_which.assert_not_called()
        mock_popen.assert_called_once()


class TestCommonTimezones(unittest.TestCase):

    def test_common_timezones_is_nonempty_list(self):
        self.assertIsInstance(COMMON_TIMEZONES, list)
        self.assertGreater(len(COMMON_TIMEZONES), 0)

    def test_utc_included(self):
        self.assertIn("UTC", COMMON_TIMEZONES)

    def test_berlin_included(self):
        self.assertIn("Europe/Berlin", COMMON_TIMEZONES)


if __name__ == '__main__':
    unittest.main()

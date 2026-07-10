import unittest
from unittest.mock import patch, MagicMock
import shutil

from modules.system_handler import getFreeDiskSpace, reboot_system, shutdown_system


class TestSystemHandler(unittest.TestCase):

    @patch('modules.system_handler.shutil.disk_usage')
    def test_getFreeDiskSpace(self, mock_disk_usage):
        # Mock disk usage: total=100GB, used=30GB, free=70GB
        mock_disk_usage.return_value = (100 * (2**30), 30 * (2**30), 70 * (2**30))

        percent_used, free_gb = getFreeDiskSpace()

        # percent_used = (100 / 100) * 30 = 30%
        # free_gb = 70
        self.assertEqual(percent_used, 30.0)
        self.assertEqual(free_gb, 70)
        mock_disk_usage.assert_called_once_with("/")

    @patch('modules.system_handler.shutil.disk_usage')
    def test_getFreeDiskSpace_different_values(self, mock_disk_usage):
        # Mock disk usage: total=50GB, used=10GB, free=40GB
        mock_disk_usage.return_value = (50 * (2**30), 10 * (2**30), 40 * (2**30))

        percent_used, free_gb = getFreeDiskSpace()

        # percent_used = (100 / 50) * 10 = 20%
        # free_gb = 40
        self.assertEqual(percent_used, 20.0)
        self.assertEqual(free_gb, 40)

    @patch('modules.system_handler.os.system')
    def test_reboot_system(self, mock_system):
        result = reboot_system()

        self.assertEqual(result, "Reboot System now!")
        mock_system.assert_called_once_with('sudo reboot')

    @patch('modules.system_handler.os.system')
    def test_shutdown_system(self, mock_system):
        result = shutdown_system()

        self.assertEqual(result, "Shutting down! Bye bye")
        mock_system.assert_called_once_with('sudo shutdown -h now')


if __name__ == '__main__':
    unittest.main()

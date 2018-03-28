import mock

import zaza.charm_lifecycle.configure as lc_configure
import unit_tests.utils as ut_utils


class TestCharmLifecycleConfigure(ut_utils.BaseTestCase):

    def test_run_configure_list(self):
        self.patch_object(lc_configure.utils, 'get_class')
        self.get_class.side_effect = lambda x: x
        mock1 = mock.MagicMock()
        mock2 = mock.MagicMock()
        lc_configure.run_configure_list([mock1, mock2])
        self.assertTrue(mock1.called)
        self.assertTrue(mock2.called)

    def test_configure(self):
        self.patch_object(lc_configure, 'run_configure_list')
        mock1 = mock.MagicMock()
        mock2 = mock.MagicMock()
        lc_configure.configure('modelname', [mock1, mock2])
        self.run_configure_list.assert_called_once_with([mock1, mock2])

    def test_parser(self):
        args = lc_configure.parse_args(
            ['-m', 'modelname', '-c', 'my.func1', 'my.func2'])
        self.assertEqual(args.configfuncs, ['my.func1', 'my.func2'])
        self.assertEqual(args.model_name, 'modelname')

import mock

import zaza.charm_lifecycle.utils as lc_utils
import unit_tests.utils as ut_utils


class TestCharmLifecycleUtils(ut_utils.BaseTestCase):

    def test_get_charm_config(self):
        self.patch("builtins.open",
                   new_callable=mock.mock_open(),
                   name="_open")
        self.patch_object(lc_utils, 'yaml')
        _yaml = "testconfig: someconfig"
        _yaml_dict = {'test_config': 'someconfig'}
        self.yaml.load.return_value = _yaml_dict
        _filename = "filename"
        _fileobj = mock.MagicMock()
        _fileobj.__enter__.return_value = _yaml
        self._open.return_value = _fileobj

        self.assertEqual(lc_utils.get_charm_config(yaml_file=_filename),
                         _yaml_dict)
        self._open.assert_called_once_with(_filename, "r")
        self.yaml.load.assert_called_once_with(_yaml)

    def test_get_class(self):
        self.assertEqual(
            type(lc_utils.get_class('unit_tests.'
                                    'test_zaza_charm_lifecycle_utils.'
                                    'TestCharmLifecycleUtils')()),
            type(self))

    def test_get_juju_model(self):
        self.patch_object(lc_utils.os, 'environ')
        self.patch_object(lc_utils.model, 'get_current_model')
        self.get_current_model.return_value = 'modelsmodel'

        def _get_env(key):
            return _env.get(key)
        self.environ.__getitem__.side_effect = _get_env
        _env = {"JUJU_MODEL": 'envmodel'}

        # JUJU_ENV environment variable set
        self.assertEqual(lc_utils.get_juju_model(), 'envmodel')
        self.get_current_model.assert_not_called()

        # No envirnment variable
        self.environ.__getitem__.side_effect = KeyError
        self.assertEqual(lc_utils.get_juju_model(), 'modelsmodel')
        self.get_current_model.assert_called_once()

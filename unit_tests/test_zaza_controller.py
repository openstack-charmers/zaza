# Copyright 2018 Canonical Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import mock

import unit_tests.utils as ut_utils

import zaza.controller as controller


class TestAddModel(ut_utils.BaseTestCase):

    def setUp(self):
        super().setUp()
        self.patch_object(controller, 'jubilant')
        self.juju_mock = mock.MagicMock()
        self.jubilant.Juju.return_value = self.juju_mock

    def test_add_model_basic(self):
        controller.add_model('mymodel')
        self.juju_mock.add_model.assert_called_once_with(
            'mymodel', None, config=None, credential=None)

    def test_add_model_with_config(self):
        controller.add_model('mymodel', config={'run-faster': 'true'})
        self.juju_mock.add_model.assert_called_once_with(
            'mymodel', None, config={'run-faster': 'true'}, credential=None)

    def test_add_model_with_cloud_and_region(self):
        controller.add_model('mymodel', cloud_name='aws', region='us-east-1')
        self.juju_mock.add_model.assert_called_once_with(
            'mymodel', 'aws/us-east-1', config=None, credential=None)

    def test_add_model_with_region_only(self):
        controller.add_model('mymodel', region='us-east-1')
        self.juju_mock.add_model.assert_called_once_with(
            'mymodel', 'us-east-1', config=None, credential=None)

    def test_add_model_with_credential(self):
        controller.add_model('mymodel', credential_name='mycred')
        self.juju_mock.add_model.assert_called_once_with(
            'mymodel', None, config=None, credential='mycred')


class TestDestroyModel(ut_utils.BaseTestCase):

    def setUp(self):
        super().setUp()
        self.patch_object(controller, 'jubilant')
        self.juju_mock = mock.MagicMock()
        self.jubilant.Juju.return_value = self.juju_mock
        # list_models is called inside destroy_model to poll for removal.
        self.patch_object(controller, 'list_models')
        self.list_models.return_value = []

    def test_destroy_model(self):
        controller.destroy_model('mymodel')
        self.juju_mock.destroy_model.assert_called_once_with(
            'mymodel', destroy_storage=True, force=True, timeout=600)

    def test_destroy_model_raises_on_timeout(self):
        # Simulate the model never disappearing.
        self.list_models.return_value = ['mymodel']
        self.patch_object(controller, 'time')
        self.time.sleep = mock.MagicMock()
        with self.assertRaises(
                zaza.utilities.exceptions.DestroyModelFailed):
            controller.destroy_model('mymodel')


class TestListModels(ut_utils.BaseTestCase):

    def setUp(self):
        super().setUp()
        self.patch_object(controller, 'jubilant')
        self.juju_mock = mock.MagicMock()
        self.jubilant.Juju.return_value = self.juju_mock

    def test_list_models(self):
        self.juju_mock.cli.return_value = json.dumps(
            {'models': [{'name': 'admin/model1'}, {'name': 'admin/model2'}]})
        result = controller.list_models()
        self.assertEqual(result, ['model1', 'model2'])
        self.juju_mock.cli.assert_called_once_with(
            'models', '--format', 'json', include_model=False)


class TestGetCloud(ut_utils.BaseTestCase):

    def setUp(self):
        super().setUp()
        self.patch_object(controller, 'jubilant')
        self.juju_mock = mock.MagicMock()
        self.jubilant.Juju.return_value = self.juju_mock

    def test_get_cloud(self):
        self.juju_mock.cli.return_value = json.dumps(
            {'myctrl': {'details': {'cloud': 'lxd'}}})
        result = controller.get_cloud()
        self.assertEqual(result, 'lxd')
        self.juju_mock.cli.assert_called_once_with(
            'show-controller', '--format', 'json', include_model=False)


class TestGoListModels(ut_utils.BaseTestCase):

    def test_go_list_models(self):
        self.patch_object(controller, 'subprocess')
        controller.go_list_models()
        self.subprocess.check_call.assert_called_once_with(["juju", "models"])


# Make zaza.utilities.exceptions available after the import of controller.
import zaza.utilities.exceptions  # noqa: E402

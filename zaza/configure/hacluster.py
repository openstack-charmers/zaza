#!/usr/bin/env python3

# Copyright 2019 Canonical Ltd.
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

"""Helpers for dealing with hacluster."""

import logging
import xml.etree.ElementTree as ET

import zaza.model


def get_crm_status_xml(service_name, model_name=None):
    """Collect crm status information.

    :param service_name: Name of Juju application to run query against.
    :type service_name: str
    :param model_name: Name of model unit_name resides in.
    :type model_name: str
    :returns: status in XML format
    :rtype: xml.etree.ElementTree.Element
    """
    status_cmd = 'crm status --as-xml'
    status_xml = zaza.model.run_on_leader(
        service_name,
        status_cmd,
        model_name=model_name)['Stdout']
    return ET.fromstring(status_xml)


def get_nodes_status(service_name, model_name=None):
    """Get the status of the nodes in the cluster.

    :param service_name: Name of Juju application to run query against.
    :type service_name: str
    :param model_name: Name of model unit_name resides in.
    :type model_name: str
    :returns: {'name': {'online': True|False, 'type': 'member'|'remote'}}
    :rtype: dict
    """
    root = get_crm_status_xml(service_name, model_name=model_name)
    status = {}
    for child in root:
        if child.tag == 'nodes':
            for node in child:
                online = None
                if node.attrib['online'] == "true":
                    online = True
                elif node.attrib['online'] == "false":
                    online = False
                status[node.attrib['name']] = {
                    'online': online,
                    'type': node.attrib['type']}
    return status


def check_all_nodes_online(service_name, model_name=None):
    """Return whether all the crm nodes are online.

    :param service_name: Name of Juju application to run query against.
    :type service_name: str
    :param model_name: Name of model unit_name resides in.
    :type model_name: str
    :returns: Whether all the crm nodes are online
    :rtype: bool
    :raises: ValueError
    """
    statuses = []
    for node, data in get_nodes_status(service_name).items():
        logging.info('Node {} of type {} is in online state {}'.format(
            node,
            data['type'],
            data['online']))
        statuses.append(data['online'])
    if False in statuses:
        return False
    if len(set(statuses)) == 1 and statuses[0]:
        return True
    raise ValueError

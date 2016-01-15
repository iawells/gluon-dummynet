# Copyright (c) 2015 Cisco Systems, Inc.
# All Rights Reserved
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

# The Gluon backend that talks to our gluon_dummynet service.

import gluon.backend
from  requests import *
import json

class Provider(gluon.backend.Provider):
    def __init__(self, logger):
        self._drivers={}
	self._logger = logger

    def driver_for(self, config, backend):
        if backend['service_type'] == 'gluon_dummynet':
            return Driver(config, backend, self._logger)
        else:
            return None

class Driver(gluon.backend.Driver):
    def __init__(self, config, backend, logger):
	self._logger = logger
	self._svcurl = backend['url']

    def _make_url(self, x):
        return '%s%s' % (self._svcurl, x)

    def bind(self, port_id, device_owner, zone, 
             device_id, host_id, binding_profile):
	# TODO zone is presently not sent, probably bad...
	self._logger.debug('dummynet binding port %s' % port_id)
	body = {
	    'device_id': device_id, 
	    'device_owner': device_owner, 
	    'host': host_id,
	    'binding:profile': binding_profile}
	resp = put(self._make_url('ports/%s/bind' % port_id), body)
	self._logger.debug('Return from dummynet bind is %s ' 
                           % resp.status_code)
	
	return True

    def unbind(self, port_id):
	self._logger.debug('dummynet unbinding port %s' % port_id)
	resp = put(self._make_url('ports/%s/unbind' % port_id))
	self._logger.debug('Return from dummynet unbind is %s ' 
                           % resp.status_code)
	pass

    def port(self, port_id):
        self._logger.error('Fetching port data for %s' % port_id)

	resp = get(self._make_url('ports/%s' % port_id))

	# TODO spot errors and nonexistent ports

	remote_port = json.loads(resp.content)
	self._logger.error('dummynet: remote port is %s' % remote_port)
	
	# Then convert to a Gluon object.

        gluon_port = {}
        
        for f in ['id', 'device_owner', 'device_id',
                  'binding:vif_type', 'binding:vnic_type', 
                  'binding:profile', 'binding:details', 
                  'binding:vif_details', 'mac_address',
                  'vif_active', 'bound', 'host']:
            gluon_port[f] = remote_port.get(f)

        # TODO at the moment, Nova knows, uses and returns a
        # network name.  We keep this as a label.
        gluon_port['label'] = "dummynet"

        # Probably should just go away - don't want Nova bothering
        # about tenancy
        gluon_port['tenant_id'] = "fake"


	return gluon_port

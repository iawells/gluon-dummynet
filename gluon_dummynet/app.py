from flask import Flask
from flask_restful import reqparse, abort, Api, Resource
import os
import logging
import logging.handlers
import gluonclient.api as gluon_api
import uuid
import requests
from keystoneauth1 import loading
from keystoneauth1 import session
from novaclient import client as nova_client

logger = logging.getLogger('gluon_dummynet')
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
logger.addHandler(ch)
logger.debug('Debug logging enabled')

app = Flask('gluon_dummynet')
app.config.from_object('gluon_dummynet.settings.Default')
if 'DUMMYNET_SETTINGS' in os.environ:
    app.config.from_envvar('GLUON_DUMMYNET_SETTINGS')
print app.config

api = Api(app)

# TODO - a job list
# Events from neutron to nova are not propagated via gluon at present
######################################################################

ports = {
}

def abort_if_port_doesnt_exist(id):
    if id not in ports:
        abort(404, message="Port {} doesn't exist".format(id))

def client():
     config = app.config
     return gluon_api.NetworkServiceAPI(config['GLUON_URL'], 'gluon_dummynet', 'http://0:%s/' % config['PORT'])

client = client()

mac_key = 0
def _make_unique_mac():
    global mac_key
    s='%08x' % mac_key
    mac_key = mac_key + 1
    return 'fc:0f:' + str.join(':', [s[i:i+2] for i in range(0, len(s), 2)])


# Port
# shows a single port item and lets you delete a port item
class Port(Resource):
    def get(self, id=None):
        if id in ports:
	    return ports[id]
        abort(404, message="Port {} doesn't exist".format(id))

    # TODO there's a whole bunch of remote information about ports that should
    # be acquired here or somewhere nearby
    # binding information returned
    # mac_address (may be unavailable from the backend)
    # ip_address (may be unavailable from the backend)
    # (Nova also likes networks, subnets, need to fix that)

    def delete(self, id):
        abort_if_port_doesnt_exist(id)

        port = ports[id]

        del ports[id]
	client.notify_delete(id)

        device_id = port['device_id']
        device_owner = port['device_owner']
        # TODO the notification doesn't work for some reason
        #nova_notify(device_owner, device_id, id, VIF_DELETED)

        return '', 204

# PortList
# shows a list of all ports, and lets you POST to add new tasks
class PortList(Resource):
    def get(self):
	return ports

    def post(self):
	port={}
	# This is so trivial, ports have no arguments.

	id=str(uuid.uuid1())
	port['id']=id

	# TODO add a whole bunch of information here
	port['mac_address'] = _make_unique_mac()
	for f in BIND_PROPS:
	    port[f]=''

	port['binding:vnic_type'] = 'normal' # == VNIC_TYPE_NORMAL in Nova
	port['binding:profile'] = {} # Nothing till we're bound
	port['vif_active'] = False
	port['bound']=False

	port['binding:details'] = {}
	port['binding:vif_details'] = {}

        devname = "tap" + id
        devname = devname[:12] # TODO magic: a number in Nova.
        port['devname'] = devname

        ports[id] = port

	client.notify_create(id)

        return port, 201

BIND_PROPS = ['device_owner', 'zone', 'device_id', 'host']

# PortBind
# The specific ops to bind and unbind a port
class PortBind(Resource):
    def __init__(self):
	self.bind_args = reqparse.RequestParser()
	for f in BIND_PROPS:
	    self.bind_args.add_argument(f)
        self.bind_args.add_argument('pci_profile')
        self.bind_args.add_argument('rxtx_factor')

    def _bind(self, id):
	args = self.bind_args.parse_args()
	binding_profile={
	    'pci_profile': args['pci_profile'],
	    'rxtx_factor': args['rxtx_factor']
	    # TODO add negotiation here on binding types that are valid
	}

	port = ports[id]

	port['binding:profile'] = binding_profile
	for f in BIND_PROPS:
	     port[f] = args[f]
	vif_details = { 'port_filter': True }
	port['binding:vif_type'] = 'bridge' # == VIF_TYPE_BRIDGE in Nova
	port['binding:vif_details'] = vif_details
	port['bound'] = True
	port['binding:details'] = { 'bridge': 'dummy' }
	port['vif_active'] = True

        device_id = port['device_id']
        device_owner = port['device_owner']
        nova_notify(device_owner, device_id, id, VIF_PLUGGED)

    def _unbind(self, id):
	# Not very distributed-fault-tolerant, but no retries yet
	port = ports[id]

        device_id = port['device_id']
        device_owner = port['device_owner']

	for f in BIND_PROPS:
	    port[f]=''

	port['binding:details'] = {}
	port['binding:vif_details'] = {}
	port['bound'] = False
	port['vif_active'] = False
        nova_notify(device_owner, device_id, id, VIF_UNPLUGGED)

    def put(self, id, op):
	abort_if_port_doesnt_exist(id)
	if op == 'bind':
	    self._bind(id)
	elif op == 'unbind':
	    self._unbind(id)
	else:
	    return 'Invalid operation on port', 404

VIF_UNPLUGGED = 'network-vif-unplugged'
VIF_PLUGGED = 'network-vif-plugged'
VIF_DELETED = 'network-vif-deleted'
# TODO should be notifying Gluon, not nova
def nova_notify(device_owner, device_id, port_id, event):
    VERSION = '2'
# Docs say this, but this is not right:
#    # TODO load of config here, note
#    loader = loading.get_plugin_loader('password')
#    auth = loader.Password(auth_url='http://127.0.0.1:35357',
#                           username='nova',
#                           password='iheartksl',
#                           project_id='service')
#    sess = session.Session(auth=auth)
#    nova = nova_client.Client(VERSION, session=sess)
    extensions = [
        ext for ext in nova_client.discover_extensions(VERSION)
        if ext.name == "server_external_events"]
    nova = nova_client.Client(VERSION, 'nova', 'iheartksl', 
                              'service', auth_url='http://127.0.0.1:5000/v2.0',
                              extensions=extensions)
    nova.server_external_events.create(
        [{'server_uuid': device_id,
            'name': event,
            'status': "completed",
            'tag': port_id}])


##
## Actually setup the Api resource routing here
##
api.add_resource(PortList, 
		 '/ports')
api.add_resource(Port, 
		 '/ports/<id>')
api.add_resource(PortBind, '/ports/<id>/<op>')

def main():
    app.run(debug=True, port=int(app.config['PORT']))

if __name__ == '__main__':
    main()

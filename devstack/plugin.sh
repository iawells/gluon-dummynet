# plugin.sh - DevStack plugin.sh dispatch script for gluon-dummynet

gluon_dummynet_debug() {
    if [ ! -z "$GLUON_DUMMYNET_DEVSTACK_DEBUG" ] ; then
	"$@" || true # a debug command failing is not a failure
    fi
}

# For debugging purposes, highlight gluon_dummynet sections
gluon_dummynet_debug tput setab 2

name=gluon_dummynet

# The server

GITREPO['gluon_dummynet']=${GLUON_DUMMYNET_REPO:-https://github.com/iawells/gluon-dummynet.git}
GITBRANCH['gluon_dummynet']=${GLUON_DUMMYNET_BRANCH:-master}
GITDIR['gluon_dummynet']=$DEST/gluon-dummynet

function pre_install_me {
    :
}

function install_me {
    git_clone_by_name 'gluon_dummynet'
    setup_develop ${GITDIR['gluon_dummynet']}
}

function init_me {
    run_process $name "env GLUON_DUMMYNET_SETTINGS='/etc/gluon_dummynet/gluon_dummynet.config' '$GLUON_DUMMYNET_BINARY'"
}

function configure_me {
# This will want switching to the Openstack way of doing things when
# we switch frameworks, but the Flask config files look like this:
    sudo mkdir -p /etc/gluon_dummynet || true
    sudo tee /etc/gluon_dummynet/gluon_dummynet.config >/dev/null <<EOF
GLUON_API=http://127.0.0.1:2704/
PORT=1234
EOF
}

function shut_me_down {
    stop_process $name
}


# check for service enabled
if is_service_enabled $name; then

    if [[ "$1" == "stack" && "$2" == "pre-install" ]]; then
        # Set up system services
        echo_summary "Configuring system services $name"
	pre_install_me

    elif [[ "$1" == "stack" && "$2" == "install" ]]; then
        # Perform installation of service source
        echo_summary "Installing $name"
        install_me

    elif [[ "$1" == "stack" && "$2" == "post-config" ]]; then
        # Configure after the other layer 1 and 2 services have been configured
        echo_summary "Configuring $name"
        configure_me

    elif [[ "$1" == "stack" && "$2" == "extra" ]]; then
        # Initialize and start the service
        echo_summary "Initializing $name"
        init_me
    fi

    if [[ "$1" == "unstack" ]]; then
        # Shut down services
	shut_me_down
    fi

    if [[ "$1" == "clean" ]]; then
        # Remove state and transient data
        # Remember clean.sh first calls unstack.sh
        # no-op
        :
    fi
fi

gluon_dummynet_debug tput setab 9

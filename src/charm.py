#!/usr/bin/env python3
#
# (c) 2020 Canonical Ltd. All right reservered
#
from ops.main import main
from ops.framework import StoredState
from ops.model import (ActiveStatus, BlockedStatus, MaintenanceStatus,
                       ModelError)

import asyncio
import logging
import os

from governor.base import GovernorBase


CHARM_NAME = "ubuntu-governor"

logger = logging.getLogger(__name__)


class UbuntuGovernorCharm(GovernorBase):
    state = StoredState()

    def __init__(self, *args):
        super().__init__(*args)

        self.state.set_default(is_deployed=False)
        self.state.set_default(daemon_started=False)
        self.state.set_default(app_deployed=False)

        self.framework.observe(self.on.install, self.on_install)
        self.framework.observe(self.on.start, self.on_start)
        self.framework.observe(self.on.stop, self.on_stop)
        self.framework.observe(self.on.config_changed, self.on_config_changed)
        self.framework.observe(self.geh.on.unit_added, self.on_unit_added)
        self.framework.observe(self.geh.on.unit_removed, self.on_unit_removed)

    def on_install(self, event):
        # FIXME Install and configure governord
        pass

    def on_start(self, event):
        if not self._try_deploy():
            event.defer()
            return

        self.start_governord()
        self.state.is_deployed = True
        self.model.unit.status = ActiveStatus()

    def on_stop(self, event):
        # FIXME destruct deployment
        pass

    def on_unit_added(self, event):
        self.framework.breakpoint()
        logging.debug("Unit Added Event called")

    def on_unit_removed(self, event):
        self.framework.breakpoint()
        logging.debug("Unit Removed Event called")

    def on_config_changed(self, event):
        pass

    def _try_deploy(self):
        addr = self.model.config['juju_controller_address']
        if len(addr) == 0:
            addr = os.environ['JUJU_API_ADDRESSES'].split(" ")[0]
        user = self.model.config['juju_controller_user']
        password = self.model.config['juju_controller_password']
        cacert = self.model.config['juju_controller_cacert']

        if (len(addr) == 0 or len(user) == 0 or len(password) == 0 or
                len(cacert) == 0):
            self.model.unit.status = BlockedStatus(
                'Missing Juju controller configuration')
            return False

        self.model.unit.status = MaintenanceStatus("Deploying Ubuntu")

        try:
            self._deploy_ubuntu()
        except Exception as e:
            logger.error('Failed to deploy Ubuntu: {}'.format(e))
            return False

        self.model.unit.status = BlockedStatus(
            'Waiting for configuration to take place')

        return True

    def _deploy_ubuntu(self):
        # HACK: Check if we have already run the deployment step
        if 'ubuntu' in self.juju.model.applications.keys():
            return True

        kwargs = {"entity_url": "cs:ubuntu", "application_name": "ubuntu"}
        self.juju.deploy(**kwargs)
        self.juju.wait_for_deployment_to_settle(CHARM_NAME)

    def _configure_ubuntu_governor(self):
        self.juju.wait_for_deployment_to_settle(CHARM_NAME)


if __name__ == "__main__":
    # We have to silence the logger for libjuju here as it is too
    # verbose by default
    loggers_to_ignore = ['websockets.protocol',
                         'juju.client.connection',
                         'juju.model']
    for name in loggers_to_ignore:
        lg = logging.getLogger(name)
        lg.setLevel(logging.INFO)

    main(UbuntuGovernorCharm)

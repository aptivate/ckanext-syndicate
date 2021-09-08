from __future__ import print_function
import logging
import paste.script
from ckan.lib.cli import CkanCommand

import ckanext.syndicate.utils as utils


log = logging.getLogger("ckanext.syndicate")


class SyndicateCommand(CkanCommand):
    """
    Ckanext-syndicate management commands.

    Usage::
        paster syndicate [command]
    """

    summary = __doc__.split("\n")[0]
    usage = __doc__

    parser = paste.script.command.Command.standard_parser(verbose=True)
    parser.add_option(
        "-c",
        "--config",
        dest="config",
        default="development.ini",
        help="Config file to use.",
    )

    parser.add_option(
        "-t",
        "--timeout",
        default=0.1,
        type=float,
        help="Timeout between job equeues",
    )

    def command(self):
        self._load_config()

        if not len(self.args):
            print(self.usage)
        elif self.args[0] == "init":
            self._init()
        elif self.args[0] == "drop":
            self._drop()
        elif self.args[0] == "create":
            self._create()
        elif self.args[0] == "sync":
            self._sync()

    def _init(self):
        utils.reset_db()
        log.info("DB tables are reinitialized")

    def _drop(self):
        utils.drop_db()
        log.info("DB tables are removed")

    def _create(self):
        utils.create_db()
        log.info("DB tables are setup")

    def _seed(self):
        utils.seed_db()

    def _sync(self):
        pkg = None
        if len(self.args) > 1:
            pkg = self.args[1]
        utils.sync_portals(pkg, self.options.timeout)

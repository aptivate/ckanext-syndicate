import logging
from time import sleep

import ckan.model as ckan_model
import ckan.plugins.toolkit as tk
import paste.script
from ckan.lib.cli import CkanCommand
from ckan.plugins import get_plugin

log = logging.getLogger('ckanext.syndicate')


class SyndicateCommand(CkanCommand):
    """
    Ckanext-syndicate management commands.

    Usage::
        paster syndicate [command]
    """

    summary = __doc__.split('\n')[0]
    usage = __doc__

    parser = paste.script.command.Command.standard_parser(verbose=True)
    parser.add_option(
        '-c',
        '--config',
        dest='config',
        default='development.ini',
        help='Config file to use.'
    )

    def command(self):
        self._load_config()

        if not len(self.args):
            print self.usage
        elif self.args[0] == 'sync':
            self._sync()

    def _sync(self):
        plugin = get_plugin('syndicate')
        from ckanext.syndicate.plugin import get_syndicate_flag

        packages = ckan_model.Session.query(ckan_model.Package
                                            ).filter_by(state='active')
        if len(self.args) > 1:
            packages = [ckan_model.Package.get(self.args[1])]

        for package in packages:
            sleep(0.02)
            package.extras[get_syndicate_flag()] = 'true'
            print('Sending syndication signal to {}'.format(package.id))
            plugin.notify(package, 'changed')

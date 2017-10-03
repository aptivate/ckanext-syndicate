from ckan.lib.cli import CkanCommand
import paste.script
import logging
import ckan.model as ckan_model
import ckanext.syndicate.syndicate_model.model as model
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
        help='Config file to use.')

    def command(self):
        self._load_config()

        if not len(self.args):
            print self.usage
        elif self.args[0] == 'init':
            self._init()
        elif self.args[0] == 'drop':
            self._drop()
        elif self.args[0] == 'create':
            self._create()
        elif self.args[0] == 'sync':
            self._sync()

    def _init(self):
        self._drop()
        self._create()
        log.info("DB tables are reinitialized")

    def _drop(self):
        model.drop_tables()
        log.info("DB tables are removed")

    def _create(self):
        model.create_tables()
        log.info("DB tables are setup")

    def _sync(self):
        plugin = get_plugin('syndicate')
        packages = ckan_model.Session.query(ckan_model.Package).filter_by(
            state='active')
        if len(self.args) > 1:
            packages = ckan_model.Package.get(self.args[1])
        for package in packages:
            print('Sending syndication sygnal to {}'.format(package.id))
            plugin.notify(package, 'changed')

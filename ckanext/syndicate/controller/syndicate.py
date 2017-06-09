import ckan.lib.base as base
import ckan.lib.helpers as h
from ckan.common import response, c, _
import ckan.model as model
import ckan.plugins.toolkit as tk
from ckan.logic import NotAuthorized, NotFound
from sqlalchemy.orm.exc import NoResultFound
from ckanext.syndicate.plugin import syndicate_dataset

import json

abort = base.abort


class SyndicateController(base.BaseController):
    """Controller that provides syndicate admin UI."""

    def admin_user_interface(self, id):
        """Method renders syndicate log page."""
        context = {'model': model, 'session': model.Session,
                   'user': c.user}

        try:
            data_dict = {'id': id, 'include_datasets': False}
            h.check_access('organization_update', data_dict)
            c.group_dict = tk.get_action('organization_show')(context, data_dict)
        except (NotFound, NotAuthorized):
            abort(404, _('Group not found'))

        tasks = []

        try:
            tasks = model.Session.query(model.TaskStatus).join(
                model.Package, model.TaskStatus.entity_id == model.Package.id
            ).join(
                model.Group, model.Package.owner_org == model.Group.id
            ).filter(model.Group.id == c.group_dict['id']).all()
        except NoResultFound:
            pass

        return base.render(
            'organization/syndicate_interface.html',
            extra_vars={
                "group_type": "organization", 'tasks': tasks
            })

    def syndicate_log_remove(self, id):
        """Ajax call trigger this method to remove log item."""
        response.headers['Content-type'] = "application/json"

        try:
            h.check_access('package_update', {'id': id})
            model.Session.query(model.TaskStatus).filter(
                model.TaskStatus.entity_id == id).delete()
            model.Session.commit()
        except (NotFound, NotAuthorized):
            return json.dumps({"success": True})

        return json.dumps({"success": True})

    def syndicate_log_retry(self, id):
        """Ajax call trigger this method to re-syndicate log item."""
        response.headers['Content-type'] = "application/json"

        try:
            h.check_access('package_update', {"id": id})
            task = model.Session.query(model.TaskStatus).filter(
                model.TaskStatus.entity_id == id).one()
            pkg_dict = {
                'id': task.entity_id,
                'state': task.state
            }
            task.delete()
            model.Session.commit()
            syndicate_dataset(pkg_dict['id'], pkg_dict['state'])

            return json.dumps({
                'success': True,
                'msg': 'Celery task was sent to re-syndicate dataset.'
            })
        except (NotFound, NotAuthorized):
            return json.dumps({
                'success': False,
                'msg': ('''Error occurred, dataset not
                     found or you are not authorized to update it.''')
            })

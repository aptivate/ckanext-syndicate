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


def _get_tasks(group_id):
    tasks = []

    try:
        tasks = model.Session.query(model.TaskStatus).join(
            model.Package, model.TaskStatus.entity_id == model.Package.id
        ).join(
            model.Group, model.Package.owner_org == model.Group.id
        ).filter(model.Group.id == group_id).all()
    except NoResultFound:
        pass

    return tasks


def _get_task_and_delete(pkg_id):
    task = model.Session.query(model.TaskStatus).filter(
        model.TaskStatus.entity_id == pkg_id).one()
    pkg_dict = {
        'id': task.entity_id,
        'state': task.state
    }
    task.delete()
    model.Session.commit()

    return pkg_dict


def _delete_log_item(pkg_id):
    delete_item = model.Session.query(model.TaskStatus).filter(
        model.TaskStatus.entity_id == pkg_id).delete()
    model.Session.commit()

    return delete_item


class SyndicateController(base.BaseController):
    """Controller that provides syndicate admin UI."""

    def admin_user_interface(self, id):
        """Method renders syndicate log page."""
        context = {'model': model, 'session': model.Session,
                   'user': c.user}

        try:
            data_dict = {'id': id, 'include_datasets': False}
            h.check_access('organization_update', data_dict)
            c.group_dict = tk.get_action('organization_show')(
                context,
                data_dict)
        except (NotFound, NotAuthorized):
            abort(404, _('Group not found'))

        tasks = _get_tasks(c.group_dict['id'])

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
            _delete_log_item(id)
        except (NoResultFound, NotFound, NotAuthorized):
            return json.dumps({'success': False, 'msg': 'Nothing to remove'})

        return json.dumps({'success': True})

    def syndicate_log_retry(self, id):
        """Ajax call trigger this method to re-syndicate log item."""
        response.headers['Content-type'] = "application/json"

        try:
            h.check_access('package_update', {"id": id})
            pkg_dict = _get_task_and_delete(id)

            syndicate_dataset(pkg_dict['id'], pkg_dict['state'])

            return json.dumps({
                'success': True,
                'msg': 'Celery task was sent to re-syndicate dataset.'
            })
        except (NoResultFound, NotFound, NotAuthorized):
            return json.dumps({
                'success': False,
                'msg': ('''Error occurred, dataset not
                     found or you are not authorized to update it.''')
            })

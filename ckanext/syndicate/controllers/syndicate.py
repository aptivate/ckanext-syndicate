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

    tasks = model.Session.query(model.TaskStatus).join(
        model.Package, model.TaskStatus.entity_id == model.Package.id
    ).join(
        model.Group, model.Package.owner_org == model.Group.id
    ).filter(model.Group.name == group_id).all()

    return tasks


def _get_task_and_delete(pkg_id):
    try:
        task = model.Session.query(model.TaskStatus).filter(
            model.TaskStatus.entity_id == pkg_id).one()
        pkg_dict = {
            'id': task.entity_id,
            'state': task.state
        }
        task.delete()
        model.Session.commit()

        return pkg_dict
    except NoResultFound:
        raise NoResultFound


def _delete_log_item(pkg_id):
    delete_item = model.Session.query(model.TaskStatus).filter(
        model.TaskStatus.entity_id == pkg_id).delete()
    model.Session.commit()

    return delete_item


class SyndicateController(base.BaseController):
    """Controller that provides syndicate admin UI."""

    def tasks_list(self, id):
        """Method renders syndicate log page."""
        context = {'model': model, 'session': model.Session,
                   'user': c.user}

        try:
            data_dict = {'id': id, 'include_datasets': False}
            h.check_access('organization_update', data_dict)
            c.group_dict = tk.get_action('organization_show')(
                context,
                data_dict)
        except NotFound:
            abort(404, _('Group not found'))
        except NotAuthorized:
            abort(403, _('Not authorized'))

        tasks = _get_tasks(id)

        return base.render(
            'organization/tasks_list.html',
            extra_vars={
                "group_type": "organization", 'tasks': tasks
            })

    def syndicate_log_remove(self, id):
        """Ajax call trigger this method to remove log item."""
        response.headers['Content-type'] = "application/json"
        responce_data = {}
        try:
            h.check_access('package_update', {'id': id})
            is_deleted = _delete_log_item(id)
        except NotFound:
            responce_data = json.dumps({
                'success': False,
                'msg': _('Dataset not found')
            })
        except NotAuthorized:
            responce_data = json.dumps({
                'success': False,
                'msg': _('You are not authorized to update this dataset')
            })
        else:
            if is_deleted:
                responce_data = json.dumps({'success': True})
            else:
                responce_data = json.dumps({
                    'success': False,
                    'msg': _('Nothing to remove')
                })

        return responce_data

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
        except (NotFound, NotAuthorized):
            return json.dumps({
                'success': False,
                'msg': ('''Error occurred, dataset not
                     found or you are not authorized to update it.''')
            })

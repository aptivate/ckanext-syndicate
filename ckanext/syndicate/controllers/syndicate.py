import ckan.lib.base as base
import ckan.lib.helpers as h
from ckan.common import request, response, c, _
import ckan.model as model
import ckan.plugins.toolkit as tk
from ckan.logic import NotAuthorized, NotFound
from sqlalchemy.orm.exc import NoResultFound
from ckanext.syndicate.plugin import (
    syndicate_dataset,
    _get_syndicate_profiles,
    _get_syndicate_profile
)
from ckanext.syndicate.syndicate_model.syndicate_config import SyndicateConfig

import json

abort = base.abort


def _get_tasks_for_dataset(id):
    query = model.Session.query(model.TaskStatus).filter(
        model.TaskStatus.task_type == 'syndicate',
        model.TaskStatus.entity_id == id
    )

    return query


def _get_tasks(group_id=None):
    tasks = model.Session.query(model.TaskStatus)

    if group_id is not None:
        tasks.join(
            model.Package, model.TaskStatus.entity_id == model.Package.id
        ).join(
            model.Group, model.Package.owner_org == model.Group.id
        ).filter(model.Group.name == group_id)
    tasks = tasks.all()

    return tasks


def _get_task_and_delete(pkg_id, url):
    try:
        task = model.Session.query(model.TaskStatus).filter(
            model.TaskStatus.entity_id == pkg_id, model.TaskStatus.key == url).one()
        pkg_dict = {
            'id': task.entity_id,
            'state': task.state
        }
        task.delete()
        model.Session.commit()

        return pkg_dict
    except NoResultFound:
        raise NoResultFound


def _delete_log_item(pkg_id, url):
    delete_item = model.Session.query(model.TaskStatus).filter(
        model.TaskStatus.entity_id == pkg_id, model.TaskStatus.key == url).delete()
    model.Session.commit()

    return delete_item

def _delete_profile_items(remove_list):

    for profile_id in remove_list:
        delete_items = model.Session.query(SyndicateConfig).filter(
            SyndicateConfig.id == profile_id).delete()
    model.Session.commit()

def _prepare_form_dict(data_dict):
    # SYNDICATE_SETTINGS_FIELDS
    profiles_list = []
    syndicate_ids = data_dict.getall('syndicate_id')
    syndicate_urls = data_dict.getall('syndicate_url')
    syndicate_api_keys = data_dict.getall('syndicate_api_key')
    syndicate_field_ids = data_dict.getall('syndicate_field_id')
    syndicate_organizations = data_dict.getall('syndicate_organization')
    syndicate_replicate_organization = data_dict.getall('syndicate_replicate_organization')
    syndicate_authors = data_dict.getall('syndicate_author')
    syndicate_prefixs = data_dict.getall('syndicate_prefix')
    syndicate_flags = data_dict.getall('syndicate_flag')

    # check for how many profiles were submitted
    profiles_num = len(syndicate_ids)

    for x in range(0, profiles_num):
        profile_dict = {
            'syndicate_url': syndicate_urls[x],
            'syndicate_api_key': syndicate_api_keys[x],
            'syndicate_field_id': syndicate_field_ids[x],
            'syndicate_flag': syndicate_flags[x],
            'syndicate_author': syndicate_authors[x],
            'syndicate_organization': syndicate_organizations[x],
            'syndicate_prefix': syndicate_prefixs[x]
        }
        if 'syndicate_replicate_organization_{0}'.format(x) in data_dict:
            profile_dict['syndicate_replicate_organization'] = True
        else:
            profile_dict['syndicate_replicate_organization'] = False
        if syndicate_ids[x]:
            profile_dict['id'] = syndicate_ids[x]
        profiles_list.append(profile_dict)

    return profiles_list

def _unique_sync_url(url, profile_list):
    url_list = []

    for profile in profile_list:
        if profile['syndicate_url'] == url:
            url_list.append(url)

    return True if len(url_list) == 1 else False

class SyndicateController(base.BaseController):
    """Controller that provides syndicate admin UI."""
    def syndicate_config(self):
        unique_urls = True
        context = {'model': model, 'session': model.Session,
            'user': c.user}
        try:
            tk.check_access('sysadmin', context)
        except NotAuthorized:
            base.abort(401, _('Need to be system administrator to administer'))

        if request.method == 'POST':
            profiles = _prepare_form_dict(request.params)
            records_list = []


            for profile in profiles:
                unique_urls = _unique_sync_url(profile['syndicate_url'], profiles)

            if unique_urls:
                # Delete marked configs
                _delete_profile_items(request.params.getall('syndicate_remove_profiles'))

                for profile in profiles:
                    record = SyndicateConfig(**profile)

                    if 'id' in profile:
                        update_record = model.Session.query(SyndicateConfig).filter(
                            SyndicateConfig.id == profile['id'])
                        del profile['id']
                        update_record.update(profile)
                    else:
                        records_list.append(record)

                if records_list:
                    model.Session.add_all(records_list)
                model.Session.commit()
            else:
                h.flash_error("Syndicate url must be unique.")

        syndicate_profiles = _get_syndicate_profiles() if unique_urls else profiles

        return base.render(
            'admin/syndicate_config.html',
            extra_vars={
                'syndicate_profiles': syndicate_profiles,
                'count_profiles': len(syndicate_profiles)
            }
        )

    def syndicate_global_logs(self):
        context = {'model': model, 'session': model.Session,
            'user': c.user}
        try:
            tk.check_access('sysadmin', context)
        except NotAuthorized:
            base.abort(401, _('Need to be system administrator to administer'))

        tasks = _get_tasks()

        return base.render(
            'admin/syndicate_global_logs.html',
            extra_vars={
                'tasks': tasks
            })

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

    def tasks_list_dataset(self, id):
        """Method renders syndicate log page."""
        context = {'model': model, 'session': model.Session,
                   'user': c.user}

        try:
            data_dict = {'id': id}
            h.check_access('package_update', data_dict)
            c.pkg_dict = tk.get_action('package_show')(
                context,
                data_dict)
        except NotFound:
            abort(404, _('Dataset not found'))
        except NotAuthorized:
            abort(403, _('Not authorized'))

        c.pkg = model.Package.get(id)
        tasks = _get_tasks_for_dataset(c.pkg.id)

        return base.render(
            'package/syndication_logs.html',
            extra_vars={'tasks': tasks})


    def syndicate_log_remove(self):
        """Ajax call trigger this method to remove log item."""
        response.headers['Content-type'] = "application/json"
        response_data = {}
        if request.method == 'POST':
            try:
                pkg_id = request.POST.get('pkgId', '')
                synd_url = request.POST.get('syndUrl', '')
                h.check_access('package_update', {'id': pkg_id})
                is_deleted = _delete_log_item(pkg_id, synd_url)
            except NotFound:
                response_data = json.dumps({
                    'success': False,
                    'msg': _('Dataset not found')
                })
            except NotAuthorized:
                response_data = json.dumps({
                    'success': False,
                    'msg': _('You are not authorized to update this dataset')
                })
            else:
                if is_deleted:
                    response_data = json.dumps({'success': True})
                else:
                    response_data = json.dumps({
                        'success': False,
                        'msg': _('Nothing to remove')
                    })
        else:
            response_data = json.dumps({
                    'success': False,
                    'msg': _('Wrong request method type')
            })

        return response_data

    def syndicate_log_retry(self):
        """Ajax call trigger this method to re-syndicate log item."""
        response.headers['Content-type'] = "application/json"

        if request.method == 'POST':
            try:
                pkg_id = request.POST.get('pkgId', '')
                synd_url = request.POST.get('syndUrl', '')
                h.check_access('package_update', {"id": pkg_id})
                pkg_dict = _get_task_and_delete(pkg_id, synd_url)
                profile = _get_syndicate_profile(synd_url)
                syndicate_dataset(pkg_dict['id'], pkg_dict['state'], profile)

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
        else:
            return json.dumps({
                    'success': False,
                    'msg': _('Wrong request method type')
            })

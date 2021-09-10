=================
ckanext-syndicate
=================

CKAN plugin to syndicate datasets to another CKAN instance.

This plugin provides a mechanism to syndicate datasets to another instance of
CKAN. If a dataset has the ``syndicate`` flag set to ``True`` in its custom
metadata, any updates to the dataset will be reflected in the syndicated
version. Resources in the syndicated dataset are stored as the URLs of the
resources in the original. You must have the API key of a user on the target
instance of CKAN. See the Config Settings section below.

Plugins can modify data sent for syndication by implementing the action
``update_dataset_for_syndication`` and modifying the ``dataset_dict``
value. This is useful if the schemas are different between CKAN instances.

------------
Requirements
------------

* Tested with CKAN 2.9.x branch on python v3.7+
* To work over SSL, requires ``pyOpenSSL``

------------
Installation
------------

To install ckanext-syndicate:

1. Activate your CKAN virtual environment, for example::

    . /usr/lib/ckan/default/bin/activate

2. Install the ckanext-syndicate Python package into your virtual environment::

     git clone https://github.com/aptivate/ckanext-syndicate.git
     pip install -e ckanext-syndicate

3. Add ``syndicate`` to the ``ckan.plugins`` setting in your CKAN config file.

4. Run CLI command to init ``syndicate_config`` table::

     ckan db upgrade -p syndicate

--------------------------------------
Config Settings for using in .ini file
--------------------------------------

If you are using syndication to single endpoint::

    # The URL of the site to be syndicated to
    ckan.syndicate.ckan_url = https://data.humdata.org/

    # The API key of the user on the syndicated site
    ckan.syndicate.api_key = 9efdd954-c643-444a-97a1-c9c374cef861

    # The custom metadata flag used for syndication
    # (optional, default: syndicate).
    ckan.syndicate.flag = syndicate_to_hdx

    # The custom metadata field to store the syndicated dataset ID
    # on the original dataset
    # (optional, default: syndicated_id)
    ckan.syndicate.id = hdx_id

    # A prefix to apply to the name of the syndicated dataset
    # (optional, default: )
    ckan.syndicate.name_prefix = my-prefix

    # The name of the organization on the target CKAN to use when creating
    # the syndicated datasets
    # (optional, default: None)
    ckan.syndicate.organization = my-org-name

    # Try to preserve dataset's organization
    # (optional, default: false)
    ckan.syndicate.replicate_organization = boolean

    # The username whose api_key is used.
    # If the dataset already exists on the target CKAN instance, the dataset will be updated
    # only if this option is set and its creator matches this user name
    # (optional, default: None)
    ckan.syndicate.author = some_user_name

If you are using syndication to multiple endpoints, specify multiple
values for each section, divided either with space or with
newline. Only distinction is `ckan.syndicate.predicate` directive,
which specifies predicate for check, whether dataset need to be
syndicated for current profile. This option uses
`import.path:function_name` format and predicate function will be
called with syndicated package object as single argument. If function
returns falsy value, no syndication happens::

  ckan.syndicate.api_key = 4c38ad33-0d77-4213-a6da-b394f66146e7 c203782c-2c5e-410e-b47e-001818b9a674
  ckan.syndicate.author =
		      sergey
		      sergey
  ckan.syndicate.ckan_url =  http://127.0.0.1:8000
                             http://127.0.0.1:7000
  ckan.syndicate.replicate_organization = true false
  ckan.syndicate.organization = default pdp
  ckan.syndicate.predicate = __builtin__:bool ckanext.anzlic.helpers:is_pdp_dataset
  ckan.syndicate.field_id = syndicate_seed_id syndicate_pdp_id


--------------------------
Config Settings in CKAN UI
--------------------------

link to admin page ``/syndicate-config`` sysadmins are only allowed.
(.ini file config will be used if no configs are set or missing in the UI)

New feature::
    - Using Syndicate CKAN UI, you can add multiple ckan instances;
    - UI provides syndicate logs page, that show all failed syndications. You can manually run syndication for each of these logs.

---
API
---
- syndicate_individual_dataset.
  ex.: curl -X POST <CKAN_URL> -H "Authorization: <USER_API_KEY>" -d '{"id": "<DATASET_ID>", "api_key": "<REMOTE_INSTANCE_API_KEY>"}'
  Trigger syndication for individual dataset.
  Restrictions:
  - User must have `package_update` access
  - <REMOTE_INSTANCE_API_KEY> must be added as syndication endpoint to updated dataset.

- syndicate_datasets_by_endpoint.
  ex.: curl -X POST <CKAN_URL> -H "Authorization: <USER_API_KEY>" -d '{"api_key": "<REMOTE_INSTANCE_API_KEY>"}'
  Trigger syndication for all dataset that have specified endpoing among `syndication_endpoints`.
  Restrictions:
  - User must have `sysadmin` access

---
CLI
---

Mass or individual syndication can be triggered as well from command line::

  ckan syndicate sync [ID]


-----------------
Running the Tests
-----------------

To run the tests, do::

  pytest --test-ini ckan.ini

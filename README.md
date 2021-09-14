# ckanext-syndicate

CKAN plugin to syndicate datasets to another CKAN instance.

This plugin provides a mechanism to syndicate datasets to another instance of
CKAN. If a dataset has the ``syndicate`` flag set to ``True`` in its custom
metadata, any updates to the dataset will be reflected in the syndicated
version. Resources in the syndicated dataset are stored as the URLs of the
resources in the original. You must have the API key of a user on the target
instance of CKAN. See the Config Settings section below.

Plugins can modify data sent for syndication or react to before/after
syndication events by implementing the ``ISyndicate`` interface and subscibing
to corresponding signals. This is useful if the schemas are different between
CKAN instances.

### Warning

Starting from v2.0 ckanext-syndicate supports only CKAN greater or equal v2.9
and python versions starting from v3.7. In addition, it was reworked and does
not relies on actions as it was before. If you need old behavior or python2
support, switch to any of v1 tags (v1.1.0).


## Requirements

* Tested with CKAN 2.9.x branch on python v3.7+
* To work over SSL, requires ``pyOpenSSL`` (``pip install -r requirements.txt``)

## Installation


To install ckanext-syndicate:

1. Activate your CKAN virtual environment, for example::

		. /usr/lib/ckan/default/bin/activate

2. Install the ckanext-syndicate Python package into your virtual environment::

		git clone https://github.com/aptivate/ckanext-syndicate.git
		pip install -e ckanext-syndicate

3. Add ``syndicate`` to the ``ckan.plugins`` setting in your CKAN config file.


## Config Settings for using in .ini file

Syndication perfomrs dataset creation and update on the remote portal. It also
possible to syndicate the dataset to the multiple portals
simultaneously. ckanext-syndicate makes no assumptions as to how many
syndication endpoints you have and performs each synchronization separately as
if you've configured the first syndication endpoind, did a syndication, updated
configuration, did a syndication once again.

Internally, set of config option related to the particular endpoint is called
profile(``ckanext.syndicate.types.Profile``). Each profile has an ID. ID is a
part of config option: ``ckanext.syndicate.profile.<PROFILE ID>.<OPTION>`` If
you want to syndicate dataset to the two different portals, ``first`` and
``another``, configuration may look like:

	ckanext.syndicate.profile.first.ckan_url = https://data.example.com
	ckanext.syndicate.profile.another.ckan_url = https://another.example.com

Here is the full list of config options available for ``Profile``. Dont forget
to replace ``PROFILE_ID`` with the any identifier you like.

     # The URL of the site to be syndicated to
	 # (required)
     ckanext.syndicate.profile.PROFILE_ID.ckan_url = https://data.example.com

     # The API key of the user on the syndicated site
	 # (required)
     ckanext.syndicate.profile.PROFILE_ID.api_key = 9efdd954-c643-444a-97a1-c9c374cef861

     # The custom metadata flag used for syndication
     # (optional, default: syndicate).
     ckanext.syndicate.profile.PROFILE_ID.flag = syndicate_to_hdx

     # The custom metadata field to store the syndicated dataset ID
     # on the original dataset
     # (optional, default: syndicated_id)
     ckanext.syndicate.profile.PROFILE_ID.field_id = hdx_id

     # A prefix to apply to the name of the syndicated dataset
     # (optional, default: '')
     ckanext.syndicate.profile.PROFILE_ID.name_prefix = my-prefix

     # The name of the organization on the target CKAN to use when creating
     # the syndicated datasets
     # (optional, default: None)
     ckanext.syndicate.profile.PROFILE_ID.organization = my-org-name

     # Try to preserve dataset's organization
     # (optional, default: false)
     ckanext.syndicate.profile.PROFILE_ID.replicate_organization = yes

     # The username whose api_key is used.
     # If the dataset already exists on the target CKAN instance, the dataset will be updated
     # only if this option is set and its creator matches this user name
     # (optional, default: None)
     ckanext.syndicate.profile.PROFILE_ID.author = some_user_name


## Extending

Syndication can be configured for the each individual portal. There are two
types of customization: reactions on events and changes to workflow.

Reactions are usefull when you need to perform a side-effect right before or
right after the syndication. This can be achieved via the [blinker's
signals](https://pythonhosted.org/blinker/). ckanext-syndicate provides two
signals that can be imported from the ``ckanext.syndicate.signals`` (or
subscribed via
[ISignal](https://docs.ckan.org/en/latest/extensions/plugin-interfaces.html#ckan.plugins.interfaces.ISignal)
starting from CKAN v2.10):

* ``before_syndication``
* ``after_syndication``

Both signals get local dataset's ID as sender and extra keyword argument
``profile``(current syndication profile). Basic subscription looks like this:

	@after_syndication.connect
	def after_syndication_listener(package_id, **kwargs):
		profile = kwargs.get("profile")
		if profile:
			do_something(package_id, profile)

Changes to syndication workflow are made via
``ckanext.syndicate.interfaces.ISyndicate`` interface. At moment, it contains two methods:

* ``skip_syndication`` - decide, whether syndication must be performed for the
  given profile.
* ``prepare_package_for_syndication`` - update the package, before it sent to
  the remote portal. It can be really usefull if portal that you are
  syndicating to, is using different metadata schema.

Basic implementations looks like this:

	class MyPlugin(plugins.Plugin):
		plugins.implements(ISyndicate, inherit=True)

		def skip_syndication(
			self, package: model.Package, profile: Profile
		) -> bool:
			if should_be_syndicated(package):
				return False
			return True

		def prepare_package_for_syndication(
			self, package_id: str, data_dict: dict[str, Any], profile: Profile
		) -> dict[str, Any]:
			data_dict.pop("sensitive_field")
			return data_dict

Default implementation of ``skip_syndication`` prevents syndication for:

* private datasets
* datasets with the falsy value of the field, specified by
  ``ckanext.syndicate.profile.PROFILE_ID.flag`` config option(``syndicate`` by
  default)

## CLI


Mass or individual syndication can be triggered as well from command line::

	ckan syndicate sync [ID]

## Running the Tests


Install ``dev-requirements.txt``:

	pip install -r dev-requirements.txt

Run the tests:

	pytest --test-ini ckan.ini

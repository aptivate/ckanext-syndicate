try:
    import ckan.plugins.toolkit as tk

    ckanext = tk.signals.ckanext
except AttributeError:
    from blinker import Namespace

    ckanext = Namespace()

before_syndication = ckanext.signal(u"syndicate:before_syndication")
after_syndication = ckanext.signal(u"syndicate:after_syndication")

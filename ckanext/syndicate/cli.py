# -*- coding: utf-8 -*-

import click

import ckanext.syndicate.utils as utils


def get_commands():
    return [syndicate, datastore]

@click.command()
def datastore():
    print('hello')

@click.group()
def syndicate():
    pass

@syndicate.command()
def seed():
    """Fill database with syndication profiles.
    """
    utils.seed_db()


@syndicate.command()
@click.argument("id", required=False)
def sync(id):
    """Syndicate datasets to remote portals.
    """
    utils.sync_portals(id)

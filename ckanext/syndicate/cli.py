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
@click.option("-t", "--timeout", type=float, default=.1)
def sync(id, timeout):
    """Syndicate datasets to remote portals.
    """
    utils.sync_portals(id, timeout)


@syndicate.command()
def init():
    """Creates new syndication table.
    """
    utils.reset_db()
    click.secho("DB tables are reinitialized", fg='green')

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
def init():
    """Clean, initialize and fill DB with syndication profiles.

    """
    utils.reset_db()
    click.secho("DB tables are reinitialized", fg="green")


@syndicate.command()
def drop():
    """Drop all extension's tables from database.

    """
    utils.drop_db()
    click.secho("DB tables are removed", fg="green")


@syndicate.command()
def create():
    """Create tables for extension.
    """
    utils.create_db()
    click.secho("DB tables are setup", fg="green")


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

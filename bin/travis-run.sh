#!/bin/bash
set -e

pytest --ckan-ini=subdir/test.ini --cov=ckanext.syndicate ckanext/syndicate/tests

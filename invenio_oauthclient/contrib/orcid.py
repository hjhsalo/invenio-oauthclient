# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2014, 2015, 2016 CERN.
#
# Invenio is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# Invenio is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Invenio; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

"""Pre-configured remote application for enabling sign in/up with ORCID.

**Usage:**

1. Edit your configuration and add:

   .. code-block:: python

       from invenio_oauthclient.contrib import orcid

       OAUTHCLIENT_REMOTE_APPS = dict(
           orcid=orcid.REMOTE_APP,
       )

       ORCID_APP_CREDENTIALS = dict(
           consumer_key="changeme",
           consumer_secret="changeme",
       )

  Note, if you want to use the ORCID Member API, use
  ``orcid.REMOTE_MEMBER_APP`` instead of ``orcid.REMOTE_APP``.

  In case you want use sandbox:
  To use the ORCID Public API sandbox, use ``orcid.REMOTE_SANDBOX_APP``
  instead of ``orcid.REMOTE_APP``.
  To use the ORCID Member API sandbox, use ``orcid.REMOTE_SANDBOX_MEMBER_APP``.

2. Register a new application with ORCID. When registering the
   application ensure that the *Redirect URI* points to:
   ``CFG_SITE_URL/oauth/authorized/orcid/`` (note, ORCID does not
   allow localhost to be used, thus testing on development machines is
   somewhat complicated by this).


3. Grab the *Client ID* and *Client Secret* after registering the application
   and add them to your instance configuration (``invenio.cfg``):

   .. code-block:: python

       ORCID_APP_CREDENTIALS = dict(
           consumer_key="<CLIENT ID>",
           consumer_secret="<CLIENT SECRET>",
       )

4. Now go to ``CFG_SITE_URL/oauth/login/orcid/`` (e.g.
   http://localhost:4000/oauth/login/orcid/)

5. Also, you should see ORCID listed under Linked accounts:
   http://localhost:4000/account/settings/linkedaccounts/

By default the ORCID module will try first look if a link already exists
between a ORCID account and a user. If no link is found, the user is asked
to provide an email address to sign-up.

In templates you can add a sign in/up link:

.. code-block:: jinja

    <a href="{{url_for('invenio_oauthclient.login', remote_app='orcid')}}">
      Sign in with ORCID
    </a>

"""

import copy

from flask import current_app, redirect, url_for
from flask_login import current_user
from invenio_db import db

from invenio_oauthclient.models import RemoteAccount
from invenio_oauthclient.utils import oauth_link_external_id, \
    oauth_unlink_external_id

REMOTE_APP = dict(
    title='ORCID',
    description='Connecting Research and Researchers.',
    icon='',
    authorized_handler='invenio_oauthclient.handlers'
                       ':authorized_signup_handler',
    disconnect_handler='invenio_oauthclient.contrib.orcid'
                       ':disconnect_handler',
    signup_handler=dict(
        info='invenio_oauthclient.contrib.orcid:account_info',
        setup='invenio_oauthclient.contrib.orcid:account_setup',
        view='invenio_oauthclient.handlers:signup_handler',
    ),
    params=dict(
        request_token_params={'scope': '/authenticate',
                              'show_login': 'true'},
        base_url='https://pub.orcid.org/v1.2/',
        request_token_url=None,
        access_token_url='https://pub.orcid.org/oauth/token',
        access_token_method='POST',
        authorize_url='https://orcid.org/oauth/authorize',
        app_key='ORCID_APP_CREDENTIALS',
        content_type='application/json',
    )
)
"""ORCID Remote Application."""

REMOTE_MEMBER_APP = copy.deepcopy(REMOTE_APP)
"""ORCID Remote Application with member API."""

REMOTE_MEMBER_APP['params'].update(dict(
    base_url='https://api.orcid.org/',
    access_token_url='https://api.orcid.org/oauth/token',
))
"""ORCID sandbox member API."""

REMOTE_SANDBOX_MEMBER_APP = copy.deepcopy(REMOTE_APP)
"""ORCID Sandbox Remote Application with member API."""

REMOTE_SANDBOX_MEMBER_APP['params'].update(dict(
    base_url='https://api.sandbox.orcid.org/',
    access_token_url='https://api.sandbox.orcid.org/oauth/token',
    authorize_url='https://sandbox.orcid.org/oauth/authorize#show_login',
))
"""ORCID sandbox member API."""

REMOTE_SANDBOX_APP = copy.deepcopy(REMOTE_APP)
"""ORCID Sandbox Remote Application with public API."""

REMOTE_SANDBOX_APP['params'].update(dict(
    base_url='https://pub.sandbox.orcid.org/',
    access_token_url='https://pub.sandbox.orcid.org/oauth/token',
    authorize_url='https://sandbox.orcid.org/oauth/authorize#show_login',
))
"""ORCID sandbox public API."""


def account_info(remote, resp):
    """Retrieve remote account information used to find local user.

    It returns a dictionary with the following structure:

    .. code-block:: python

        {
            'user': {
                'profile': {
                    'full_name': 'Full Name',
                },
            },
            'external_id': 'github-unique-identifier',
            'external_method': 'github',
        }

    :param remote: The remote application.
    :param resp: The response.
    :returns: A dictionary with the user information.
    """
    orcid = resp.get('orcid')

    return {
        'external_id': orcid,
        'external_method': 'orcid',
        'user': {
            'profile': {
                'full_name': resp.get('name'),
            },
        },
    }


def disconnect_handler(remote, *args, **kwargs):
    """Handle unlinking of remote account.

    :param remote: The remote application.
    """
    if not current_user.is_authenticated:
        return current_app.login_manager.unauthorized()

    account = RemoteAccount.get(user_id=current_user.get_id(),
                                client_id=remote.consumer_key)
    orcid = account.extra_data.get('orcid')

    if orcid:
        oauth_unlink_external_id({'id': orcid, 'method': 'orcid'})
    if account:
        with db.session.begin_nested():
            account.delete()

    return redirect(url_for('invenio_oauthclient_settings.index'))


def account_setup(remote, token, resp):
    """Perform additional setup after user have been logged in.

    :param remote: The remote application.
    :param token: The token value.
    :param resp: The response.
    """
    with db.session.begin_nested():
        # Retrieve ORCID from response.
        orcid = resp.get('orcid')
        full_name = resp.get('name')

        # Set ORCID in extra_data.
        token.remote_account.extra_data = {
            'orcid': orcid,
            'full_name': full_name,
        }

        user = token.remote_account.user

        # Create user <-> external id link.
        oauth_link_external_id(user, {'id': orcid, 'method': 'orcid'})

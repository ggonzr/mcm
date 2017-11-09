#!/usr/bin/env python

from collections import defaultdict
from tools.locker import locker
from tools.settings import settings
from couchdb_layer.mcm_database import database
from tools.enum import Enum
from flask import request, has_request_context

class user_pack:
    """
    Class used for transmission between user representation in requests and packed user representation
    """
    def __init__(self,db=False):
        self.user_dict = user_pack.get_request_header_dictionary()
        if db:
            if  self.get_username():
                ## the user name could be not provided in case of public/ apis
                udb = database('users')
                u = udb.get( self.get_username())
                if "email" in u: #we take email from DB if user is registered, else we use ADFS
                    self.user_dict['email'] = u['email']


    @staticmethod
    def get_request_header_dictionary():
        """
        Parse flask request header and get what's in there
        """
        if not has_request_context():
            return defaultdict(lambda: None)
        user_dict = defaultdict(lambda: None, [(key.lower().replace('-','_'), value) if not key.lower().startswith('adfs-') else (key.lower()[5:], value) for (key, value) in request.headers.iteritems()])
        return user_dict

    def __getattr__(self, name):
        if name.startswith('get_'):
            return lambda : self.user_dict['_'.join(name.split('_')[1:])]
        else:
            return self.user_dict[name]

    def get_username(self):
        return self.get_login()

    def get_email(self):
        return self.email if self.email else self.remote_user

    def get_name(self):
        return self.get_firstname()

    def get_surname(self):
        return self.get_lastname()

    def get_fullname(self):
        return self.get_firstname() + " " + self.get_lastname() if self.get_firstname() and self.get_lastname() else None


roles = ('user', 'generator_contact', 'generator_convener', 'production_manager', 'administrator')
access_rights = Enum(*roles)


class authenticator:

    # roles list is a list of valid roles for a page
    __db = database('users')
    __users_roles = dict()
    __lookup_counter = defaultdict(int)

    # get the roles that are registered to a specific username
    @classmethod
    def get_user_role(cls, username, email=None):
        with locker.lock(username):
            if username not in cls.__users_roles:
                if not cls.__db.document_exists(username):
                    cls.__users_roles[username] = 'user'
                else:
                    user = cls.__db.get(username)
                    if email and ('email' not in user or user['email'] != email):
                        user['email'] = email
                        cls.__db.update(user)
                    role = None
                    while not role:
                        try:
                            role = user['role']
                        except:
                            ## how to print an error from here ?
                            user = cls.__db.get(username)
                            pass
                    cls.__users_roles[username] = user['role']
            else:
                if cls.__lookup_counter[username] == settings().get_value("user_cache_refresh_counter"):
                    if cls.__db.document_exists(username):
                        cls.__users_roles[username] = cls.__db.get(username)['role']
                    cls.__lookup_counter[username] = 0
                else:
                    cls.__lookup_counter[username] += 1
            return cls.__users_roles[username]

    @classmethod
    def get_user_role_index(cls, username, email=None):
        r = cls.get_user_role(username, email)
        return getattr(access_rights, r), r

    @classmethod
    def set_user_role(cls, username, role):
        with locker.lock(username):
            cls.__users_roles[username] = role

    @classmethod
    def can_access(cls, username, limit):
        """
        returns True, if a user matches the base role or higher
        returns False, otherwise.
        """
        role = cls.get_user_role(username)
        try:
            if getattr(access_rights, role) >= limit:
                return True
            return False
        except AttributeError:
            raise ValueError('Role {0} is not recognized'.format(role))
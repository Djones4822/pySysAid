import os
import requests
import json
import time
from urllib.parse import quote_plus
import orjson
import re
from logging import getLogger

logger = getLogger(__name__)

def has_protocol(url):
    """ Helper function to check if a url has an http protocol """
    pattern = r'^https?://'
    return bool(re.match(pattern, url))


class Client:
    """
    Simple client that logs in, stores the necessary cookies, and uses those cookies to make requests against the API.
    """
    def __init__(self, username, password, environment_name=None, base_url=None, cookie_dir='.', cookie_file_name=None):

        if (environment_name is None and base_url is None) or (environment_name and base_url):
            raise ValueError('Must provide either environment_name or base_url, but not both')
        
        self.username = username
        self.password = password
        self.__cookie_dir = cookie_dir
        if not os.path.isdir(cookie_dir):
            logger.warning('cookie_dir not found, creating...')
            os.makedirs(cookie_dir)
            logger.info('successfully created cookie directory')

        if cookie_file_name:
            self.__cookie_path = os.path.join(self.__cookie_dir, cookie_file_name)
        else:
            self.__cookie_path = os.path.join(self.__cookie_dir, f"{self.username}_cookies.json")

        if environment_name:
            self.base_url = f"https://{environment_name}.sysaidit.com/api/v1/"
        
        if base_url:
            if not has_protocol(base_url):
                raise ValueError('base_url must include the http protocol (http:// or https://)')
            self.base_url = f"{base_url.strip('/')}/api/v1/"

        self.cookies = self.load_cookies()

        if not self.cookies:
            self.login()

    @property
    def cookie_path(self):
        return self.__cookie_path

    def load_cookies(self):
        try:
            with open(self.__cookie_path, "r") as file:
                cookies = json.load(file)
                return cookies
        except FileNotFoundError:
            return None

    def save_cookies(self, cookies):
        with open(self.__cookie_path, "w") as file:
            json.dump(cookies, file)

    def login(self):
        url = f"{self.base_url}login"
        payload = {"user_name": self.username, "password": quote_plus(self.password)}
        headers = { 'Content-Type': 'application/json' }

        while True:
            response = requests.post(url, data=orjson.dumps(payload), headers=headers)

            if response.status_code == 200:
                self.cookies = response.cookies.get_dict()
                self.save_cookies(self.cookies)
                break
            elif response.status_code == 429:
                print("Too many login requests. Retrying in 5 minutes.")
                time.sleep(300)
            else:
                response.raise_for_status()

    def make_request(self, method, endpoint, params=None, body=None, retry=False):
        """ 
        Issues a request given the parameters. Will attempt 1 retry if a 401 response (UnAuthorized)
        after trying to log in again.
        """
        headers = { 'Content-Type': 'application/json' }
        if body:
            if not isinstance(body, str):
                body = orjson.dumps(body)
        url = self.base_url + endpoint
        if method.lower() == 'get':
            response = requests.get(url, params=params, cookies=self.cookies, headers=headers)
        elif method.lower() == 'post':
            response = requests.post(url, params=params, data=body, cookies=self.cookies, headers=headers)
        elif method.lower() == 'put':
            response = requests.put(url, params=params, data=body, cookies=self.cookies, headers=headers)
        elif method.lower() == 'delete':
            response = requests.delete(url, params=params, cookies=self.cookies, headers=headers)
        else:
            raise ValueError(f'Unknown method: {method}')

        if response.status_code == 200:
            try:
                return response.json()
            except Exception as e:
                return response.text
        elif response.status_code == 401:
            if not retry:
                self.login()
                return self.make_request(method, endpoint, body, True)
            else:
                print(response.text)
                raise Exception('Could not make authorized request')
        else:
            print(response.text)
            raise Exception('Could not make authorized request')

    def get_sr(self, sr_id):
        # TODO: Implement a Service Record Object
        endpoint = f'sr/{sr_id}'
        return self.make_request('get', endpoint)

    def get_sr_list(self, view=None, fields=None, ids=None, type=None, offset=None, limit=None, filters=None, sort=None, dir=None):
        params = {k: v for k, v in locals().items() if v is not None}
        endpoint = 'sr'
        return self.make_request('get', endpoint, params=params)
        
    def update_sr(self, id, fields: dict):
        info_payload = []
        for k,v in fields.items():
            info_payload.append({'key':k, 'value':v})
        payload =  {
          'id': id,
          'info': info_payload
        }
        endpoint = f'sr/{id}'
        return self.make_request('put', endpoint, body=payload)

    def search_srs(self, query=None, view=None, fields=None, type=None, offset=None, limit=None, filters=None, sort=None, dir=None):
        params = {k: v for k, v in locals().items() if v is not None}
        endpoint = f'sr/search' 
        return self.make_request('get', endpoint, params=params)
    
    def count_srs(self, filters=None):
        raise NotImplementedError

    def close_sr(self, id):
        raise NotImplementedError

    def get_sr_template(self, view=None, fields=None, type=None, template_id=None):
        raise NotImplementedError

    def create_sr(self, data, view=None, type=None, template_id=None):
        if type not in ('incident', 'request', 'problem', 'change', 'all'):
            raise ValueError(f'SR type must be one of: incident, request, problem, change, or all. Not {type}')
        raise NotImplementedError
    
    def add_sr_link(self, id, name, link):
        raise NotImplementedError
    
    def delete_sr_link(self, id, name):
        raise NotImplementedError
    
    def add_sr_attachment(self, id, data):
        raise NotImplementedError
    
    def delete_sr_attachment(self, id, file_id):
        raise NotImplementedError

    def delete_sr(self, ids):
        raise NotImplementedError
    
    def add_sr_activity(self, id, user_id, from_time, to_time, description):
        raise NotImplementedError
    
    def send_sr_message(self, id, method, add_as_attachment, add_as_details, file_data, message_from_user_id, 
                        message_to_users, message_cc_users, message_subject, message_body):
        # TODO: implement a message object
        raise NotImplementedError

    def get_users_list(self, view=None, fields=None, type=None, offset=None, limit=None):
        params = {k: v for k, v in locals().items() if v is not None}
        endpoint = f'users' 
        return self.make_request('get', endpoint, params=params)

    def get_user(self, id, view=None, fields=None):
        # TODO: implement a user object
        params = {k: v for k, v in locals().items() if v is not None}
        endpoint = f'users/{id}' 
        return self.make_request('get', endpoint, params=params)

    def search_users(self, query=None, view=None, fields=None, type=None, offset=None, limit=None, sort=None, dir=None):
        raise NotImplementedError

    def get_user_photo(self, user_id):
        raise NotImplementedError

    def upload_user_photo(self, user_id, photo):
        raise NotImplementedError

    def get_user_permissions(self, user_id):
        raise NotImplementedError
    
    def get_filters_list(self, view=None, fields=None, offset=None, limit=None):
        raise NotImplementedError

    def get_filter(self, id, view=None, offset=None, limit=None):
        raise NotImplementedError
    
    def get_action_items(self, view=None, fields=None, type=None, archive=None, ids=None, 
                         staticFilterId=None, query=None, offset=None, limit=None, sort=None, dir=None):
        # TODO: implement an action item object
        raise NotImplementedError

    def count_action_items(self, view, fields, type, archive, ids, staticFilterId, query):
        raise NotImplementedError

    def approve_action_item(self, id):
        raise NotImplementedError

    def reject_action_item(self, id):
        raise NotImplementedError

    def complete_action_item(self, id):
        raise NotImplementedError

    def reopen_action_item(self, id):
        raise NotImplementedError
    
    def get_assets_list(self, view, fields, type, offset, limit):
        raise NotImplementedError

    def get_asset(self, id, view, fields):
        # TODO: Implement an asset object
        raise NotImplementedError

    def search_assets(self, query, view, fields, offset, limit):
        raise NotImplementedError
    
    def get_all_lists(self, entity, fields, offset, limit):
        raise NotImplementedError

    def get_list(self, id, entity, entityId, entityType, fields, offset, limit, keyField):
        # TODO: Implement a list object
        raise NotImplementedError

    def list_addon_applications(self):
        # TODO: Implement an Addon Object
        raise NotImplementedError

    def get_addon_parameters(self, addon_name):
        raise NotImplementedError

    def update_addon_parameters(self, addon_name, parameters):
        raise NotImplementedError

    def test_addon_connection(self, addon_name):
        raise NotImplementedError

    def get_ci_list(self, view, fields, ids, offset, limit, filters, sort, dir, supportBarcode):
        # TODO: Implement a CI object
        raise NotImplementedError

    def update_ci(self, id, data):
        raise NotImplementedError

    def get_ci_types(self, supportBarcode):
        raise NotImplementedError

    def get_ci_view(self, ciTypeId, view):
        raise NotImplementedError

    def get_ci_relation_types(self, ):
        raise NotImplementedError

    def get_ci_relation(self, ciId):
        raise NotImplementedError

    def create_ci_relations(self, ciId, relations):
        raise NotImplementedError

    def delete_ci_relations(self, ciId):
        raise NotImplementedError

    def get_rb_translated_keys(self, locale):
        raise NotImplementedError

    def get_ldap_domains(self):
        raise NotImplementedError

    def get_password_services_permission(self):
        raise NotImplementedError

    def get_security_question(self, method, user_id):
        raise NotImplementedError

    def unlock_account(self, user_id, answers):
        raise NotImplementedError

    def reset_password(self, user_id, answers):
        raise NotImplementedError

    def update_password(self, user_id, token):
        raise NotImplementedError
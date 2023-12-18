from ast import Attribute
import os
from typing import List, Literal
import requests
import json
import time
from urllib.parse import quote_plus
import orjson
import re
from logging import getLogger

from pysysaid.service_request import SRAttribute, ServiceRequest

logger = getLogger(__name__)

PROTOCOL_RE_PATTERN = r'^https?://'
ENDPOINT_PARAM_IGNORE = ['self', 'format']

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
            if not bool(re.match(PROTOCOL_RE_PATTERN, base_url)):
                raise ValueError('base_url must include the http protocol (http:// or https://)')
            self.base_url = f"{base_url.strip('/')}/api/v1/"

        self.cookies = self.load_cookies()

        if not self.cookies:
            self.login()

    def __get_params(self, params):
        return {k: v for k, v in params.items() if v is not None and k not in ENDPOINT_PARAM_IGNORE}
    
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

    def make_request(self, method, endpoint, params=None, body=None, retry=False, files=None):
        """ 
        Issues a request given the parameters. Will attempt 1 retry if a 401 response (UnAuthorized)
        after trying to log in again.
        """
        headers = { 'Content-Type': 'application/json' }
        if body:
            if not isinstance(body, str):
                body = orjson.dumps(body)
        url = self.base_url + endpoint

        req_params = {'cookies': self.cookies, 'headers': headers}
        if params:
            req_params['params'] = params
        if body:
            req_params['body'] = body
        if files:
            req_params['files'] = files

        if method.lower() == 'get':
            fn = requests.get
        elif method.lower() == 'post':
            fn = requests.post
        elif method.lower() == 'put':
            fn = requests.put
        elif method.lower() == 'delete':
            fn = requests.delete
        else:
            raise ValueError(f'Unknown method: {method}')
        
        response = fn(url, **req_params)

        if response.status_code == 200:
            try:
                return response.json()
            except Exception as e:
                return response.text
        elif response.status_code == 401:
            if not retry:
                self.login()
                return self.make_request(method, endpoint, params, body, True, files)
            else:
                print(response.text)
                raise Exception('Could not make authorized request')
        else:
            print(response.text)
            raise Exception('Could not make authorized request')

    def get_sr(self, sr_id, format: Literal['dict', 'object'] = 'object') -> ServiceRequest|dict|None:
        endpoint = f'sr/{sr_id}'
        resp = self.make_request('get', endpoint)
        if isinstance(resp, list):
            if len(resp):
                sr = resp[0]
                if format == 'object':
                    return ServiceRequest.from_response(sr)
                else:
                    return sr

    def get_sr_list(self, view=None, fields=None, ids=None, type=None, offset=None, limit=None, filters=None, 
                    sort=None, dir=None, format: Literal['dict', 'object'] = 'object') -> List[ServiceRequest|dict]|None:
        params = self.__get_params(locals())
        endpoint = 'sr'
        resp = self.make_request('get', endpoint, params=params)
        if isinstance(resp, list):
            if len(resp):
                if format == 'object':
                    return [ServiceRequest.from_response(sr) for sr in resp]
                else:
                    return resp
    
    def search_srs(self, query=None, view=None, fields=None, type=None, offset=None, limit=None, filters=None,
                   sort=None, dir=None, format: Literal['dict', 'object'] = 'object') -> List[ServiceRequest|dict]|None:
        params = self.__get_params(locals())
        endpoint = f'sr/search'
        resp = self.make_request('get', endpoint, params=params)
        if isinstance(resp, list):
            if len(resp):
                if format == 'object':
                    return [ServiceRequest.from_response(sr) for sr in resp]
                else:
                    return resp
        
    def update_sr(self, id, info: List[dict|SRAttribute]):
        info_payload = []
        for field in info:
            if isinstance(field, SRAttribute):
                info_payload.append({'key': field.key, 'value': field.value})
            elif isinstance(field, dict):
                info_payload.append({'key':field['key'], 'value':field['value']})
            else:
                TypeError(f'Info element must be a dict with keys `key` and `value` or an `SRAttribute`, not {type(field)}')

        payload =  {
          'id': id,
          'info': info_payload
        }
        endpoint = f'sr/{id}'
        return self.make_request('put', endpoint, body=payload)
    
    def count_srs(self, filters=None):
        params = self.__get_params(locals())
        endpoint = f"sr/count"
        return self.make_request('get', endpoint, params=params)

    def close_sr(self, id, solution):
        if not isinstance(solution, str):
            raise TypeError('solution must be a string')
        endpoint= f'sr/{id}/close'
        payload = {'solution': solution}
        return self.make_request('post', endpoint, body=payload)

    def get_sr_template(self, view=None, fields=None, type=None, template_id=None):
        params = self.__get_params(locals())
        endpoint = f"sr/template"
        return self.make_request('get', endpoint, params=params)

    def create_sr(self, info, view=None, sr_type='incident', template_id=None, format: Literal['dict', 'object'] = 'object') -> ServiceRequest|dict:
        """
        Method for creating a service request. 
        
        See documentatin available at: https://documentation.sysaid.com/docs/rest-api-details#create-service-request
        """
        INFO_ERROR = 'info must be a list of dictionaries with `key` and `value` fields'
        if sr_type not in ('incident', 'request', 'problem', 'change', 'all'):
            raise ValueError(f'SR type must be one of: incident, request, problem, change, or all. Not {sr_type}')
        if not isinstance(info, list):
            raise TypeError(INFO_ERROR)
        for i, data in enumerate(info):
            if not isinstance(data, dict):
                raise TypeError(INFO_ERROR)
            if not data.get('key'):
                raise KeyError(f'Error on info element {i}: missing key `key`')
            if not data.get('value'):
                raise KeyError(f'Error on info element {i}: missing key `key`')
            
            key = data.get('key')
            val = data.get('value')
            if key == 'notes':
                if not isinstance(val, dict):
                    raise TypeError('value for `notes` must be a dictionary with keys "userName", "createDate", and "text"')
                if not isinstance(val['createDate'], int):
                    raise TypeError('createDate note element must be an integer representing UTC date in milliseconds')
            elif key == 'due_date':
                if not isinstance(val, int):
                     raise TypeError('due_date element must be an integer representing UTC date in milliseconds')
            
        params = self.__get_params(locals())
        del params['info']  # remove the info which is sent as the body

        endpoint = 'sr'
        resp = self.make_request('post', endpoint, params=params, body=info)
        if isinstance(resp, dict):
            if format == 'dict':
                return resp
            return ServiceRequest.from_response(resp)
        raise TypeError(f'Unknown response type: {type(resp)}')
    
    def delete_sr(self, ids):
        if isinstance(ids, (list, tuple)):
            ids = ','.join(ids)
        params = {'ids': ids}
        endpoint = 'sr'
        return self.make_request('delete', endpoint, params=params)
    
    def add_sr_link(self, id, name, link):
        endpoint = f'sr/{id}/link'
        payload = {'name': name, 'link': link}
        return self.make_request('post', endpoint, body=payload)
    
    def delete_sr_link(self, id, name):
        endpoint = f'sr/{id}/link'
        payload = {'name': name}
        return self.make_request('delete', endpoint, body=payload)
    
    def add_sr_attachment(self, id, file_path=None, file_data=None):
        if file_path:
            files = {'file': open(file_path, 'rb')}
        else:
            files = {'file': file_data}

        endpoint = f'sr/{id}/attachment'
        return self.make_request('post', endpoint, files=files)
    
    def delete_sr_attachment(self, id, file_id):
        endpoint = f'sr/{id}/attachment'
        payload = {'fileId': file_id}
        return self.make_request('delete', endpoint, body=payload)
    
    def add_sr_activity(self, id, user_id: str, from_time: str, to_time: str, description:str):
        payload = self.__get_params(locals())
        del payload['id']
        endpoint = f'sr/{id}/activity'
        return self.make_request('post', endpoint, body=payload)

    def delete_sr_activity(self, id, activity_id):
        payload = {'id': activity_id}
        endpoint = f'sr/{id}/activity'
        return self.make_request('delete', endpoint, body=payload)
    
    def send_sr_message(self, id, message_from_user_id, message_to_users, message_cc_users, message_subject, message_body, 
                        method='email', file_path=None, add_details=True, add_attachment=True):
        """
        Sends a message using the method provided (defaults to email). 

        The IDs of the users in the To and CC fields must be a comma-separated string, with users IDs. If there's a group, 
        the group ID should be surrounded by [ ].

        See documentation at: https://documentation.sysaid.com/docs/rest-api-details#send-message-from-service-request
        """
        # TODO: implement a message object
        params = {'method': method,
                  'addAttachmentToSr': add_attachment,
                  'addSrDetails': add_details}
        endpoint = f'sr/{id}/message'
        message = {
            'fromUserId': message_from_user_id,
            'toUsers': message_to_users,
            'ccUsers': message_cc_users,
            'msgSubject': message_subject,
            'msgBody': message_body
        }
        payload = {
            'message': message
        }
        files = None
        if file_path:
            files = {'file': open(file_path, 'rb')}

        return self.make_request('post', endpoint, params=params, body=payload, files=files)

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
import requests
import json
import time
from urllib.parse import quote_plus
import orjson

class SysAidAPI:
    """
    Simple client that logs in, stores the necessary cookies, and uses those cookies to make requests against the API.
    """
    def __init__(self, username, password, environment_name):
        self.username = username
        self.password = password
        self.environment_name = environment_name
        self.base_url = f"https://{environment_name}.sysaidit.com/api/v1/"
        self.cookies = self.load_cookies()

        if not self.cookies:
            self.login()

    def load_cookies(self):
        try:
            with open(f"{self.username}_cookies.json", "r") as file:
                cookies = json.load(file)
                return cookies
        except FileNotFoundError:
            return None

    def save_cookies(self, cookies):
        with open(f"{self.username}_cookies.json", "w") as file:
            json.dump(cookies, file)

    def login(self):
        url = self.base_url + "login"
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

    def make_request(self, method, endpoint, body=None, retry=False):
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
            response = requests.get(url, cookies=self.cookies, headers=headers)
        elif method.lower() == 'post':
            response = requests.post(url, data=body, cookies=self.cookies, headers=headers)
        elif method.lower() == 'put':
            response = requests.put(url, data=body, cookies=self.cookies, headers=headers)
        elif method.lower() == 'delete':
            response = requests.delete(url, cookies=self.cookies, headers=headers)

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
        endpoint = 'sr/' + str(sr_id)
        return self.make_request('get', endpoint)

    def get_sr_list(self, **kwargs):
        endpoint = 'sr?' + '&'.join([f'{str(k)}={str(v)}' for k,v in kwargs.items()])
        return self.make_request('get', endpoint)
        
    def update_fields(self, id, field_dict):
        info_payload = []
        for k,v in field_dict.items():
            info_payload.append({'key':k, 'value':v})
        payload =  {
          'id': id,
          'info': info_payload
        }
        endpoint = 'sr/' + str(id)
        return self.make_request('put', endpoint, payload)

    def search_srs(self, query, **kwargs):
        endpoint = f'sr/search?query={query}&' + '&'.join([f'{str(k)}={str(v)}' for k,v in kwargs.items()])
        return self.make_request('get', endpoint)

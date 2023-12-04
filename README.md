# pySysAid
Simple python library for interacting with the SysAid REST API.

**Current Version**: 0.0.1

*Note:* This is a first pass to do what I needed it to do, released on GH so I can install it into virtual envs easily where needed. This has the barebone functionality for you to make your own requests as needed, and a few helper functions.

I will revisit this when I have time to add functionality, improve the codebase, add tests, etc. If you'd like to contribute please make a PR :)

## SysAid REST Documention

https://documentation.sysaid.com/docs/rest-api-details

You will need this! Note that the methods for each endpoint are not specified for some reason, you'll have to interpret what the endpoint is doing to know which method you want. For example, retrieving any info is probably a `GET` request, updating an SR is probably a `PUT` request, and creating an SR is probably a `POST` request!

## Usage

Install from github with:

`python -m pip install git+https://github.com/Djones4822/pySysAid`

Then, in your project import with

```python
from pysysaid import Client
```

Create a connection by instantiating a client object

```python
un = 'myusername'
pw = 'mypassword'
env_name = 'my_env_name'  # this is provided to you by SysAid once your instance is created
client = Client(username=username, password=password, environment_name=env_name)
```

Upon instantiation, the client will log in. I don't believe SSO works, so you need to create a SysAid Administrator with mobile access. After logging in, the library will create a file in the current working directory called `{username}_cookies.json` where the necessary cookies are stored. These get written to a file for easy re-use between runs, as the SysAid API only allows 2 logins per 5 minutes. 

Once you have the client you can then use the few helper functions I've added, or issue your own requests:

```python
# Helper Functions:

client.get_sr(sr_id=1)
client.get_sr_list(**kwargs)  # see the sysaid rest api documentation for valid fields
client.search_srs(**kwargs)   # see the sysaid rest api documentation for valid fields
client.update_fields(id=1, field_dict={'sr_status': 'Open'})  # see the sysaid rest api documentatino for valid fields

# Or execute your own request
client.make_request('get', 'sr/1')
```

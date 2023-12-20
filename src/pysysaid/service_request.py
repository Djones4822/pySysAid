from logging import getLogger
from typing import TYPE_CHECKING, Any, List, Optional
if TYPE_CHECKING:
    from pysysaid.client import Client

logger = getLogger(__name__)


class SRAttribute:
    def __init__(self, data):
        self.__data = data
    
    @property
    def value(self):
        return self.__data['value']
    
    @value.setter
    def value(self, value):
        self.__data['value'] = value
    
    @property
    def value_class(self):
        return self.__data['valueClass']
    
    @property
    def value_caption(self):
        return self.__data['valueCaption']
    
    @property
    def key_caption(self):
        return self.__data['keyCaption']
    
    @property
    def key(self):
        return self.__data['key']
    
    def __repr__(self):
        return self.__data
    
    def __str__(self):
        return f"{self.key}: {self.value}"
    
    def __getitem__(self, key):
        return self.__data[key]


class ServiceRequest:
    def __init__(self, id: int, can_update=True, can_delete=False, can_archive=False, has_children=False, info=[], client: Optional['Client'] =None, auto_commit=True):
        self.__id = id
        self.__can_update = can_update
        self.__can_delete = can_delete
        self.__can_archive = can_archive
        self.__has_children = has_children
        self.__info = {}
        self.__client = client
        self.__auto_commit = auto_commit
        self.__pending_commits = {}

        if client is None:
            logger.warning('No client provided, SR is read-only')

        for info_dict in info:
            self.__info[info_dict['key']] = SRAttribute(info_dict)

    def __getattribute__(self, __name: str) -> Any:
        "Fetches an attribute either from the class spec or from within the info body"
        try:
            return super().__getattribute__(__name)
        except AttributeError:
            attr = self.__info.get(__name)
            if attr:
                return attr.value
            raise AttributeError(f"SR {self.id} has no attribute '{__name}'. If the SR was created with limited fields, try re-creating without using the fields paramter")

    def __setattr__(self, name, value):
        if name in self.__info.keys():
            if not self.client:
                raise AttributeError('SR is read-only, cannot modify values')
            if self.__auto_commit:
                self.client.update_sr(self.__id, [{'key': name, 'value': value}])
            else:
                old = self.__info[name].value
                self.__info[name].value = value
                self.__pending_commits[name] = {'old': old, 'new': value}
        else:
            super().__setattr__(name, value)
        return True

    @classmethod
    def from_response(cls, data: dict):
        return cls(id=int(data['id']),
                   can_update=data['canUpdate'], 
                   can_delete=data['canDelete'], 
                   can_archive=data['canArchive'], 
                   has_children=data['hasChildren'], 
                   info=data['info'])
    
    @property
    def id(self):
        return self.__id

    @property
    def can_update(self):
        return self.__can_update
    
    @property
    def can_delete(self):
        return self.__can_delete
    
    @property
    def can_archive(self):
        return self.__can_archive
    
    @property
    def has_children(self):
        return self.__has_children
    
    @property
    def client(self):
        return self.__client
    
    @property
    def pending_commits(self):
        return self.__pending_commits

    @property
    def auto_commit(self):
        return self.__auto_commit
    
    @auto_commit.setter
    def auto_commit(self, state:bool):
        if state == self.__auto_commit:
            return 
        
        if state and self.__pending_commits:
            raise ValueError('Cannot set auto_commit=True while pending commits. Use `commit()` or `rollback()` to clear pending changes.')
        
        self.__auto_commit = state

    def set_client(self, value):
        if self.__client:
            raise AttributeError('Client is already set')
        self.__client = value
        logger.info('Client has been set, SR can now be modified')

    def commit(self):
        if not self.client:
                raise AttributeError('SR is read-only, cannot modify values')
        if self.__auto_commit:
            logger.warning('SR is set to auto-commit, no pending changes.')
        if not self.__pending_commits:
            logger.warning('No pending commits.')
        
        info: List[dict[str, Any]] = [{'key': k, 'value': v['new']} for k, v in self.__pending_commits.items()]
        try:
            self.client.update_sr(self.__id, info)
        except Exception as e:
            logger.error('Could not perform update. Use `rollback()` to revert pending changes')
        return True

    def rollback(self, field:Optional[str]=None):
        if self.__auto_commit:
            logger.warning('SR is set to auto-commit, no pending changes.')
        if not self.__pending_commits:
            logger.warning('No pending commits.')

        if field: 
            if field not in self.__info.keys():
                raise AttributeError(f'Field {field} not present in SR fields')
            if field not in self.__pending_commits.keys():
                raise AttributeError(f'Field {field} does not having pending commits to rollback')

            old = self.__pending_commits[field]['old']
            self.__info[field].value = old
            return True

        if not self.__pending_commits:
            logger.warning('No pending commits to rollback')
        
        for field, values in self.__pending_commits.items():
            old = values['old']
            self.__info[field].value = old
        return True
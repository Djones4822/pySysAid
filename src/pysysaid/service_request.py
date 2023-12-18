from typing import Any
from logging import getLogger
from typing import TYPE_CHECKING, Any, Optional
if TYPE_CHECKING:
    from pysysaid.client import Client

logger = getLogger(__name__)


class SRAttribute:
    def __init__(self, data):
        self.__data = data
    
    @property
    def value(self):
        return self.__data['value']
    
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
    def __init__(self, id: int, can_update=True, can_delete=False, can_archive=False, has_children=False, info=[], client: Optional['Client'] =None):
        self.__id = id
        self.__can_update = can_update
        self.__can_delete = can_delete
        self.__can_archive = can_archive
        self.__has_children = has_children
        self.__info = {}
        self.__client = client

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

    def set_client(self, value):
        if self.__client:
            raise AttributeError('Client is already set')
        self.__client = value
        logger.info('Client has been set, SR can now be modified')

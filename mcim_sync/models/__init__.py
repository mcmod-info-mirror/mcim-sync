from typing import Union
from pydantic import BaseModel

class ProjectDetail(BaseModel):
    id: Union[int, str]
    name: str
    version_count: int
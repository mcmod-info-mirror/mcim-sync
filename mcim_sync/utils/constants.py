from enum import Enum
from typing import Union
from pydantic import BaseModel


class Platform(Enum):
    CURSEFORGE = "curseforge"
    MODRINTH = "modrinth"

class ProjectDetail(BaseModel):
    id: Union[int, str]
    name: str
    version_count: int
from sync.modrinth import sync_project
from sync.curseforge import sync_mod
from models import ProjectDetail

project_id = "OpqpD8K2"
modId = 1052133

def test_sync_project():
    result = sync_project(project_id)
    assert isinstance(result, ProjectDetail)

def test_sync_mod():
    result = sync_mod(modId)
    assert isinstance(result, ProjectDetail)
from sync.modrinth import sync_project
from sync.curseforge import sync_mod, sync_categories
from models import ProjectDetail
from models.database.curseforge import Category

project_id = "OpqpD8K2"
modId = 1052133

def test_sync_project():
    result = sync_project(project_id)
    assert isinstance(result, ProjectDetail)

def test_sync_mod():
    result = sync_mod(modId)
    assert isinstance(result, ProjectDetail)

def test_sync_categories():
    result = sync_categories(gameId=432)
    assert isinstance(result, list)
    assert all(Category(**item) for item in result)
    assert len(result) > 0
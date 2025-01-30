from mcim_sync.sync.modrinth import (
    sync_project,
    sync_categories,
    sync_loaders,
    sync_game_versions,
)
from mcim_sync.utils.constans import ProjectDetail

project_id = "OpqpD8K2"


def test_sync_project():
    result = sync_project(project_id)
    assert isinstance(result, ProjectDetail)


def test_sync_categories():
    result = sync_categories()
    assert isinstance(result, list)
    assert len(result) > 0


def test_sync_loaders():
    result = sync_loaders()
    assert isinstance(result, list)
    assert len(result) > 0


def test_sync_game_versions():
    result = sync_game_versions()
    assert isinstance(result, list)
    assert len(result) > 0


from mcim_sync.sync.curseforge import sync_mod, sync_categories
from mcim_sync.utils.constans import ProjectDetail


modId = 1052133

def test_sync_mod():
    result = sync_mod(modId)
    assert isinstance(result, ProjectDetail)

def test_sync_categories():
    result = sync_categories(gameId=432)
    assert isinstance(result, list)
    assert len(result) > 0
from mcim_sync.tasks.modrinth import (
    sync_modrinth_queue,
    refresh_modrinth_with_modify_date,
)
from mcim_sync.tasks.curseforge import (
    sync_curseforge_queue,
    refresh_curseforge_with_modify_date,
    refresh_curseforge_categories,
)


def test_sync_modrinth_queue():
    assert sync_modrinth_queue()


def test_sync_curseforge_queue():
    assert sync_curseforge_queue()


def test_refresh_modrinth_with_modify_date():
    assert refresh_modrinth_with_modify_date()


def test_refresh_curseforge_with_modify_date():
    assert refresh_curseforge_with_modify_date()


def test_refresh_curseforge_categories():
    assert refresh_curseforge_categories()

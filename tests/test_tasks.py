from pytest import mark

from mcim_sync.tasks.modrinth import (
    sync_modrinth_queue,
    refresh_modrinth_with_modify_date,
    sync_modrinth_by_search
)
from mcim_sync.tasks.curseforge import (
    sync_curseforge_queue,
    refresh_curseforge_with_modify_date,
    refresh_curseforge_categories,
    sync_curseforge_by_search
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

@mark.skip(reason="不在 ci 测试全量抓取，耗时过久")
@mark.usefixtures("insert_recent_modrinth_project")
def test_sync_modrinth_by_search():
    assert sync_modrinth_by_search()

@mark.skip(reason="不在 ci 测试全量抓取，耗时过久")
@mark.usefixtures("insert_recent_curseforge_mod")
def test_sync_curseforge_by_search():
    assert sync_curseforge_by_search(class_ids=[6]) # 只测试 Mods 类别的搜索功能，免得耗时太久
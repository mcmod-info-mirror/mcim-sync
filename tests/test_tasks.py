from sync.tasks import (
    sync_modrinth_queue,
    sync_curseforge_queue,
    refresh_modrinth_with_modify_date,
    refresh_curseforge_with_modify_date,
    # send_statistics_to_telegram
)

def test_sync_modrinth_queue():
    assert sync_modrinth_queue()

def test_sync_curseforge_queue():
    assert sync_curseforge_queue()

def test_refresh_modrinth_with_modify_date():
    assert refresh_modrinth_with_modify_date()

def test_refresh_curseforge_with_modify_date():
    assert refresh_curseforge_with_modify_date()
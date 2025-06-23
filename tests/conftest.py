import pymongo
import httpx
import json
import pytest
import os

if not os.path.exists("config.json"):
    config: dict = json.loads(os.environ.get("CONFIG"))
else:
    config = json.load(open("config.json", "r", encoding="utf-8"))
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3",
    "Accept": "application/json",
    "x-api-key": config.get("curseforge_api_key", ""),
}

mongo_client = pymongo.MongoClient(
    host=config["mongodb"]["host"],
    port=config["mongodb"]["port"],
)

mongo_db = mongo_client[config["mongodb"]["database"]]


@pytest.fixture(scope="session")
def insert_recent_curseforge_mod():
    # 排除 Bukkit Plugins
    class_info = [
        {"id": 4546, "name": "Customization"},
        {"id": 4559, "name": "Addons"},
        {"id": 12, "name": "Resource Packs"},
        {"id": 6, "name": "Mods"},
        {"id": 4471, "name": "Modpacks"},
        {"id": 17, "name": "Worlds"},
        {"id": 6552, "name": "Shaders"},
        {"id": 6945, "name": "Data Packs"},
    ]
    for cls in class_info:
        classId = cls["id"]
        class_name = cls["name"]
        res = httpx.get(
            "https://api.curseforge.com/v1/mods/search",
            params={
                "gameId": "432",
                "classId": classId,
                "sortField": "11",
                "sortOrder": "desc",
                "index": 60,
                "pageSize": 1,
            },
            headers=headers,
        ).json()

        mod = res["data"][0]

        mod["_id"] = mod["id"]
        del mod["id"]
        mongo_db["curseforge_mods"].insert_one(mod)
        print(
            f"Inserted recent curseforge mods for classId: {classId}, name: {class_name}, modid {mod['_id']}, name: {mod['name']}"
        )

    yield

    # 清理插入的测试数据
    mongo_db["curseforge_mods"].delete_one({"_id": mod["_id"]})


@pytest.fixture(scope="session")
def insert_recent_modrinth_project():
    res = httpx.get(
        "https://api.modrinth.com/v2/search",
        params={
            "limit": 1,
            "offset": 60,
            "index": "newest",
        },
    ).json()    

    project = res["hits"][0]

    project["_id"] = project["project_id"]

    del project["project_id"]

    mongo_db["modrinth_projects"].insert_one(project)
    print(
        f"Inserted recent modrinth project with id: {project['_id']}, name: {project['title']}"
    )

    yield

    # 清理插入的测试数据
    mongo_db["modrinth_projects"].delete_many({"_id": project["_id"]})
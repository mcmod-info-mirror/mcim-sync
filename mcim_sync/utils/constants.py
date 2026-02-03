from enum import Enum

ACCEPT_GAMEIDS = [432, 78022]  # 432: Minecraft, 78022: Minecraft Bedrock Edition

GAME_432_CLASSES_INFO = [
    {"id": 4546, "name": "Customization"},
    {"id": 4559, "name": "Addons"},
    {"id": 12, "name": "Resource Packs"},
    {"id": 5, "name": "Bukkit Plugins"},
    {"id": 6, "name": "Mods"},
    {"id": 4471, "name": "Modpacks"},
    {"id": 17, "name": "Worlds"},
    {"id": 6552, "name": "Shaders"},
    {"id": 6945, "name": "Data Packs"},
]

GAME_78022_CLASSES_INFO = [
    {
        "id": 4984,
        "gameId": 78022,
        "name": "Addons",
        "slug": "addons",
        "url": "https://www.curseforge.com/minecraft-bedrock/addons",
        "iconUrl": "https://media.forgecdn.net/avatars/411/876/637630589173819650.png",
        "dateModified": "2024-12-15T10:47:02.327Z",
        "isClass": True,
        "displayIndex": 0,
    },
    {
        "id": 6913,
        "gameId": 78022,
        "name": "Maps",
        "slug": "maps",
        "url": "https://www.curseforge.com/minecraft-bedrock/maps",
        "iconUrl": "https://media.forgecdn.net/avatars/943/844/638427377367294459.png",
        "dateModified": "2025-05-12T12:34:46.877Z",
        "isClass": True,
        "displayIndex": 0,
    },
    {
        "id": 6929,
        "gameId": 78022,
        "name": "Texture Packs",
        "slug": "texture-packs",
        "url": "https://www.curseforge.com/minecraft-bedrock/texture-packs",
        "iconUrl": "https://media.forgecdn.net/avatars/943/861/638427382732560320.png",
        "dateModified": "2025-05-12T12:49:21.767Z",
        "isClass": True,
        "displayIndex": 0,
    },
    {
        "id": 6940,
        "gameId": 78022,
        "name": "Scripts",
        "slug": "scripts",
        "url": "https://www.curseforge.com/minecraft-bedrock/scripts",
        "iconUrl": "https://media.forgecdn.net/avatars/943/873/638427388082139294.png",
        "dateModified": "2024-02-11T13:25:28.477Z",
        "isClass": True,
        "displayIndex": 0,
    },
    {
        "id": 6925,
        "gameId": 78022,
        "name": "Skins",
        "slug": "skins",
        "url": "https://www.curseforge.com/minecraft-bedrock/skins",
        "iconUrl": "https://media.forgecdn.net/avatars/943/856/638427381455151332.png",
        "dateModified": "2024-02-11T13:25:17.637Z",
        "isClass": True,
        "displayIndex": 0,
    },
]


class Platform(Enum):
    CURSEFORGE = "curseforge"
    MODRINTH = "modrinth"

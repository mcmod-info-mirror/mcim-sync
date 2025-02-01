from typing import List, Optional, Union

from mcim_sync.utils.network import request
from mcim_sync.config import Config

config = Config.load()

API = config.curseforge_api
HEADERS = {
    "x-api-key": config.curseforge_api_key,
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36 Edg/116.0.1938.54",
}


def get_mod_files(modId: int, index: int, pageSize: int) -> dict:
    params = {"index": index, "pageSize": pageSize}
    res = request(f"{API}/v1/mods/{modId}/files", headers=HEADERS, params=params).json()
    return res


def get_mod(modId: int) -> dict:
    res = request(f"{API}/v1/mods/{modId}", headers=HEADERS).json()["data"]
    return res


def get_mutil_mods_info(modIds: List[int]):
    data = {"modIds": modIds}
    res = request(
        method="POST", url=f"{API}/v1/mods", json=data, headers=HEADERS
    ).json()["data"]
    return res


def get_mutil_files(fileIds: List[int]):
    data = {"fileIds": fileIds}
    res = request(
        method="POST", url=f"{API}/v1/mods/files", json=data, headers=HEADERS
    ).json()["data"]
    return res


def get_mutil_fingerprints(fingerprints: List[int]):
    res = request(
        method="POST",
        url=f"{API}/v1/fingerprints/432",
        headers=HEADERS,
        json={"fingerprints": fingerprints},
    ).json()["data"]
    return res


def get_categories(
    gameId: int = 432, classId: Optional[int] = None, classOnly: Optional[bool] = None
) -> List[dict]:
    params = {"gameId": gameId}
    if classId is not None:
        params["classId"] = classId
    elif classOnly:
        params["classOnly"] = classOnly
    res = request(f"{API}/v1/categories", params=params, headers=HEADERS).json()["data"]
    return res
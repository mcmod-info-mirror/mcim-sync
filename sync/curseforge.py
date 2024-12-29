from typing import List, Optional, Union
from utils.telegram import ProjectDetail
from odmantic import query
import time

from models.database.curseforge import File, Mod, Pagination, Fingerprint
from models.database.file_cdn import File as FileCDN
from utils.network import request_sync
from utils.loger import log
from utils import submit_models
from database.mongodb import sync_mongo_engine as mongodb_engine
from config import Config
from exceptions import ResponseCodeException

config = Config.load()

API = config.curseforge_api
MAX_LENGTH = config.max_file_size
MIN_DOWNLOAD_COUNT = 0
HEADERS = {
    "x-api-key": config.curseforge_api_key,
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36 Edg/116.0.1938.54",
}


def append_model_from_files_res(
    res, latestFiles: dict, need_to_cache: bool = True
) -> List[Union[File, Fingerprint]]:
    models = []
    for file in res["data"]:
        for _hash in file["hashes"]:
            if _hash["algo"] == 1:
                file["sha1"] = _hash["value"]
            elif _hash["algo"] == 2:
                file["md5"] = _hash["value"]
        file_model = File(found=True, need_to_cache=need_to_cache, **file)
        models.append(file_model)
        models.append(
            Fingerprint(
                id=file["fileFingerprint"],
                file=file,
                latestFiles=latestFiles,
                found=True,
            )
        )
        # for file_cdn
        if config.file_cdn:
            if (
                file_model.sha1 is not None
                and file_model.gameId == 432
                and file_model.fileLength <= MAX_LENGTH
                and file_model.downloadCount >= MIN_DOWNLOAD_COUNT
                and file_model.downloadUrl is not None
            ):
                models.append(
                    FileCDN(
                        sha1=file_model.sha1,
                        url=file_model.downloadUrl,
                        path=file_model.sha1,
                        size=file_model.fileLength,
                        mtime=int(time.time()),
                    )
                )
    return models


def sync_mod_all_files(
    modId: int,
    latestFiles: List[dict] = None,
    need_to_cache: bool = True,
) -> List[Union[File, Mod]]:
    models = []
    if not latestFiles:
        mod_model = mongodb_engine.find_one(Mod, Mod.id == modId)
        if mod_model is not None:
            latestFiles = mod_model.latestFiles
            need_to_cache = mod_model.classId == 6

    try:
        params = {"index": 0, "pageSize": 50}
        file_id_list = []

        while True:
            res = request_sync(
                f"{API}/v1/mods/{modId}/files",
                headers=HEADERS,
                params=params,
            ).json()

            models = append_model_from_files_res(
                res, latestFiles, need_to_cache=need_to_cache
            )
            file_id_list.extend([file["id"] for file in res["data"]])
            submit_models(models=models)

            page = Pagination(**res["pagination"])
            log.debug(
                f'Sync curseforge modid:{modId} index:{params["index"]} ps:{params["pageSize"]} total:{page.totalCount}'
            )

            if page.index >= page.totalCount - 1:
                break

            params["index"] = page.index + page.pageSize

        removed_count = mongodb_engine.remove(
            File, File.modId == modId, query.not_in(File.id, file_id_list)
        )
        log.info(
            f"Finished sync mod {modId}, total {page.totalCount} files, removed {removed_count} files"
        )

        return page.totalCount

    except ResponseCodeException as e:
        if e.status_code == 404:
            log.error(f"Mod {modId} not found!")
        else:
            log.error(f"Sync mod {modId} failed, {e}")
    except Exception as e:
        log.error(f"Sync mod {modId} failed, {e}")

    return models


def sync_mod(modId: int) -> ProjectDetail:
    models: List[Union[File, Mod]] = []
    try:
        res = request_sync(f"{API}/v1/mods/{modId}", headers=HEADERS).json()["data"]
        models.append(Mod(found=True, **res))
        # mod = mongodb_engine.find_one(Mod, Mod.id == modId)
        # if mod is not None:
        #     if mod.dateReleased == models[0].dateReleased:
        #         log.info(f"Mod {modId} is not out-of-date, pass!")
        #         return
        total_count = sync_mod_all_files(
            modId,
            latestFiles=res["latestFiles"],
            need_to_cache=True if res["classId"] == 6 else False,
        )
        submit_models(models)
        return ProjectDetail(
            id=res["id"],
            name=res["name"],
            version_count=total_count,
        )
    except ResponseCodeException as e:
        if e.status_code == 404:
            log.error(f"Mod {modId} not found!")
    except Exception as e:
        log.error(f"Sync mod {modId} failed, {e}")


def fetch_mutil_mods_info(modIds: List[int]):
    modIds = list(set(modIds))
    data = {"modIds": modIds}
    try:
        res = request_sync(
            method="POST", url=f"{API}/v1/mods", json=data, headers=HEADERS
        ).json()["data"]
        return res
    except Exception as e:
        log.error(f"Failed to fetch mutil mods info: {e}")
        return []


def fetch_mutil_files(fileIds: List[int]):
    fileIds = list(set(fileIds))
    data = {"fileIds": fileIds}
    try:
        res = request_sync(
            method="POST", url=f"{API}/v1/mods/files", json=data, headers=HEADERS
        ).json()["data"]
        return res
    except Exception as e:
        log.error(f"Failed to fetch mutil files info: {e}")
        return []


def fetch_mutil_fingerprints(fingerprints: List[int]):
    try:
        res = request_sync(
            method="POST",
            url=f"{API}/v1/fingerprints/432",
            headers=HEADERS,
            json={"fingerprints": fingerprints},
        ).json()["data"]
        return res
    except Exception as e:
        log.error(f"Failed to fetch mutil fingerprints info: {e}")
        return []

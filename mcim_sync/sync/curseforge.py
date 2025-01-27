from typing import List, Optional, Union
from odmantic import query
import time

from mcim_sync.models.database.curseforge import File, Mod, Pagination, Fingerprint, Category
from mcim_sync.models.database.file_cdn import File as FileCDN
from mcim_sync.models import ProjectDetail
from mcim_sync.utils.network import request
from mcim_sync.utils.loger import log
from mcim_sync.utils import ModelSubmitter
from mcim_sync.database.mongodb import sync_mongo_engine as mongodb_engine
from mcim_sync.config import Config
from mcim_sync.exceptions import ResponseCodeException

config = Config.load()

API = config.curseforge_api
MAX_LENGTH = config.max_file_size
MIN_DOWNLOAD_COUNT = 0
HEADERS = {
    "x-api-key": config.curseforge_api_key,
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36 Edg/116.0.1938.54",
}


def append_model_from_files_res(
    res,
    latestFiles: dict,
    need_to_cache: bool = True,
):
    with ModelSubmitter() as submitter:
        for file in res["data"]:
            for _hash in file["hashes"]:
                if _hash["algo"] == 1:
                    file["sha1"] = _hash["value"]
                elif _hash["algo"] == 2:
                    file["md5"] = _hash["value"]
            file_model = File(**file)
            submitter.add(
                Fingerprint(
                    id=file["fileFingerprint"],
                    file=file,
                    latestFiles=latestFiles,
                )
            )
            # for file_cdn
            if config.file_cdn:
                if (
                    need_to_cache, # classId filter (must be 6)
                    file_model.sha1 is not None
                    and file_model.gameId == 432
                    and file_model.fileLength <= MAX_LENGTH
                    and file_model.downloadCount >= MIN_DOWNLOAD_COUNT
                    and file_model.downloadUrl is not None,
                ):
                    submitter.add(
                        FileCDN(
                            sha1=file_model.sha1,
                            url=file_model.downloadUrl,
                            path=file_model.sha1,
                            size=file_model.fileLength,
                            mtime=int(time.time()),
                        ) # type: ignore
                    )
                    file_model.file_cdn_cached = True # 在这里设置 file_cdn_cached，默认为 False
            submitter.add(file_model)


def sync_mod_all_files(
    modId: int,
    latestFiles: List[dict],
    need_to_cache: bool = True,
) -> List[Union[File, Mod]]:
    models = []
    if not latestFiles:
        mod_model = mongodb_engine.find_one(Mod, Mod.id == modId)
        if mod_model:
            latestFiles = mod_model.latestFiles
            need_to_cache = mod_model.classId == 6
        else:
            raise Exception("latestFiles is required when mod not in database")

    try:
        params = {"index": 0, "pageSize": 50}
        file_id_list = []

        while True:
            res = request(
                f"{API}/v1/mods/{modId}/files",
                headers=HEADERS,
                params=params,
            ).json()

            append_model_from_files_res(
                res, latestFiles, need_to_cache=need_to_cache
            )
            file_id_list.extend([file["id"] for file in res["data"]])

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
    try:
        with ModelSubmitter() as submitter:
            res = request(f"{API}/v1/mods/{modId}", headers=HEADERS).json()["data"]
            total_count = sync_mod_all_files(
                modId,
                latestFiles=res["latestFiles"],  # 此处调用必传 latestFiles
                need_to_cache=True if res["classId"] == 6 else False,
            )
            submitter.add(Mod(**res))
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
        res = request(
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
        res = request(
            method="POST", url=f"{API}/v1/mods/files", json=data, headers=HEADERS
        ).json()["data"]
        return res
    except Exception as e:
        log.error(f"Failed to fetch mutil files info: {e}")
        return []


def fetch_mutil_fingerprints(fingerprints: List[int]):
    try:
        res = request(
            method="POST",
            url=f"{API}/v1/fingerprints/432",
            headers=HEADERS,
            json={"fingerprints": fingerprints},
        ).json()["data"]
        return res
    except Exception as e:
        log.error(f"Failed to fetch mutil fingerprints info: {e}")
        return []


def sync_categories(
    gameId: int = 432, classId: Optional[int] = None, classOnly: Optional[bool] = None
) -> List[Category]:
    try:
        with ModelSubmitter() as submitter:
            params = {"gameId": gameId}
            if classId is not None:
                params["classId"] = classId
            elif classOnly:
                params["classOnly"] = classOnly
            res = request(
                f"{API}/v1/categories",
                params=params,
                headers=HEADERS,
            ).json()["data"]
            for category in res:
                submitter.add(Category(**category))
            return res
    except ResponseCodeException as e:
        if e.status_code == 404:
            log.error(f"Categories not found!")
        else:
            log.error(f"Failed to sync categories: {e}")
        return []
    except Exception as e:
        log.error(f"Failed to sync categories: {e}")
        return []

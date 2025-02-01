from typing import List, Optional, Union
from tenacity import retry, stop_after_attempt, wait_fixed
from odmantic import query
import time

from mcim_sync.models.database.curseforge import (
    File,
    Mod,
    Pagination,
    Fingerprint,
    Category,
)
from mcim_sync.apis.curseforge import (
    get_mod,
    get_mod_files,
    get_categories,
    get_mutil_files,
    get_mutil_fingerprints,
    get_mutil_mods_info,
)
from mcim_sync.models.database.file_cdn import File as FileCDN
from mcim_sync.utils.constans import ProjectDetail
from mcim_sync.utils.loger import log
from mcim_sync.utils.model_submitter import ModelSubmitter
from mcim_sync.utils import find_hash_in_curseforge_hashes
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
    res, latestFiles: List[dict], need_to_cache: bool = True
):
    with ModelSubmitter() as submitter:
        for file in res["data"]:
            file_model = File(**file)
            submitter.add(
                Fingerprint(
                    id=file["fileFingerprint"],
                    file=file,
                    latestFiles=latestFiles,  # type: ignore
                )
            )
            file_sha1 = find_hash_in_curseforge_hashes(file["hashes"], 1)

            if config.file_cdn:
                if (
                    file_model.fileLength is not None
                    and file_model.downloadCount is not None
                    and file_model.downloadUrl is not None
                    and file_sha1
                ):
                    if (
                        need_to_cache
                        and file_model.gameId == 432
                        and file_model.fileLength <= MAX_LENGTH
                        and file_model.downloadCount >= MIN_DOWNLOAD_COUNT
                    ):
                        submitter.add(
                            FileCDN(
                                sha1=file_sha1,
                                url=file_model.downloadUrl,
                                path=file_sha1,
                                size=file_model.fileLength,
                                mtime=int(time.time()),
                            )  # type: ignore
                        )
                        file_model.file_cdn_cached = True
            submitter.add(file_model)


def sync_mod_all_files(
    modId: int, latestFiles: List[dict], need_to_cache: bool = True
) -> int:
    params = {"index": 0, "pageSize": 50}
    file_id_list = []

    while True:
        res = get_mod_files(modId, params["index"], params["pageSize"])
        append_model_from_files_res(
            res, latestFiles=latestFiles, need_to_cache=need_to_cache
        )
        file_id_list.extend([file["id"] for file in res["data"]])

        page = Pagination(**res["pagination"])
        log.debug(
            f"Sync curseforge modid:{modId} index:{params['index']} ps:{params['pageSize']} total:{page.totalCount}"
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


@retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
def sync_mod(modId: int) -> Optional[ProjectDetail]:
    try:
        with ModelSubmitter() as submitter:
            res = get_mod(modId)
            submitter.add(Mod(**res))
            sync_mod_all_files(
                modId,
                latestFiles=res["latestFiles"],
                need_to_cache=True if res["classId"] == 6 else False,
            )
            return ProjectDetail(
                id=res["id"],
                name=res["name"],
                version_count=len(res["latestFiles"]),
            )
    except ResponseCodeException as e:
        if e.status_code == 404:
            log.error(f"Mod {modId} not found!")
        else:
            raise e


@retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
def fetch_mutil_mods_info(modIds: List[int]):
    modIds = list(set(modIds))
    try:
        res = get_mutil_mods_info(modIds)
        return res
    except Exception as e:
        log.error(f"Failed to fetch mutil mods info: {e}")
        return None


@retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
def fetch_mutil_files(fileIds: List[int]):
    fileIds = list(set(fileIds))
    try:
        res = get_mutil_files(fileIds)
        return res
    except Exception as e:
        log.error(f"Failed to fetch mutil files info: {e}")
        return None


@retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
def fetch_mutil_fingerprints(fingerprints: List[int]):
    fingerprints = list(set(fingerprints))
    try:
        res = get_mutil_fingerprints(fingerprints)
        return res
    except Exception as e:
        log.error(f"Failed to fetch mutil fingerprints info: {e}")
        return None


@retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
def sync_categories(
    gameId: int = 432, classId: Optional[int] = None, classOnly: Optional[bool] = None
) -> Optional[List[dict]]:
    try:
        with ModelSubmitter() as submitter:
            if classId is not None:
                res = get_categories(gameId, classId=classId)
            elif classOnly:
                res = get_categories(gameId, classOnly=classOnly)
            else:
                res = get_categories(gameId)
            for category in res:
                submitter.add(Category(**category))
            return res
    except ResponseCodeException as e:
        if e.status_code == 404:
            log.error("Categories not found!")
            return None
        else:
            raise e

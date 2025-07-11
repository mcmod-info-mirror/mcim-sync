from typing import List, Optional, Union
from tenacity import retry, stop_after_attempt, wait_fixed
from odmantic import query
from enum import Enum
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
    get_search_result,
)
# from mcim_sync.models.database.file_cdn import File as FileCDN
from mcim_sync.utils.constans import ProjectDetail
from mcim_sync.utils.loger import log
from mcim_sync.utils.model_submitter import ModelSubmitter
# from mcim_sync.utils import find_hash_in_curseforge_hashes
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
            # file_sha1 = find_hash_in_curseforge_hashes(file["hashes"], 1)

            # if config.file_cdn:
            #     if (
            #         file_model.fileLength is not None
            #         and file_model.downloadCount is not None
            #         and file_model.downloadUrl is not None
            #         and file_sha1
            #     ):
            #         if (
            #             need_to_cache
            #             and file_model.gameId == 432
            #             and file_model.fileLength <= MAX_LENGTH
            #             and file_model.downloadCount >= MIN_DOWNLOAD_COUNT
            #         ):
            #             submitter.add(
            #                 FileCDN(
            #                     sha1=file_sha1,
            #                     url=file_model.downloadUrl,
            #                     path=file_sha1,
            #                     size=file_model.fileLength,
            #                     mtime=int(time.time()),
            #                 )  # type: ignore
            #             )
            #             file_model.file_cdn_cached = True
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


def sync_mod_all_files_at_once(
    modId: int, latestFiles: List[dict], need_to_cache: bool = True
) -> Optional[int]:
    max_retries = 3
    page_size= 10000
    for i in range(max_retries):
        res = get_mod_files(modId, index=0, pageSize=page_size)

        file_id_list = [file["id"] for file in res["data"]]

        page = Pagination(**res["pagination"])

        if page.resultCount != page.totalCount or len(file_id_list) != page.resultCount:
            log.warning(
                f"ResultCount {page.resultCount} != TotalCount {page.totalCount} for mod {modId}, or the count of files != resultCount, response maybe incomplete, passing sync, retrying {i+1}/{max_retries}"
            )
            # time.sleep(1)
            page_size -= 1
            continue
        else:
            break
    else:
        log.error(f"Failed to get all files for mod {modId} after {max_retries} retries")
        return None

    append_model_from_files_res(
        res, latestFiles=latestFiles, need_to_cache=need_to_cache
    )

    removed_count = mongodb_engine.remove(
        File, File.modId == modId, query.not_in(File.id, file_id_list)
    )
    log.info(
        f"Finished sync mod {modId}, total {page.totalCount} files, resultCount {page.resultCount}, removed {removed_count} files"
    )

    return page.totalCount


@retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
def sync_mod(modId: int) -> Optional[ProjectDetail]:
    try:
        with ModelSubmitter() as submitter:
            res = get_mod(modId)
            mod_model = Mod(**res)
            if mod_model.gameId == 432:
                # version_count = sync_mod_all_files(
                #     modId,
                #     latestFiles=res["latestFiles"],
                #     need_to_cache=True if res["classId"] == 6 else False,
                # )

                version_count = sync_mod_all_files_at_once(
                    modId,
                    latestFiles=res["latestFiles"],
                    need_to_cache=True if res["classId"] == 6 else False,
                )

                if version_count is None:
                    return None

                # 最后再添加，以防未成功刷新版本列表而更新 Mod 信息
                submitter.add(mod_model)

                return ProjectDetail(
                    id=res["id"],
                    name=res["name"],
                    version_count=version_count,
                )
            else:
                log.debug(f"Mod {modId} gameId is not 432")

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


class ModsSearchSortField(int, Enum):
    """
    https://docs.curseforge.com/rest-api/#tocS_ModsSearchSortField
    """

    Featured = 1
    Popularity = 2
    LastUpdated = 3
    Name = 4
    Author = 5
    TotalDownloads = 6
    Category = 7
    GameVersion = 8
    EarlyAccess = 9
    FeaturedReleased = 10
    ReleasedDate = 11
    Rating = 12


class ModLoaderType(int, Enum):
    """
    https://docs.curseforge.com/rest-api/#tocS_ModLoaderType
    """

    Any = 0
    Forge = 1
    Cauldron = 2
    LiteLoader = 3
    Fabric = 4
    Quilt = 5
    NeoForge = 6


class ModsSearchSortOrder(str, Enum):
    """
    'asc' if sort is in ascending order, 'desc' if sort is in descending order
    """

    ASC = "asc"
    DESC = "desc"


@retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
def fetch_search_result(
    gameId: int = 432,
    classId: Optional[int] = None,
    categoryId: Optional[int] = None,
    categoryIds: Optional[str] = None,
    gameVersion: Optional[str] = None,
    gameVersions: Optional[str] = None,
    searchFilter: Optional[str] = None,
    sortField: Optional[ModsSearchSortField] = None,
    sortOrder: Optional[ModsSearchSortOrder] = None,
    modLoaderType: Optional[ModLoaderType] = None,
    modLoaderTypes: Optional[str] = None,
    gameVersionTypeId: Optional[int] = None,
    authorId: Optional[int] = None,
    primaryAuthorId: Optional[int] = None,
    slug: Optional[str] = None,
    index: Optional[int] = None,
    pageSize: Optional[int] = 50,
):
    """
    Fetch search result from CurseForge API.
    """
    try:
        res = get_search_result(
            gameId=gameId,
            classId=classId,
            categoryId=categoryId,
            categoryIds=categoryIds,
            gameVersion=gameVersion,
            gameVersions=gameVersions,
            searchFilter=searchFilter,
            sortField=sortField.value if sortField else None,
            sortOrder=sortOrder.value if sortOrder else None,
            modLoaderType=modLoaderType.value if modLoaderType else None,
            modLoaderTypes=modLoaderTypes,
            gameVersionTypeId=gameVersionTypeId,
            authorId=authorId,
            primaryAuthorId=primaryAuthorId,
            slug=slug,
            index=index,
            pageSize=pageSize,
        )
        return res
    except ResponseCodeException as e:
        if e.status_code == 404:
            log.error("Search result not found!")
            return None
        else:
            raise e

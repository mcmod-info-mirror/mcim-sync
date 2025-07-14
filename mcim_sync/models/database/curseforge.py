from odmantic import Model, Field
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class CategoryInfo(BaseModel):
    id: int
    gameId: int
    name: str
    slug: Optional[str] = None  # stupid curseforge dev | For id 4591 and 236, slug is None
    url: str
    iconUrl: str
    dateModified: datetime
    isClass: Optional[bool] = None
    classId: Optional[int] = None
    parentCategoryId: Optional[int] = None
    displayIndex: Optional[int] = None

class FileDependencies(BaseModel):
    modId: int
    relationType: Optional[int] = None


class FileSortableGameVersions(BaseModel):
    gameVersionName: Optional[str] = None
    gameVersionPadded: Optional[str] = None
    gameVersion: Optional[str] = None
    gameVersionReleaseDate: Optional[datetime] = None
    gameVersionTypeId: Optional[int] = None


class Hash(BaseModel):
    value: str
    algo: int


class Author(BaseModel):
    id: int
    name: str
    url: Optional[str] = None


class Logo(BaseModel):
    id: int
    modId: int
    title: Optional[str] = None
    description: Optional[str] = None
    thumbnailUrl: Optional[str] = None
    url: Optional[str] = None


class Links(BaseModel):
    websiteUrl: Optional[str] = None
    wikiUrl: Optional[str] = None
    issuesUrl: Optional[str] = None
    sourceUrl: Optional[str] = None


class ScreenShot(BaseModel):
    id: int
    modId: int
    title: Optional[str] = None
    description: Optional[str] = None
    thumbnailUrl: Optional[str] = None
    url: Optional[str] = None


class Module(BaseModel):
    name: Optional[str] = None
    fingerprint: Optional[int] = None


class File(Model):
    id: int = Field(primary_field=True, index=True)
    gameId: int
    modId: int = Field(index=True)
    isAvailable: Optional[bool] = None
    displayName: Optional[str] = None
    fileName: Optional[str] = None
    releaseType: Optional[int] = None
    fileStatus: Optional[int] = None
    hashes: Optional[List[Hash]] = None
    fileDate: Optional[datetime] = None
    fileLength: Optional[int] = None
    downloadCount: Optional[int] = None
    fileSizeOnDisk: Optional[int] = None
    downloadUrl: Optional[str] = None
    gameVersions: Optional[List[str]] = None
    sortableGameVersions: Optional[List[FileSortableGameVersions]] = None
    dependencies: Optional[List[FileDependencies]] = None
    exposeAsAlternative: Optional[bool] = None
    parentProjectFileId: Optional[int] = None
    alternateFileId: Optional[int] = None
    isServerPack: Optional[bool] = None
    serverPackFileId: Optional[int] = None
    isEarlyAccessContent: Optional[bool] = None
    earlyAccessEndDate: Optional[datetime] = None
    fileFingerprint: Optional[int] = None
    modules: Optional[List[Module]] = None

    sync_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {
        "collection": "curseforge_files",
    }


class FileInfo(BaseModel):
    id: int
    gameId: int
    modId: int
    isAvailable: Optional[bool] = None
    displayName: Optional[str] = None
    fileName: Optional[str] = None
    releaseType: Optional[int] = None
    fileStatus: Optional[int] = None
    hashes: Optional[List[Hash]] = None
    fileDate: Optional[datetime] = None
    fileLength: Optional[int] = None
    downloadCount: Optional[int] = None
    fileSizeOnDisk: Optional[int] = None
    downloadUrl: Optional[str] = None
    gameVersions: Optional[List[str]] = None
    sortableGameVersions: Optional[List[FileSortableGameVersions]] = None
    dependencies: Optional[List[FileDependencies]] = None
    exposeAsAlternative: Optional[bool] = None
    parentProjectFileId: Optional[int] = None
    alternateFileId: Optional[int] = None
    isServerPack: Optional[bool] = None
    serverPackFileId: Optional[int] = None
    isEarlyAccessContent: Optional[bool] = None
    earlyAccessEndDate: Optional[datetime] = None
    fileFingerprint: Optional[int] = None
    modules: Optional[List[Module]] = None


class FileIndex(BaseModel):
    gameVersion: Optional[str] = None
    fileId: int
    filename: Optional[str] = None
    releaseType: Optional[int] = None
    gameVersionTypeId: Optional[int] = None
    modLoader: Optional[int] = None


class Mod(Model):
    id: int = Field(primary_field=True, index=True)
    gameId: Optional[int] = None
    name: Optional[str] = None
    slug: str
    links: Optional[Links] = None
    summary: Optional[str] = None
    status: Optional[int] = None
    downloadCount: Optional[int] = None
    isFeatured: Optional[bool] = None
    primaryCategoryId: Optional[int] = None
    categories: Optional[List[CategoryInfo]] = None
    classId: Optional[int] = None
    authors: Optional[List[Author]] = None
    logo: Optional[Logo] = None
    screenshots: Optional[List[ScreenShot]] = None
    mainFileId: Optional[int] = None
    latestFiles: Optional[List[FileInfo]] = None
    latestFilesIndexes: Optional[List[FileIndex]] = None
    dateCreated: Optional[datetime] = None
    dateModified: Optional[datetime] = None
    dateReleased: Optional[datetime] = None
    allowModDistribution: Optional[bool] = None
    gamePopularityRank: Optional[int] = None
    isAvailable: Optional[bool] = None
    thumbsUpCount: Optional[int] = None
    rating: Optional[int] = None

    translated_summary: Optional[str] = None

    sync_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {
        "collection": "curseforge_mods",
    }


class Pagination(BaseModel):
    index: int
    pageSize: int
    resultCount: int
    totalCount: int


class Fingerprint(Model):
    id: int = Field(primary_field=True, index=True)
    file: FileInfo
    latestFiles: List[FileInfo]

    sync_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {
        "collection": "curseforge_fingerprints",
        "indexes": [
            {"fields": ["file.id"], "name": "file.id_1"},
            {"fields": ["_id"], "name": "_id_"},
            
        ],
    }


class Category(Model):
    id: int = Field(primary_field=True, index=True)
    gameId: int
    name: str
    slug: Optional[str] = None # stupid curseforge dev | For id 4591 and 236, slug is None
    url: str
    iconUrl: str
    dateModified: datetime
    isClass: Optional[bool] = None
    classId: Optional[int] = None
    parentCategoryId: Optional[int] = None
    displayIndex: Optional[int] = None

    sync_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {
        "collection": "curseforge_categories",
        "title": "CurseForge Category",
    }

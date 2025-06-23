from typing import Union, List, Set, TypeVar
from odmantic import Model
from enum import Enum

from mcim_sync.models.database.curseforge import Mod
from mcim_sync.models.database.modrinth import Project
from mcim_sync.database.mongodb import sync_mongo_engine
from mcim_sync.utils.loger import log


class Platform(Enum):
    CURSEFORGE = "curseforge"
    MODRINTH = "modrinth"

class ModelSubmitter:
    """
    用于批量 save model
    """
    def __init__(self, batch_size: int = 100):
        self.models: List[Model] = []
        self.batch_size = batch_size
        self.total_submitted = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        if exc_type:
            log.error(f"Error during model submission: {exc_val}")
            return False
        return True

    def add(self, model: Model) -> None:
        """添加文档到批次"""
        self.models.append(model)
        if len(self.models) >= self.batch_size:
            self.flush()

    def flush(self) -> None:
        """强制保存当前批次"""
        if not self.models:
            return

        try:
            # 批量保存模型
            sync_mongo_engine.save_all(self.models)
            self.total_submitted += len(self.models)
            log.debug(
                f"Saved {len(self.models)} models (total: {self.total_submitted})"
            )
        except Exception as e:
            log.error(f"Error saving models: {e}")
            raise
        finally:
            self.models.clear()

    def close(self) -> None:
        """保存所有剩余模型并清理"""
        self.flush()
        log.debug(f"ModelSubmitter finished, total submitted: {self.total_submitted}")

    def clear(self) -> None:
        """清空待保存的模型"""
        self.models.clear()
        log.debug("Cleared pending models.")

    @property
    def pending_count(self) -> int:
        """待保存的模型数量"""
        return len(self.models)

    @property
    def total_count(self) -> int:
        """已保存的模型数量"""
        return self.total_submitted

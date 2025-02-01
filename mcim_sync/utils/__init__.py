from typing import List, Optional


def find_hash_in_curseforge_hashes(hashes: Optional[List[dict]], algo: int) -> Optional[str]:
    """
    algo: 1=sha1, 2=md5
    """
    if not hashes:
        return None
    for _hash in hashes:
        if _hash["algo"] == algo:
            return _hash["value"]
    return None
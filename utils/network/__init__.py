"""
与网络请求相关的模块
"""

import httpx

from tenacity import retry, stop_after_attempt, retry_if_not_exception_type
from typing import Optional, Union
from exceptions import ApiException, ResponseCodeException, TooManyRequestsException
from config import Config
from utils.loger import log

config = Config.load()


PROXY: Optional[str] = config.proxies

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36 Edg/116.0.1938.54",
}

TIMEOUT = 5
RETRY_TIMES = 3
REQUEST_LOG = True


httpx_client: httpx.Client = httpx.Client(proxy=PROXY)


def get_session() -> httpx.Client:
    global httpx_client
    if httpx_client:
        return httpx_client
    else:
        httpx_client = httpx.Client()
        return httpx_client


@retry(
    stop=stop_after_attempt(RETRY_TIMES),
    retry=(retry_if_not_exception_type(ResponseCodeException)),
    reraise=True,
)
def request(
    url: str,
    method: str = "GET",
    data: Optional[dict] = None,
    params: Optional[dict] = None,
    json: Optional[dict] = None,
    timeout: Optional[Union[int, float]] = TIMEOUT,
    ignore_status_code: bool = False,
    **kwargs,
) -> httpx.Response:
    """
    HTTPX 请求函数

    Args:
        url (str): 请求 URL

        method (str, optional): 请求方法 默认 GET

        timeout (Optional[Union[int, float]], optional): 超时时间，默认为 5 秒

        **kwargs: 其他参数

    Returns:
        Any: 请求结果
    """
    # delete null query
    if params is not None:
        params = {k: v for k, v in params.items() if v is not None}

    session = get_session()

    if json is not None:
        res: httpx.Response = session.request(
            method, url, json=json, params=params, timeout=timeout, **kwargs
        )
    else:
        res: httpx.Response = session.request(
            method, url, data=data, params=params, timeout=timeout, **kwargs
        )
    if not ignore_status_code:
        if res.status_code != 200:
            if res.status_code == 429:
                raise TooManyRequestsException(
                    method=method,
                    url=url,
                    data=data if data is None else json,
                    params=params,
                )
            else:
                raise ResponseCodeException(
                    status_code=res.status_code,
                    method=method,
                    url=url,
                    data=data if data is None else json,
                    params=params,
                    msg=res.text,
                )
    return res

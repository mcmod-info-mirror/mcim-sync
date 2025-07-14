import time
import threading
from typing import Dict
from urllib.parse import urlparse

from mcim_sync.config import Config


class TokenBucket:
    """令牌桶"""

    def __init__(self, capacity: int, refill_rate: float, initial_tokens: int = None):
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = initial_tokens if initial_tokens is not None else capacity
        self.last_refill_time = time.monotonic()
        self.condition = threading.Condition()
        self.waiting_count = 0
        self._start_refill_thread()

    def _start_refill_thread(self):
        """启动后台线程定期补充令牌"""

        def refill_loop():
            while True:
                with self.condition:
                    old_tokens = self.tokens
                    self._refill()
                    new_tokens = int(self.tokens - old_tokens)
                    if new_tokens > 0 and self.waiting_count > 0:
                        for _ in range(min(new_tokens, self.waiting_count)):
                            self.condition.notify()
                time.sleep(1.0 / self.refill_rate)

        thread = threading.Thread(target=refill_loop, daemon=True)
        thread.start()

    def _refill(self):
        """补充令牌 - 必须在持有锁的情况下调用"""
        current_time = time.monotonic()
        time_passed = current_time - self.last_refill_time
        tokens_to_add = time_passed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill_time = current_time

    def acquire(self, tokens: int = 1, timeout: float = None) -> bool:
        """
        获取令牌，如果没有则等待
        """
        with self.condition:
            self._refill()
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True

            self.waiting_count += 1
            end_time = None if timeout is None else time.monotonic() + timeout

            try:
                while self.tokens < tokens:
                    if timeout is None:
                        self.condition.wait()
                    else:
                        remaining = end_time - time.monotonic()
                        if remaining <= 0 or not self.condition.wait(timeout=remaining):
                            return False
                    self._refill()
                self.tokens -= tokens
                return True
            finally:
                self.waiting_count -= 1

    def get_status(self) -> Dict:
        """获取状态"""
        with self.condition:
            self._refill()
            return {
                "capacity": self.capacity,
                "current_tokens": self.tokens,
                "refill_rate": self.refill_rate,
                "waiting_requests": self.waiting_count,
                "utilization": (self.capacity - self.tokens) / self.capacity,
            }


class DomainRateLimiter:
    """基于令牌桶的域名限速器"""

    def __init__(self):
        self.domain_rate_limits_config = Config.load().domain_rate_limits
        self.token_buckets: Dict[str, TokenBucket] = {}
        self.lock = threading.Lock()

    def get_domain_from_url(self, url: str) -> str:
        """从URL中提取域名"""
        try:
            parsed = urlparse(url)
            return parsed.hostname.lower() if parsed.hostname else "unknown"
        except Exception:
            return "unknown"

    def _get_token_bucket(self, domain: str) -> TokenBucket:
        """获取域名对应的令牌桶"""
        with self.lock:
            bucket = self.token_buckets.get(domain)
            if bucket is not None:
                return bucket

            config = self.domain_rate_limits_config.get(domain)
            if config is None:
                raise ValueError(f"Domain '{domain}' not configured in rate limiter")

            bucket = TokenBucket(
                capacity=config.capacity,
                refill_rate=config.refill_rate,
                initial_tokens=config.initial_tokens,
            )
            self.token_buckets[domain] = bucket
            return bucket

    def acquire_token(self, url: str, timeout: float = None) -> bool:
        """
        获取令牌，如果没有则等待
        """
        domain = self.get_domain_from_url(url)

        if domain not in self.domain_rate_limits_config:
            return True

        try:
            bucket = self._get_token_bucket(domain)
        except ValueError:
            return True  # fallback for dynamic change

        return bucket.acquire(timeout=timeout)

    def get_domain_status(self, domain: str) -> Dict:
        """获取域名的限速状态"""
        if domain not in self.domain_rate_limits_config:
            return {"configured": False}

        bucket = self._get_token_bucket(domain)
        status = bucket.get_status()
        config = self.domain_rate_limits_config[domain]

        return {
            "configured": True,
            "algorithm": "token_bucket",
            "capacity": config.capacity,
            "refill_rate": config.refill_rate,
            "current_tokens": status["current_tokens"],
            "waiting_requests": status["waiting_requests"],
            "utilization": status["utilization"],
        }

domain_rate_limiter = DomainRateLimiter()

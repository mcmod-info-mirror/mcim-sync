"""
域名限速器模块
"""

import time
import threading
from collections import deque, defaultdict
from urllib.parse import urlparse
from typing import Dict

from mcim_sync.config import Config


class DomainRateLimiter:
    """简单的域名限速器"""
    
    def __init__(self):
        self.config = Config.load()
        self.domain_requests: Dict[str, deque] = defaultdict(deque)
        self.locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)
    
    def get_domain_from_url(self, url: str) -> str:
        """从URL中提取域名"""
        try:
            parsed = urlparse(url)
            return parsed.netloc.lower()
        except Exception:
            return "unknown"
    
    def can_make_request(self, url: str) -> bool:
        """检查是否可以向指定URL发起请求"""
        domain = self.get_domain_from_url(url)
        
        # 如果域名没有配置限速，则允许请求
        if domain not in self.config.domain_rate_limits:
            return True
        
        domain_config = self.config.domain_rate_limits[domain]
        current_time = time.time()
        
        with self.locks[domain]:
            requests = self.domain_requests[domain]
            
            # 清理超出时间窗口的请求记录
            while requests and current_time - requests[0] > domain_config.time_window:
                requests.popleft()
            
            # 检查是否超过最大请求数
            return len(requests) < domain_config.max_requests
    
    def record_request(self, url: str):
        """记录请求"""
        domain = self.get_domain_from_url(url)
        
        # 如果域名没有配置限速，则不记录
        if domain not in self.config.domain_rate_limits:
            return
        
        current_time = time.time()
        
        with self.locks[domain]:
            self.domain_requests[domain].append(current_time)
    
    def wait_time(self, url: str) -> float:
        """计算需要等待的时间"""
        domain = self.get_domain_from_url(url)
        
        # 如果域名没有配置限速，则不需要等待
        if domain not in self.config.domain_rate_limits:
            return 0.0
        
        domain_config = self.config.domain_rate_limits[domain]
        current_time = time.time()
        
        with self.locks[domain]:
            requests = self.domain_requests[domain]
            
            # 清理超出时间窗口的请求记录
            while requests and current_time - requests[0] > domain_config.time_window:
                requests.popleft()
            
            # 如果请求数已满，计算等待时间
            if len(requests) >= domain_config.max_requests:
                oldest_request = requests[0]
                return domain_config.time_window - (current_time - oldest_request)
            
            return 0.0
    
    def get_domain_status(self, domain: str) -> Dict:
        """获取域名的限速状态"""
        if domain not in self.config.domain_rate_limits:
            return {"configured": False}
        
        domain_config = self.config.domain_rate_limits[domain]
        current_time = time.time()
        
        with self.locks[domain]:
            requests = self.domain_requests[domain]
            
            # 清理超出时间窗口的请求记录
            while requests and current_time - requests[0] > domain_config.time_window:
                requests.popleft()
            
            return {
                "configured": True,
                "max_requests": domain_config.max_requests,
                "time_window": domain_config.time_window,
                "current_requests": len(requests),
                "remaining_requests": domain_config.max_requests - len(requests),
                "next_reset_time": requests[0] + domain_config.time_window if requests else current_time
            }


# 全局限速器实例
domain_rate_limiter = DomainRateLimiter()

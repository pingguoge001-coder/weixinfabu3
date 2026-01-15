"""
调度模块

包含任务队列管理和定时调度功能：
- QueueManager: 任务队列管理器，维护待执行任务队列
- TaskScheduler: 定时任务调度器，基于 APScheduler
- IdempotencyManager: 幂等性管理器，防止重复执行
- CircuitBreaker: 熔断器，防止系统在异常情况下持续失败
- RetryHandler: 重试处理器，实现指数退避重试策略
- RateLimiter: 速率限制器，根据失败率动态调整发送间隔
"""
from .queue_manager import QueueManager
from .task_scheduler import TaskScheduler
from .idempotency_manager import IdempotencyManager, IdempotencyContext
from .circuit_breaker import CircuitBreaker, CircuitBreakerContext
from .retry_handler import RetryHandler, RetryContext
from .rate_limiter import RateLimiter, ThrottledExecutor


__all__ = [
    "QueueManager",
    "TaskScheduler",
    "IdempotencyManager",
    "IdempotencyContext",
    "CircuitBreaker",
    "CircuitBreakerContext",
    "RetryHandler",
    "RetryContext",
    "RateLimiter",
    "ThrottledExecutor"
]

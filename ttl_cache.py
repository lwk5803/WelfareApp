"""
ttl_cache.py
------------
st.cache_data(ttl=...)를 대체하는 간단한 TTL(유효시간) 캐시 데코레이터입니다.
같은 인자로 다시 호출하면, ttl초가 지나기 전까지는 실제 함수를 다시 실행하지 않고
저장해둔 결과를 그대로 돌려줍니다. 정부 API·검색 API처럼 자주 안 바뀌는 데이터를
매번 다시 호출하지 않기 위한 용도입니다.
"""
import functools
import time


def cache_data(ttl: int):
    def decorator(func):
        cache: dict = {}

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            key = (args, tuple(sorted(kwargs.items())))
            now = time.monotonic()
            cached = cache.get(key)
            if cached is not None:
                value, expires_at = cached
                if now < expires_at:
                    return value
            value = func(*args, **kwargs)
            cache[key] = (value, now + ttl)
            return value

        return wrapper

    return decorator

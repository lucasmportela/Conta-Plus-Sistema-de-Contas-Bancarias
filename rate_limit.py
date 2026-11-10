"""Armazenamento configurável para limitação de tentativas de login."""
from database import (
    conectar,
    obter_bloqueio_login,
    registrar_falha_login,
    limpar_tentativas_login,
)


class LoginRateLimiter:
    def __init__(self, backend="sqlite", redis_url=None):
        self.backend = backend
        self.client = None
        if backend == "redis":
            if not redis_url:
                raise RuntimeError("REDIS_URL é obrigatório quando LOGIN_RATE_LIMIT_BACKEND=redis.")
            try:
                import redis
            except ImportError as erro:
                raise RuntimeError("Instale a dependência redis para usar o backend Redis.") from erro
            self.client = redis.Redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=3,
                socket_timeout=3,
                health_check_interval=30,
            )
            self.client.ping()
        elif backend != "sqlite":
            raise RuntimeError("LOGIN_RATE_LIMIT_BACKEND deve ser sqlite ou redis.")

    def _key(self, key_hash):
        return f"conta-plus:login:{key_hash}"

    def blocked_seconds(self, key_hash, now, window_seconds, retention_seconds):
        if self.backend == "sqlite":
            with conectar() as conn:
                return obter_bloqueio_login(
                    conn, key_hash, now, window_seconds, retention_seconds
                )

        script = """
        local data = redis.call('HMGET', KEYS[1], 'attempts', 'window_started', 'blocked_until')
        if not data[1] then return 0 end
        local window_started = tonumber(data[2])
        local blocked_until = tonumber(data[3]) or 0
        local now = tonumber(ARGV[1])
        if blocked_until > now then return blocked_until - now end
        if blocked_until > 0 or now - window_started >= tonumber(ARGV[2]) then
            redis.call('DEL', KEYS[1])
        end
        return 0
        """
        return int(self.client.eval(
            script, 1, self._key(key_hash), now, window_seconds
        ))

    def record_failure(
        self, key_hash, now, limit, window_seconds,
        block_seconds, retention_seconds
    ):
        if self.backend == "sqlite":
            with conectar() as conn:
                return registrar_falha_login(
                    conn, key_hash, now, limit, window_seconds,
                    block_seconds, retention_seconds
                )

        script = """
        local data = redis.call('HMGET', KEYS[1], 'attempts', 'window_started', 'blocked_until')
        local now = tonumber(ARGV[1])
        local limit = tonumber(ARGV[2])
        local window_seconds = tonumber(ARGV[3])
        local block_seconds = tonumber(ARGV[4])
        local retention_seconds = tonumber(ARGV[5])
        local attempts = tonumber(data[1])
        local window_started = tonumber(data[2])
        local blocked_until = tonumber(data[3]) or 0

        if blocked_until > now then return blocked_until - now end

        if not attempts or not window_started
            or now - window_started >= window_seconds
            or blocked_until > 0 then
            attempts = 1
            window_started = now
        else
            attempts = attempts + 1
        end

        blocked_until = 0
        if attempts >= limit then
            blocked_until = now + block_seconds
        end

        redis.call(
            'HSET', KEYS[1],
            'attempts', attempts,
            'window_started', window_started,
            'blocked_until', blocked_until
        )
        redis.call('EXPIRE', KEYS[1], retention_seconds)
        return math.max(0, blocked_until - now)
        """
        return int(self.client.eval(
            script, 1, self._key(key_hash), now, limit,
            window_seconds, block_seconds, retention_seconds
        ))

    def reset(self, key_hash):
        if self.backend == "sqlite":
            with conectar() as conn:
                limpar_tentativas_login(conn, key_hash)
        else:
            self.client.delete(self._key(key_hash))

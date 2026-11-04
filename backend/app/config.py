from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки читаются из переменных окружения (в docker compose — из .env)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "kroy"
    db_user: str = "kroy_app"
    db_password: str

    log_level: str = "INFO"

    # Ключ подписи JWT. Задаётся в .env, без него сервер не стартует.
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24

    # Сколько ждём оплату нового заказа, потом он отменяется и остаток возвращается
    order_payment_ttl_minutes: int = 15
    # test — эмулятор платёжного сервиса внутри backend (docs/stage3/db-design.md, раздел 5)
    payment_provider: str = "test"
    # Как часто фоновая задача ищет просроченные заказы
    expire_orders_interval_seconds: int = 60

    # Хранилище фото по S3 API. Без MINIO_ENDPOINT загрузка фото отвечает 503,
    # остальной сервер работает
    minio_endpoint: str | None = None
    minio_access_key: str = ""
    minio_secret_key: str = ""
    minio_bucket: str = "kroy-products"
    minio_secure: bool = False

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


settings = Settings()

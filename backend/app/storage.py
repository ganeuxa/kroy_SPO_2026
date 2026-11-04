"""Хранилище фото товаров по протоколу S3 (FR-13, docs/stage3/db-design.md, раздел 6).

Клиент minio работает с любым S3-совместимым сервером. В БД лежит только ключ
объекта, сами файлы отдаёт Nginx по /media/<ключ>.
"""

import io
import logging
from functools import lru_cache

from minio import Minio

from app.config import settings

log = logging.getLogger("kroy.storage")


class StorageUnavailable(Exception):
    pass


@lru_cache
def _client() -> Minio:
    if not settings.minio_endpoint:
        raise StorageUnavailable("MINIO_ENDPOINT не задан")
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


def _ensure_bucket(client: Minio) -> None:
    # Чтение без ключей (для Nginx /media/) настраивается в самом хранилище:
    # SeaweedFS не поддерживает политики бакетов, см. identity anonymous в compose
    bucket = settings.minio_bucket
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
        log.info("Создан бакет %s", bucket)


def put_object(key: str, data: bytes, content_type: str) -> None:
    try:
        client = _client()
        _ensure_bucket(client)
        client.put_object(settings.minio_bucket, key, io.BytesIO(data), len(data), content_type=content_type)
    except StorageUnavailable:
        raise
    except Exception as exc:
        log.error("Не удалось сохранить %s: %s", key, exc.__class__.__name__)
        raise StorageUnavailable from exc


def remove_object(key: str) -> None:
    try:
        _client().remove_object(settings.minio_bucket, key)
    except Exception as exc:
        # Строки в БД уже нет, файл без ссылки на него никому не мешает: только пишем в лог
        log.error("Не удалось удалить %s из хранилища: %s", key, exc.__class__.__name__)

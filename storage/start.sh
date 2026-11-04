#!/bin/sh
# Хранилище фото: SeaweedFS с S3 API на порту 8333 (вместо MinIO, см. docs/decisions.md).
# Ключи берутся из переменных окружения, в репозиторий не попадают.
# anonymous может только читать объекты бакета: так Nginx отдаёт /media/ без ключей,
# а список файлов и запись без ключей недоступны.
set -e

: "${MINIO_ACCESS_KEY:?Задайте MINIO_ACCESS_KEY в .env}"
: "${MINIO_SECRET_KEY:?Задайте MINIO_SECRET_KEY в .env}"
: "${MINIO_BUCKET:=kroy-products}"

cat > /tmp/s3.json <<EOF
{
  "identities": [
    {"name": "anonymous", "actions": ["Read:${MINIO_BUCKET}"]},
    {
      "name": "kroy-backend",
      "credentials": [{"accessKey": "${MINIO_ACCESS_KEY}", "secretKey": "${MINIO_SECRET_KEY}"}],
      "actions": ["Admin", "Read", "Write", "List", "Tagging"]
    }
  ]
}
EOF

# -ip.bind=0.0.0.0: в тестовом окружении у контейнера две сети, слушаем обе
exec weed server -dir=/data -ip.bind=0.0.0.0 -s3 -s3.port=8333 -s3.config=/tmp/s3.json

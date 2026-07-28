#!/bin/bash
set -e

cd /home/unaa_leasing

echo "→ Получаем изменения..."
git pull origin main

IMAGE_TAG=$(git rev-parse --short HEAD)

echo "→ Собираем образ $IMAGE_TAG"
docker build -t unaa_leasing:$IMAGE_TAG .


echo "→ Миграции..."
IMAGE_TAG=$IMAGE_TAG docker compose run --rm app python manage.py migrate --noinput


echo "→ Статика..."
IMAGE_TAG=$IMAGE_TAG docker compose run --rm app python manage.py collectstatic --noinput


echo "→ Обновляем контейнеры..."
IMAGE_TAG=$IMAGE_TAG docker compose up -d


echo "✅ Деплой завершён: $IMAGE_TAG"
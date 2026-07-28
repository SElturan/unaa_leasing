#!/bin/bash
set -e

cd /home/unaa_leasing

echo "→ Стягиваем изменения..."
git pull origin main

IMAGE_TAG=$(git rev-parse --short HEAD)
export IMAGE_TAG

echo "→ Собираем образ (unaa_leasing:$IMAGE_TAG)..."
docker build -t unaa_leasing:$IMAGE_TAG .

echo "→ Прогоняем миграции..."
docker run --rm --env-file .env --network unaa_leasing_default unaa_leasing:$IMAGE_TAG \
    python manage.py migrate --noinput

echo "→ Собираем статику..."
docker run --rm --env-file .env -v /home/unaa_leasing/static:/app/staticfiles unaa_leasing:$IMAGE_TAG \
    python manage.py collectstatic --noinput

echo "→ Обновляем стек (rolling update)..."
docker stack deploy -c docker-compose.yml unaa_leasing

echo "✅ Деплой завершён, версия: $IMAGE_TAG"
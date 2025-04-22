FROM python:3.9.12
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt /app/
RUN python -m pip install --upgrade pip

# Добавьте 'apt-get update' перед установкой пакетов
RUN apt-get update && apt-get install -y gettext

RUN pip install -r requirements.txt

COPY . .
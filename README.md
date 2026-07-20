# HUB Portal (Django + Bootstrap)

MVP-портал для сети CRM-точек и дизайнеров 3D-моделирования.

## Что реализовано

- Приём заявок из CRM по API:
  - `POST /api/v1/briefs`
  - `GET /api/v1/briefs/{brief_id}`
  - `POST /api/v1/briefs/{brief_id}`
  - `POST /api/v1/briefs/{brief_id}/messages`
- HMAC-аутентификация входящих запросов от CRM:
  - `Authorization: Bearer <site_token>`
  - `X-Site-Id`
  - `X-Timestamp`
  - `X-Signature = hex(hmac_sha256(site_secret, timestamp + "\n" + raw_body))`
- Модель зарегистрированных через Max дизайнеров.
- Bot webhook endpoint `POST /api/v1/max/webhook` с FSM-регистрацией:
  - `Регистрация: Дизайнер` → ФИО → телефон СБП → опыт → портфолио
  - после завершения регистрации бот выдаёт web-логин и пароль для входа в портал
- Команды дизайнера:
  - `Очередь`
  - `Беру <brief_id> <срок>`
  - `Уточнение <brief_id> <текст>`
  - `Готово <brief_id>`
- Web API для кабинета дизайнера:
  - `POST /api/v1/designer/auth/login`
  - `GET /api/v1/designer/briefs` (общая очередь + уже взятые задачи + кто исполнитель)
  - `POST /api/v1/designer/briefs/{brief_id}/claim` (атомарное назначение, второй дизайнер получит `409`)
- Django admin для управления точками, дизайнерами, заявками и событиями.
- Веб-кабинет дизайнеров на Django templates + Bootstrap 5:
  - `/designer/login` — вход по кредам от бота,
  - `/designer/queue` — общая очередь для всех дизайнеров,
  - `/designer/briefs/<brief_id>` — детальная карточка заявки с данными из CRM,
  - видно, кто взял задачу в работу,
  - повторный захват уже взятой задачи блокируется,
  - назначенный дизайнер меняет статус, добавляет комментарий, ссылку на финальный файл и ссылки на фото/скриншоты.
- При `has_stl=true` и наличии `model_url` HUB автоматически скачивает STL в локальное хранилище заявки.

## Быстрый старт

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Открыть в браузере:

- `http://127.0.0.1:8000/designer/login` — кабинет дизайнера
- `http://127.0.0.1:8000/admin/` — админка

## Настройки

Переменные окружения:

- `DJANGO_SECRET_KEY` — секретный ключ Django.
- `DJANGO_DEBUG` — `1` или `0`.
- `DJANGO_ALLOWED_HOSTS` — список хостов через запятую.
- `DJANGO_TIMEZONE` — часовой пояс (по умолчанию `UTC`).
- `HUB_MAX_STL_SIZE_BYTES` — лимит размера скачиваемого STL (по умолчанию 25MB).

## Порядок подключения CRM

1. В админке HUB создать `SiteNode` с `site_id`, `site_token`, `site_secret`.
2. В CRM прописать те же `site_id/token/secret` и адрес HUB.
3. Отправлять заявки в `POST /api/v1/briefs` в формате из `openapi-hub.yaml`.

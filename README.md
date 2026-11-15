# Pigeon

[English](#english) | [Русский](#русский)

---

<a id="english"></a>

# English

## Overview

**Pigeon** is an asynchronous bidirectional bridge between VK and Telegram. It allows messages to be automatically forwarded between a VK community conversation and a Telegram group.

The project is built with Python and follows a modular architecture, separating platform-specific integrations from the shared message-processing logic.

## Features

- Bidirectional message forwarding between VK and Telegram.
- Asynchronous message processing.
- Reply support with cross-platform message mapping.
- Persistent message mapping using PostgreSQL.
- Independent VK and Telegram adapters.
- Configurable source and destination conversations.
- Docker-based deployment.

### Supported message types

| Message type | Status |
|---|---|
| Text | Implemented |
| Links | Implemented |
| Replies | Implemented |
| Images | Implemented |
| Videos | impossible |
| Voice messages | Implemented |
| Documents and albums | Implemented |

## Architecture

Pigeon uses a modular architecture consisting of three main components:

- **VK Adapter** — receives messages from VK and sends messages to VK.
- **Telegram Adapter** — receives messages from Telegram and sends messages to Telegram.
- **Core** — processes incoming messages, determines their destinations, and coordinates message delivery.

PostgreSQL stores message mappings between platforms. These mappings allow Pigeon to identify the original message when a user replies to a forwarded message.

## Tech Stack

| Technology | Purpose |
|---|---|
| Python 3.14 | Main programming language |
| aiogram | Telegram Bot API integration |
| vkbottle | VK API integration |
| PostgreSQL | Persistent data storage |
| SQLAlchemy | Database ORM |
| asyncpg | Asynchronous PostgreSQL driver |

## Requirements

For local launch:

- Python 3.14
- PostgreSQL

## Installation

Clone the repository:

```bash
git clone https://github.com/YOUR_USERNAME/Pigeon.git
cd Pigeon
```

Create a virtual environment:

**Windows (PowerShell):**

```powershell
py -3.14 -m venv .venv
.venv\Scripts\Activate.ps1
```

**Linux:**

```bash
python3.14 -m venv .venv
source .venv/bin/activate
```

Install the project and its dependencies:

```bash
pip install -e .
```

## Configuration

Create a `.env` file in the project root using `.env.example` as a template.

Configure the following environment variables:

| Variable | Description |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Telegram bot token |
| `VK_GROUP_TOKEN` | VK community access token |
| `TELEGRAM_CHAT_ID` | Telegram destination group ID |
| `VK_PEER_ID` | VK destination conversation peer ID |
| `DATABASE_USER` | PostgreSQL username |
| `DATABASE_PASSWORD` | PostgreSQL password |
| `DATABASE_ADDRESS` | PostgreSQL host and port |
| `DATABASE_NAME` | PostgreSQL database name |

## Running locally

After configuring the environment and preparing the PostgreSQL database, run:

```bash
python -m pigeon_tg_vk
```

## License

This project is distributed under the MIT License. See [LICENSE](LICENSE) for details.

---

<a id="русский"></a>

# Русский

## О проекте

**Pigeon** — это асинхронный двусторонний мост между VK и Telegram, предназначенный для автоматической пересылки сообщений между беседой сообщества ВКонтакте и группой Telegram.

Проект написан на Python и использует модульную архитектуру, разделяющую интеграции с платформами и общую логику обработки сообщений.

## Возможности

- Двусторонняя пересылка сообщений между VK и Telegram.
- Асинхронная обработка сообщений.
- Поддержка ответов на сообщения с сопоставлением сообщений между платформами.
- Хранение связей между сообщениями в PostgreSQL.
- Независимые адаптеры VK и Telegram.
- Настройка исходных и целевых бесед.
- Развёртывание с помощью Docker.

### Поддерживаемые типы сообщений

| Тип сообщения | Статус |
|---|---|
| Текст | Реализовано |
| Ссылки | Реализовано |
| Ответы на сообщения | Реализовано |
| Изображения | Реализовано |
| Видео | Невозможно |
| Голосовые сообщения | Реализовано |
| Документы и альбомы | Реализовано |

## Архитектура

Pigeon построен на основе модульной архитектуры и состоит из трёх основных компонентов:

- **VK Adapter** — отвечает за получение и отправку сообщений во ВКонтакте.
- **Telegram Adapter** — отвечает за получение и отправку сообщений в Telegram.
- **Core** — обрабатывает входящие сообщения, определяет направление пересылки и координирует доставку.

Для хранения связей между сообщениями разных платформ используется PostgreSQL. Благодаря этому Pigeon может определять исходное сообщение при пересылке ответа на него.

## Используемые технологии

| Технология | Назначение |
|---|---|
| Python 3.14 | Основной язык программирования |
| aiogram | Интеграция с Telegram Bot API |
| vkbottle | Интеграция с VK API |
| PostgreSQL | Хранение данных |
| SQLAlchemy | ORM для работы с базой данных |
| asyncpg | Асинхронный драйвер PostgreSQL |

## Требования

Для локального запуска:

- Python 3.14
- PostgreSQL

## Установка

Клонируйте репозиторий:

```bash
git clone https://github.com/YOUR_USERNAME/Pigeon.git
cd Pigeon
```

Создайте виртуальное окружение:

**Windows (PowerShell):**

```powershell
py -3.14 -m venv .venv
.venv\Scripts\Activate.ps1
```

**Linux:**

```bash
python3.14 -m venv .venv
source .venv/bin/activate
```

Установите проект и его зависимости:

```bash
pip install -e .
```

## Конфигурация

Создайте файл `.env` в корневой директории проекта, используя `.env.example` в качестве шаблона.

Необходимо указать следующие переменные окружения:

| Переменная | Описание |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Токен Telegram-бота |
| `VK_GROUP_TOKEN` | Токен сообщества ВКонтакте |
| `TELEGRAM_CHAT_ID` | ID целевой группы Telegram |
| `VK_PEER_ID` | Peer ID целевой беседы ВКонтакте |
| `DATABASE_USER` | Имя пользователя PostgreSQL |
| `DATABASE_PASSWORD` | Пароль PostgreSQL |
| `DATABASE_ADDRESS` | Адрес и порт PostgreSQL |
| `DATABASE_NAME` | Название базы данных PostgreSQL |

## Локальный запуск

После настройки переменных окружения и подготовки базы данных PostgreSQL запустите приложение:

```bash
python -m pigeon_tg_vk
```

## Лицензия

Проект распространяется под лицензией MIT. Подробнее см. в файле [LICENSE](LICENSE).
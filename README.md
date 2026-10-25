# Pigeon_Tg-Vk

A bidirectional message bridge between VK group conversations and Telegram group chats.

## Overview

Pigeon_Tg-Vk is a Python project designed to forward messages between a VK group conversation and a Telegram group chat in both directions.

The planned functionality includes:
- Forwarding text messages and links.
- Supporting photos, videos, and documents.
- Preventing duplicate message delivery.
- Storing message mappings and delivery information in PostgreSQL.

## Tech Stack

- Python 3.14
- aiogram 3 — Telegram integration
- vkbottle — VK integration
- SQLAlchemy 2 — database access
- asyncpg — asynchronous PostgreSQL driver
- Alembic — database migrations
- Docker Compose — local service setup

## Project Status

The project is under active development. The features listed above describe the intended functionality and may not all be implemented yet.

## Configuration

Configuration will be provided through environment variables. Secrets such as bot tokens and database credentials must not be committed to the repository.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.

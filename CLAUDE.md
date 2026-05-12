# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run development server
python manage.py runserver

# Database migrations
python manage.py migrate
python manage.py makemigrations

# Run tests
python manage.py test
python manage.py test user_profile   # single app

# Management commands
python manage.py createsuperuser
python manage.py create_superuser    # custom command in core/management/commands/
python manage.py import_retailers    # import retailers from data file

# Legacy data migration
python import_slips.py               # imports from old_bolle.sql MySQL dump
```

## Environment

Configuration is loaded from a `.env` file in the project root (required):

```
DATABASE_URL=mysql://...
DJANGO_SECRET_KEY=...
DJANGO_DEBUG=true
EMAIL_HOST_USER=...
EMAIL_HOST_PASSWORD=...
DEFAULT_FROM_EMAIL=...
```

`dj_database_url` parses `DATABASE_URL`. `DEBUG` defaults to `False` if unset, which enables HSTS and secure cookie settings.

## Architecture

Django 5.0.1 project with three apps and a top-level `templates/` directory (not per-app templates):

### Apps

**`core`** — public website and shared models
- Public views: homepage, contact form (email via SMTP), Instagram feed, login/logout, retailers map
- Shared models used across apps: `Recipient`, `Slip`, `Retailer`, and image models (`HeroImage`, `TerritoryImage`, `AboutImage`)
- ImageKit `ImageSpecField`s auto-generate responsive WebP variants from uploaded originals

**`user_profile`** — private authenticated area (all views require `@login_required`)
- Delivery slip (bolla) CRUD: `Slip` items are stored as a JSON list on the model
- PDF generation: serializes slip data to JSON and invokes `core/static/programs/SlipDrawer/BollaDrawer-1.0-SNAPSHOT.jar` via `subprocess`; the JAR writes a PDF to a temp dir which Django reads back
- Bulk PDF printing: generates PDFs in parallel via `ThreadPoolExecutor`, then merges with `PyPDF2.PdfMerger`
- Price list management: `PriceList → PriceListItem → (PriceListItemMaterial, PriceListItemWork, PriceListItemExternalCost, PriceListItemPhoto)`
- Cost calculation chain on `PriceListItem`: `final_cost = primary_total (materials) + secondary_total (works) + external_total (fixed + percentage external costs)`; percentage costs can apply to materials, works, subtotal, or subtotal+fixed
- Price list editor views use a dual-response pattern: if `X-Requested-With: XMLHttpRequest`, return the partial template `price_list_item_editor_partial.html`; otherwise redirect with a Django message

**`product_collections`** — public product catalogue
- `Collection → Item → ItemImage` with ImageKit thumbnails/detail views

### Key cross-app dependency

`Slip` and `Recipient` are defined in `core/models.py` but managed primarily from `user_profile/views.py`. Import them as `from core.models import Slip, Recipient`.

### Static files and serving

- WhiteNoise serves static files in production
- Media files are served via a `re_path` route in `django_tendresse/urls.py`
- ASGI server is Daphne (`ASGI_APPLICATION = 'django_tendresse.asgi.application'`)

### PDF slip generation dependency

The Java JAR at `core/static/programs/SlipDrawer/BollaDrawer-1.0-SNAPSHOT.jar` must be present and `java` must be on PATH for slip download and bulk-print features to work.

# Django Tendresse

A Django web application for "Tendresse," a knitwear company. The project features a public-facing website and a private user area for managing delivery slips and recipients.

## Live Website

The website is live at [https://tendresse.it/](https://tendresse.it/).

## Showcase

Below is a screenshot of the website homepage. Click the image to open the full-size version on GitHub, or visit the live site linked above.

[![Tendresse website homepage](https://raw.githubusercontent.com/Morelli-01/django_tendresse/main/core/static/images/website_home.png)](https://raw.githubusercontent.com/Morelli-01/django_tendresse/main/core/static/images/website_home.png)

Caption: Homepage screenshot (sourced from the repository image `core/static/images/website_home.png`).

## Features

* **Public Website:** Includes a homepage, contact page, and an Instagram feed integration.
* **User Management:** Secure user login and logout functionality.
* **Dashboard:** A private user dashboard to manage delivery slips.
* **Recipient Management:** Users can add, edit, and delete recipient details for delivery slips.
* **Delivery Slip Management:** Users can create, edit, delete, and download delivery slips.

## Technologies Used

* **Backend:** Django
* **Database:** MySQL
* **Frontend:** Bootstrap 5, AOS (Animate On Scroll), Font Awesome, Google Fonts
* **Image Processing:** Django ImageKit

## Setup

1.  Clone the repository.
2.  Install dependencies.
3.  Configure your MySQL database settings in `django_tendresse/settings.py`.
4.  Run migrations to create the database schema.
5.  Create a superuser to access the admin panel.

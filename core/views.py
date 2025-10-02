import json
from django.shortcuts import render, redirect
import requests
from .models import TerritoryImage, AboutImage ,HeroImage, Retailer
import random
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings

def home(request):
    """
    Renders the home page with dynamic content and optimized images.
    """
    # Query all TerritoryImage objects from the database
    territory_images = TerritoryImage.objects.all()
    about_images = AboutImage.objects.all()
    hero_image = HeroImage.objects.order_by('?').first()

    context = {
        # ... your existing context
        "page_title": {
            "it": "Tendresse - Maglieria dal 1992",
            "en": "Tendresse - Knitwear since 1992",
        },
        "meta_description": {
            "it": "Tendresse è una piccola azienda di maglieria con sede a Carpi, fondata nel 1992. Realizziamo capi di alta qualità con passione e cura artigianale.",
            "en": "Tendresse is a small knitwear company based in Carpi, founded in 1992. We create high-quality garments with passion and craftsmanship.",
        },
        "hero_title": {
            "it": "Tendresse, Maglieria dal 1992",
            "en": "Tendresse, Knitwear since 1992",
        },
        "hero_subtitle": {
            "it": "Artigianalità e passione, da oltre 30 anni nel cuore di Carpi.",
            "en": "Craftsmanship and passion, for over 30 years in the heart of Carpi.",
        },
        "about_title": {"it": "La Nostra Storia", "en": "Our History"},
        "about_text": {
            "it": "Tendresse è una piccola azienda di maglieria con sede a Carpi, fondata nel 1992. Da allora, l'azienda ha costruito una solida reputazione nella produzione di capi di maglieria femminile. Specializzandosi nella lavorazione dei tessuti e nella creazione di design unici, Tendresse si distingue per l'attenzione ai dettagli e la cura artigianale che mette in ogni prodotto. Utilizzando materiali pregiati e tecnologie moderne, l'azienda si impegna a garantire capi confortevoli, durevoli e alla moda.",
            "en": "Tendresse is a small knitwear company based in Carpi, founded in 1992. Since then, the company has built a solid reputation in the production of women's knitwear. Specializing in fabric processing and the creation of unique designs, Tendresse stands out for its attention to detail and the craftsmanship it puts into every product. Using fine materials and modern technologies, the company is committed to ensuring comfortable, durable, and fashionable garments.",
        },
        "territory_title": {
            "it": "Il Legame con il Territorio",
            "en": "The Bond with the Territory",
        },
        "territory_text": {
            "it": "Tendresse è profondamente radicata nel territorio in cui opera, ed è una parte preziosa della nostra comunità. Siamo fortemente legati al nostro territorio non solo grazie alla nostra passione per la produzione di maglieria di alta qualità, ma anche grazie ai nostri fidati fornitori e collaboratori locali. Siamo orgogliosi di essere una ditta di maglieria che si impegna a preservare le tradizioni artigianali locali e a offrire prodotti che riflettono l'eccellenza del nostro territorio.",
            "en": "Tendresse is deeply rooted in the territory in which it operates, and is a precious part of our community. We are strongly linked to our territory not only thanks to our passion for the production of high-quality knitwear, but also thanks to our trusted local suppliers and collaborators. We are proud to be a knitwear company that is committed to preserving local craft traditions and offering products that reflect the excellence of our territory.",
        },
        "cta_title": {"it": "Vieni a Trovarci", "en": "Come and Visit Us"},
        "cta_text": {
            "it": "Siamo a tua disposizione per mostrarti le nostre creazioni.",
            "en": "We are at your disposal to show you our creations.",
        },
        "cta_button": {
            "it": "Orari e Dove trovarci",
            "en": "Opening Hours and Where to find us",
        },
        # Use the new query instead of the hardcoded list
        "territory_images": territory_images,
        "about_images": about_images,
        "hero_image": hero_image,
    }
    return render(request, "tendresse/home.html", context)

def contact(request):
    """
    Renders the contact and hours page.
    """
    return render(request, 'tendresse/contact.html')

def contact(request):
    if request.method == 'POST':
        print(request.POST)
        name = request.POST.get('name')
        email = request.POST.get('email')
        message = request.POST.get('message')
        
        # Send email
        try:
            send_mail(
                subject=f'Contact form message from {name}',
                message=f'From: {name} ({email})\n\nMessage:\n{message}',
                from_email=email,
                recipient_list=['info@tendresse.it'],
                fail_silently=False,
            )
            messages.success(request, 'Messaggio inviato con successo!')
            print(request, 'Messaggio inviato con successo!')
        except Exception as e:
            messages.error(request, 'Errore nell\'invio del messaggio.')
            print(request, 'Errore nell\'invio del messaggio.')
        
        return redirect('contact')
    
    return render(request, 'tendresse/contact.html')

def instagram_feed(request):
    """
    Renders the page to display the Instagram feed.
    """
    context = {
        "page_title": {
            "it": "Tendresse - Instagram",
            "en": "Tendresse - Instagram",
        },
        "meta_description": {
            "it": "Visita il nostro profilo Instagram per scoprire le ultime novità e ispirazioni.",
            "en": "Visit our Instagram profile to discover the latest news and inspirations.",
        },
    }
    return render(request, "tendresse/instagram.html", context)

def login_view(request):
    """
    Renders the login page and handles login form submission.
    """
    # If the request is a POST, it means the form was submitted
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            messages.success(request, 'Login successful!')
            return redirect('home') # Redirect to home page on success
        else:
            messages.error(request, 'Invalid username or password.') # Display an error message

    context = {
        "page_title": {
            "it": "Accedi",
            "en": "Login",
        },
    }
    return render(request, "tendresse/login.html", context)

def logout_view(request):
    logout(request)
    return redirect('home')

def retailers(request):
    """
    Renders the retailers page.
    """
    retailers = Retailer.objects.all()
    retailers_by_region = {}

    for retailer in retailers:
        if retailer.region not in retailers_by_region:
            retailers_by_region[retailer.region] = []
        retailers_by_region[retailer.region].append(retailer)

    context = {
        'retailers_by_region': retailers_by_region,
    }
    return render(request, 'tendresse/retailers.html', context)
from django.db import models
from imagekit.models import ImageSpecField
from imagekit.processors import ResizeToFill
from django.contrib.auth.models import User
import json

class TerritoryImage(models.Model):
    """
    A model to store and process images for the territory section.
    """
    # This field will store the original, high-resolution image file.
    original_image = models.ImageField(upload_to='territory_images/')

    # This ImageSpecField will automatically create a large-sized version (e.g., for desktop).
    carousel_large = ImageSpecField(
        source='original_image',
        processors=[ResizeToFill(1200, 800)],
        format='WEBP', # Use WebP for better compression
        options={'quality': 80}
    )

    # This ImageSpecField will automatically create a medium-sized version (e.g., for tablets).
    carousel_medium = ImageSpecField(
        source='original_image',
        processors=[ResizeToFill(800, 533)], # Maintain aspect ratio
        format='WEBP',
        options={'quality': 70}
    )

    # This ImageSpecField will automatically create a small-sized version (e.g., for mobile).
    carousel_small = ImageSpecField(
        source='original_image',
        processors=[ResizeToFill(400, 267)],
        format='WEBP',
        options={'quality': 60}
    )

    def __str__(self):
        return f"Territory Image - {self.original_image.name}"

    class Meta:
        verbose_name = "Territory Image"
        verbose_name_plural = "Territory Images"

class AboutImage(models.Model):
    """
    Model to handle images for the "Our Story" section.
    """
    original_image = models.ImageField(upload_to='about_images/')

    # Image spec for small/tablet screens (based on col-md-6)
    about_medium = ImageSpecField(
        source='original_image',
        processors=[ResizeToFill(480, 720)],
        format='WEBP',
        options={'quality': 70}
    )

    # Image spec for large/desktop screens (based on col-md-6)
    about_large = ImageSpecField(
        source='original_image',
        processors=[ResizeToFill(760, 1140)],
        format='WEBP',
        options={'quality': 80}
    )
    
    def __str__(self):
        return f"About Section Image - {self.original_image.name}"

    class Meta:
        verbose_name = "About Section Image"
        verbose_name_plural = "About Section Images"

class HeroImage(models.Model):
    """
    Model to handle the hero background image.
    """
    original_image = models.ImageField(upload_to='hero_images/')

    # Spec for desktop screens (Full HD resolution is a good target)
    hero_desktop = ImageSpecField(
        source='original_image',
        processors=[ResizeToFill(1920, 1080)], # Standard widescreen HD
        format='WEBP',
        options={'quality': 80}
    )

    # Spec for mobile screens (portrait orientation)
    hero_mobile = ImageSpecField(
        source='original_image',
        processors=[ResizeToFill(1024, 768)], # Good for most mobile devices
        format='WEBP',
        options={'quality': 70}
    )
    
    def __str__(self):
        return f"Hero Image - {self.original_image.name}"

    class Meta:
        verbose_name = "Hero Image"
        verbose_name_plural = "Hero Images"

class Recipient(models.Model):
    """
    Model to store details of a recipient for delivery slips.
    """
    company_name = models.CharField(max_length=255, verbose_name="Ragione Sociale / Nome")
    address_line1 = models.CharField(max_length=255, verbose_name="Indirizzo / Linea 1")
    address_line2 = models.CharField(max_length=255, blank=True, null=True, verbose_name="Indirizzo / Linea 2")
    city = models.CharField(max_length=100, verbose_name="Città")
    postal_code = models.CharField(max_length=20, verbose_name="CAP")
    province_sigla = models.CharField(max_length=10, blank=True, null=True, verbose_name="Provincia (Sigla)")
    country = models.CharField(max_length=100, verbose_name="Paese", default="Italia")
    phone = models.CharField(max_length=50, blank=True, null=True, verbose_name="Telefono")
    email = models.EmailField(blank=True, null=True, verbose_name="Email")
    vat_number = models.CharField(max_length=50, blank=True, null=True, verbose_name="Partita IVA / Codice Fiscale")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recipients', null=True, blank=True)

    class Meta:
        verbose_name = "Destinatario"
        verbose_name_plural = "Destinatari"
        ordering = ['company_name']

    def __str__(self):
        return f"{self.company_name} - {self.city}, {self.country}"

class Slip(models.Model):
    """
    Model to store delivery/shipping slips with separate slip number and year fields.
    """
    slip_number = models.IntegerField(verbose_name="Numero Bolla")
    slip_year = models.PositiveIntegerField(verbose_name="Anno")
    full_slip_number = models.CharField(max_length=50, unique=True, verbose_name="Numero Bolla Completo", editable=False)
    date = models.DateField(verbose_name="Data")
    recipient = models.ForeignKey(Recipient, on_delete=models.CASCADE, related_name='slips', verbose_name="Destinatario")
    
    different_address = models.JSONField(blank=True, null=True, verbose_name="Indirizzo di Consegna Diverso")

    lavorazione = models.CharField(max_length=50, blank=True, null=True, verbose_name="Lavorazione")
    resp_spedizione = models.CharField(max_length=50, blank=True, null=True, verbose_name="Responsabile Spedizione")
    data_trasp = models.DateField(blank=True, null=True, verbose_name="Data Trasporto")
    aspetto = models.CharField(max_length=50, blank=True, null=True, verbose_name="Aspetto dei beni")
    
    items = models.JSONField(default=list, verbose_name="Articoli")
    notes = models.TextField(blank=True, null=True, verbose_name="Note")
    
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='slips', verbose_name="Creato da")

    class Meta:
        verbose_name = "Bolla di Consegna"
        verbose_name_plural = "Bolle di Consegna"
        ordering = ['-date', '-slip_number']
        unique_together = ('slip_number', 'slip_year')

    def save(self, *args, **kwargs):
        # Generate full slip number as combination of slip_number and slip_year
        self.full_slip_number = f"{self.slip_number}-{self.slip_year}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Bolla #{self.full_slip_number} del {self.date.strftime('%d/%m/%Y')} a {self.recipient.company_name}"

    def get_total_quantity(self):
        total = 0.0
        try:
            for item in self.items:
                quantity = item.get('quantity', 0)
                if isinstance(quantity, str):
                    quantity = quantity.replace(',', '.')
                total += float(quantity)
        except (ValueError, TypeError):
            pass
        return total

    def get_items_display(self):
        if not self.items:
            return "Nessun articolo"
        
        display_list = []
        for item in self.items:
            desc = item.get('description', 'N/A')
            qty = item.get('quantity', 'N/A')
            unit = item.get('unit', 'pz')
            display_list.append(f"{qty} {unit} - {desc}")
        return ", ".join(display_list)
    
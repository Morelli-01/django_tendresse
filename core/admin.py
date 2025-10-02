from django.contrib import admin
from core.models import HeroImage, TerritoryImage, AboutImage, Recipient, Slip, Retailer

@admin.register(TerritoryImage)
class TerritoryImageAdmin(admin.ModelAdmin):
    list_display = ('original_image',)

@admin.register(AboutImage)
class AboutImageImageAdmin(admin.ModelAdmin):
    list_display = ('original_image',)

@admin.register(HeroImage)
class HeroImageAdmin(admin.ModelAdmin):
    list_display = ('original_image',)

@admin.register(Retailer)
class RetailerAdmin(admin.ModelAdmin):
    list_display = ('name', 'street', 'postal_code', 'city', 'province', 'region', 'country', 'vat_number', 'fiscal_code', 'phone')
    search_fields = ('name', 'street', 'city', 'province', 'region', 'country', 'vat_number', 'fiscal_code')

@admin.register(Recipient)
class RecipientAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'city', 'province_sigla', 'country', 'email', 'created_by')
    search_fields = ('company_name', 'city', 'vat_number')
    list_filter = ('created_by', 'country')
    fieldsets = (
        (None, {
            'fields': ('company_name', 'address_line1', 'address_line2', 'city', 'postal_code', 'province_sigla', 'country', 'phone', 'email', 'vat_number')
        }),
    )

@admin.register(Slip)
class SlipAdmin(admin.ModelAdmin):
    list_display = ('slip_number', 'date', 'recipient', 'lavorazione', 'get_total_quantity')
    list_filter = ('date', 'recipient', 'created_by')
    search_fields = ('slip_number', 'recipient__company_name', 'items')
    fieldsets = (
        (None, {
            'fields': ('slip_number', 'date', 'recipient', 'lavorazione', 'resp_spedizione', 'data_trasp', 'aspetto', 'notes', 'created_by')
        }),
        ('Articoli', {
            'fields': ('items',),
            'description': 'Inserisci gli articoli in formato JSON. Es: [{"description": "Maglione", "quantity": 10, "unit": "pezzi"}]'
        }),
    )

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
from django.contrib import admin
from .models import Collection, Item, ItemImage

class ItemImageInline(admin.TabularInline):
    model = ItemImage
    extra = 1

class ItemInline(admin.TabularInline):
    model = Item
    extra = 1
    inlines = [ItemImageInline]

@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = ('name', 'season', 'year')
    search_fields = ('name', 'season', 'year')
    inlines = [ItemInline]

@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'unique_code', 'collection')
    search_fields = ('name', 'unique_code', 'collection__name')
    inlines = [ItemImageInline]

@admin.register(ItemImage)
class ItemImageAdmin(admin.ModelAdmin):
    list_display = ('item', 'is_main', 'order')
    list_filter = ('is_main',)
    raw_id_fields = ('item',)
from django.contrib import admin

from .models import (
    PriceList,
    PriceListItem,
    PriceListItemExternalCost,
    PriceListItemMaterial,
    PriceListItemPhoto,
    PriceListItemWork,
)


class PriceListItemPhotoInline(admin.TabularInline):
    model = PriceListItemPhoto
    extra = 0
    fields = ("original_image", "is_main", "order")


class PriceListItemMaterialInline(admin.TabularInline):
    model = PriceListItemMaterial
    extra = 0
    fields = ("material_type", "description", "supplier", "quantity", "unit", "unit_cost", "waste_pct", "sort_order")


class PriceListItemWorkInline(admin.TabularInline):
    model = PriceListItemWork
    extra = 0
    fields = ("operation_name", "quantity", "unit", "unit_cost", "sort_order")


class PriceListItemExternalCostInline(admin.TabularInline):
    model = PriceListItemExternalCost
    extra = 0
    fields = ("description", "cost_type", "amount", "applies_to", "sort_order")


class PriceListItemInline(admin.TabularInline):
    model = PriceListItem
    extra = 0
    fields = ("sku", "name", "is_active", "sort_order")


@admin.register(PriceList)
class PriceListAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at")
    search_fields = ("name",)
    ordering = ("-created_at",)
    inlines = [PriceListItemInline]


@admin.register(PriceListItem)
class PriceListItemAdmin(admin.ModelAdmin):
    list_display = ("sku", "name", "price_list", "final_cost", "is_active")
    list_filter = ("price_list", "is_active")
    search_fields = ("sku", "name", "price_list__name")
    ordering = ("price_list", "sort_order", "id")
    inlines = [
        PriceListItemPhotoInline,
        PriceListItemMaterialInline,
        PriceListItemWorkInline,
        PriceListItemExternalCostInline,
    ]

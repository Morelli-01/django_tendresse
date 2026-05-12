from decimal import Decimal, ROUND_HALF_UP

from django.db import models
from imagekit.models import ImageSpecField
from imagekit.processors import ResizeToFill


MONEY_DECIMAL = Decimal("0.01")
ZERO_MONEY = Decimal("0.00")


def quantize_money(value):
    return value.quantize(MONEY_DECIMAL, rounding=ROUND_HALF_UP)


class PriceList(models.Model):
    name = models.CharField(max_length=255, verbose_name="Nome")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creato il")

    class Meta:
        verbose_name = "Listino Prezzi"
        verbose_name_plural = "Listini Prezzi"
        ordering = ["-created_at", "name"]

    def __str__(self):
        return self.name


class PriceListItem(models.Model):
    class MaterialType(models.TextChoices):
        YARN = "yarn", "Filato"
        BUTTON = "button", "Bottone"
        ACCESSORY = "accessory", "Accessorio"
        LABEL = "label", "Etichetta"
        OTHER = "other", "Altro"

    class MaterialUnit(models.TextChoices):
        PIECE = "pz", "Pezzo"
        GRAM = "g", "Grammi"
        KILO = "kg", "Chili"
        METER = "m", "Metri"
        CENTIMETER = "cm", "Centimetri"

    class ExternalCostType(models.TextChoices):
        FIXED = "fixed", "Fisso"
        PERCENTAGE = "percentage", "Percentuale"

    class ExternalCostBase(models.TextChoices):
        MATERIALS = "materials", "Materiali"
        WORKS = "works", "Lavorazioni"
        SUBTOTAL = "subtotal", "Subtotale"
        SUBTOTAL_PLUS_FIXED = "subtotal_plus_fixed", "Subtotale + costi fissi"

    price_list = models.ForeignKey(
        PriceList,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="Listino Prezzi",
    )
    sku = models.CharField(max_length=100, blank=True, default="", verbose_name="Codice / SKU")
    name = models.CharField(max_length=255, verbose_name="Nome")
    description = models.TextField(blank=True, null=True, verbose_name="Descrizione")
    notes = models.TextField(blank=True, null=True, verbose_name="Note")
    is_active = models.BooleanField(default=True, verbose_name="Attivo")
    sort_order = models.PositiveIntegerField(default=0, verbose_name="Ordine")

    class Meta:
        verbose_name = "Capo Listino"
        verbose_name_plural = "Capi Listino"
        ordering = ["sort_order", "id"]

    def __str__(self):
        if self.sku:
            return f"{self.name} ({self.sku})"
        return self.name

    @property
    def main_photo(self):
        main_photo = self.photos.filter(is_main=True).first()
        if main_photo:
            return main_photo
        return self.photos.order_by("order", "id").first()

    @property
    def primary_total(self):
        total = sum((material.subtotal for material in self.materials.all()), ZERO_MONEY)
        return quantize_money(total)

    @property
    def secondary_total(self):
        total = sum((work.subtotal for work in self.works.all()), ZERO_MONEY)
        return quantize_money(total)

    @property
    def external_fixed_total(self):
        total = sum(
            (cost.subtotal(material_total=self.primary_total, work_total=self.secondary_total, fixed_external_total=ZERO_MONEY)
             for cost in self.external_costs.filter(cost_type=self.ExternalCostType.FIXED)),
            ZERO_MONEY,
        )
        return quantize_money(total)

    @property
    def external_total(self):
        material_total = self.primary_total
        work_total = self.secondary_total
        fixed_external_total = sum(
            (
                cost.subtotal(
                    material_total=material_total,
                    work_total=work_total,
                    fixed_external_total=ZERO_MONEY,
                )
                for cost in self.external_costs.filter(cost_type=self.ExternalCostType.FIXED)
            ),
            ZERO_MONEY,
        )
        percentage_total = sum(
            (
                cost.subtotal(
                    material_total=material_total,
                    work_total=work_total,
                    fixed_external_total=fixed_external_total,
                )
                for cost in self.external_costs.filter(cost_type=self.ExternalCostType.PERCENTAGE)
            ),
            ZERO_MONEY,
        )
        return quantize_money(fixed_external_total + percentage_total)

    @property
    def final_cost(self):
        return quantize_money(self.primary_total + self.secondary_total + self.external_total)


class PriceListItemPhoto(models.Model):
    item = models.ForeignKey(
        PriceListItem,
        on_delete=models.CASCADE,
        related_name="photos",
        verbose_name="Capo Listino",
    )
    original_image = models.ImageField(upload_to="price_list_items/")
    is_main = models.BooleanField(default=False, verbose_name="Principale")
    order = models.PositiveIntegerField(default=0, verbose_name="Ordine")

    thumbnail = ImageSpecField(
        source="original_image",
        processors=[ResizeToFill(240, 320)],
        format="WEBP",
        options={"quality": 80},
    )
    detail_view = ImageSpecField(
        source="original_image",
        processors=[ResizeToFill(720, 960)],
        format="WEBP",
        options={"quality": 85},
    )

    class Meta:
        verbose_name = "Foto Capo Listino"
        verbose_name_plural = "Foto Capi Listino"
        ordering = ["order", "id"]

    def __str__(self):
        return f"Foto {self.item.name} #{self.order}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_main:
            self.item.photos.exclude(pk=self.pk).update(is_main=False)
        elif not self.item.photos.exclude(pk=self.pk).filter(is_main=True).exists():
            self.item.photos.filter(pk=self.pk).update(is_main=True)
            self.is_main = True


class PriceListItemMaterial(models.Model):
    item = models.ForeignKey(
        PriceListItem,
        on_delete=models.CASCADE,
        related_name="materials",
        verbose_name="Capo Listino",
    )
    material_type = models.CharField(
        max_length=20,
        choices=PriceListItem.MaterialType.choices,
        default=PriceListItem.MaterialType.YARN,
        verbose_name="Tipo materiale",
    )
    description = models.CharField(max_length=255, verbose_name="Descrizione")
    supplier = models.CharField(max_length=255, blank=True, default="", verbose_name="Fornitore")
    unit = models.CharField(max_length=20, blank=True, default="pz", verbose_name="Unita")
    quantity = models.DecimalField(max_digits=10, decimal_places=3, default=0, verbose_name="Quantita")
    unit_cost = models.DecimalField(max_digits=12, decimal_places=4, default=0, verbose_name="Costo unitario")
    waste_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name="Sfrido %")
    sort_order = models.PositiveIntegerField(default=0, verbose_name="Ordine")
    notes = models.TextField(blank=True, default="", verbose_name="Note")

    class Meta:
        verbose_name = "Materiale Primario"
        verbose_name_plural = "Materiali Primari"
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.description

    @property
    def subtotal(self):
        base_total = self.quantity * self.unit_cost
        if self.waste_pct:
            base_total *= Decimal("1") + (self.waste_pct / Decimal("100"))
        return quantize_money(base_total)


class PriceListItemWork(models.Model):
    item = models.ForeignKey(
        PriceListItem,
        on_delete=models.CASCADE,
        related_name="works",
        verbose_name="Capo Listino",
    )
    operation_name = models.CharField(max_length=255, verbose_name="Lavorazione")
    quantity = models.DecimalField(max_digits=10, decimal_places=3, default=0, verbose_name="Quantita")
    unit = models.CharField(max_length=20, blank=True, default="pz", verbose_name="Unita")
    unit_cost = models.DecimalField(max_digits=12, decimal_places=4, default=0, verbose_name="Costo unitario")
    sort_order = models.PositiveIntegerField(default=0, verbose_name="Ordine")
    notes = models.TextField(blank=True, default="", verbose_name="Note")

    class Meta:
        verbose_name = "Lavorazione"
        verbose_name_plural = "Lavorazioni"
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.operation_name

    @property
    def subtotal(self):
        return quantize_money(self.quantity * self.unit_cost)


class PriceListItemExternalCost(models.Model):
    item = models.ForeignKey(
        PriceListItem,
        on_delete=models.CASCADE,
        related_name="external_costs",
        verbose_name="Capo Listino",
    )
    cost_type = models.CharField(
        max_length=20,
        choices=PriceListItem.ExternalCostType.choices,
        default=PriceListItem.ExternalCostType.FIXED,
        verbose_name="Tipo costo",
    )
    description = models.CharField(max_length=255, verbose_name="Descrizione")
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Valore")
    applies_to = models.CharField(
        max_length=30,
        choices=PriceListItem.ExternalCostBase.choices,
        default=PriceListItem.ExternalCostBase.SUBTOTAL,
        verbose_name="Applica a",
    )
    sort_order = models.PositiveIntegerField(default=0, verbose_name="Ordine")
    notes = models.TextField(blank=True, default="", verbose_name="Note")

    class Meta:
        verbose_name = "Costo Esterno"
        verbose_name_plural = "Costi Esterni"
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.description

    def subtotal(self, material_total, work_total, fixed_external_total):
        if self.cost_type == PriceListItem.ExternalCostType.FIXED:
            return quantize_money(self.amount)

        base_map = {
            PriceListItem.ExternalCostBase.MATERIALS: material_total,
            PriceListItem.ExternalCostBase.WORKS: work_total,
            PriceListItem.ExternalCostBase.SUBTOTAL: material_total + work_total,
            PriceListItem.ExternalCostBase.SUBTOTAL_PLUS_FIXED: material_total + work_total + fixed_external_total,
        }
        calculation_base = base_map.get(self.applies_to, material_total + work_total)
        return quantize_money(calculation_base * (self.amount / Decimal("100")))

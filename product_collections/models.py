from django.db import models
from imagekit.models import ImageSpecField
from imagekit.processors import ResizeToFill

class Collection(models.Model):
    name = models.CharField(max_length=255)
    season = models.CharField(max_length=50)
    year = models.IntegerField()
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.name} ({self.season} {self.year})"

class Item(models.Model):
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE, related_name='items')
    unique_code = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.name} ({self.unique_code})"

class ItemImage(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='images')
    original_image = models.ImageField(upload_to='collection_items/')
    is_main = models.BooleanField(default=False)
    order = models.IntegerField(default=0)

    thumbnail = ImageSpecField(
        source='original_image',
        processors=[ResizeToFill(300, 300)],
        format='WEBP',
        options={'quality': 80}
    )
    detail_view = ImageSpecField(
        source='original_image',
        processors=[ResizeToFill(600, 800)],
        format='WEBP',
        options={'quality': 80}
    )

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.item.name} Image ({self.order})"
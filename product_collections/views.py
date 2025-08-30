from django.shortcuts import render, get_object_or_404
from .models import Collection, Item, ItemImage


def collection_list_view(request):
    """
    Displays a list of all product collections with their main image.
    """
    collections_with_images = []
    collections = Collection.objects.all().order_by('-year', 'name')

    for collection in collections:
        # Try to find an item with a main image for the collection's display
        main_item = Item.objects.filter(collection=collection).first()
        if main_item:
            main_image = ItemImage.objects.filter(item=main_item, is_main=True).first()
            if not main_image:
                main_image = ItemImage.objects.filter(item=main_item).order_by('order').first()
        else:
            main_image = None
        
        collections_with_images.append({
            'collection': collection,
            'main_image': main_image,
        })

    context = {
        'page_title': 'Collections',
        'collections': collections_with_images,
    }
    return render(request, 'collections/collection_list.html', context)


def collection_detail_view(request, pk):
    """
    Displays the details of a single collection and its items.
    """
    collection = get_object_or_404(Collection, pk=pk)
    items = Item.objects.filter(collection=collection).prefetch_related('images').order_by('name')

    context = {
        'page_title': f"{collection.name} ({collection.year})",
        'collection': collection,
        'items': items,
    }
    return render(request, 'collections/collection_detail.html', context)
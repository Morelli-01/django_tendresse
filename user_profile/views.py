# file: user_profile/views.py
from decimal import Decimal, InvalidOperation

from django.db import models
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from core.models import Slip, Recipient
import json
from django.http import HttpResponse
from datetime import date
from django.db import IntegrityError
from django.db.models import Max
from django.conf import settings
from django.urls import reverse
import subprocess
import tempfile
import os
from io import BytesIO
from PyPDF2 import PdfMerger
import concurrent.futures

from .models import (
    PriceList,
    PriceListItem,
    PriceListItemExternalCost,
    PriceListItemMaterial,
    PriceListItemPhoto,
    PriceListItemWork,
)


WORK_PRESETS = {
    "confezionatura": {
        "label": "Confezionatura",
        "quantity": Decimal("1"),
        "unit": "pz",
        "unit_cost": Decimal("1.50"),
    },
    "lavanderia": {
        "label": "Lavanderia",
        "quantity": Decimal("1"),
        "unit": "pz",
        "unit_cost": Decimal("0.40"),
    },
    "smacchinatura": {
        "label": "Smacchinatura",
        "quantity": Decimal("1"),
        "unit": "pz",
        "unit_cost": Decimal("4.10"),
    },
    "attaccatura_bottoni": {
        "label": "Attaccatura Bottoni",
        "quantity": Decimal("6"),
        "unit": "bottoni",
        "unit_cost": Decimal("0.10"),
    },
    "cartellino": {
        "label": "Cartellino",
        "quantity": Decimal("1"),
        "unit": "pz",
        "unit_cost": Decimal("0.16"),
    },
    "stiro": {
        "label": "Stiro",
        "quantity": Decimal("1"),
        "unit": "pz",
        "unit_cost": Decimal("1.50"),
    },
}

EXTERNAL_COST_PRESETS = {
    "generali": {
        "label": "Generali",
        "cost_type": PriceListItem.ExternalCostType.FIXED,
        "amount": Decimal("2.32"),
        "applies_to": PriceListItem.ExternalCostBase.SUBTOTAL,
    },
    "margine": {
        "label": "Margine",
        "cost_type": PriceListItem.ExternalCostType.PERCENTAGE,
        "amount": Decimal("33.00"),
        "applies_to": PriceListItem.ExternalCostBase.SUBTOTAL_PLUS_FIXED,
    },
}


def is_dynamic_request(request):
    return request.headers.get("x-requested-with") == "XMLHttpRequest"


def parse_decimal_input(raw_value, default=Decimal("0")):
    normalized_value = (raw_value or "").strip().replace(",", ".")
    if not normalized_value:
        return default

    try:
        return Decimal(normalized_value)
    except InvalidOperation as exc:
        raise ValueError from exc


def normalize_choice(raw_value, choices, default_value):
    valid_values = {choice_value for choice_value, _ in choices}
    if raw_value in valid_values:
        return raw_value
    return default_value


def add_editor_message(request, message_text, message_tag):
    if message_tag == "danger":
        messages.error(request, message_text)
    elif message_tag == "warning":
        messages.warning(request, message_text)
    else:
        messages.success(request, message_text)


def get_next_sort_order(queryset, field_name="sort_order"):
    aggregate_key = f"max_{field_name}"
    return (queryset.aggregate(**{aggregate_key: Max(field_name)})[aggregate_key] or 0) + 1


def get_price_list_detail_url(price_list, active_item=None):
    if active_item is not None:
        return get_price_list_item_edit_url(price_list, active_item)
    return reverse("price_list_detail", kwargs={"pk": price_list.pk})


def get_price_list_item_edit_url(price_list, active_item):
    return reverse(
        "price_list_item_edit",
        kwargs={"pk": price_list.pk, "item_pk": active_item.pk},
    )


def get_item_editor_tab(request, default_tab="general"):
    return (request.GET.get("tab") or request.POST.get("active_tab") or default_tab).strip() or default_tab


def build_price_list_item_editor_context(
    price_list,
    active_item,
    active_tab="general",
    editor_message=None,
    editor_message_tag="success",
):
    active_item = (
        price_list.items.prefetch_related("photos", "materials", "works", "external_costs")
        .filter(pk=active_item.pk)
        .first()
    )

    return {
        "price_list": price_list,
        "active_item": active_item,
        "material_type_choices": PriceListItem.MaterialType.choices,
        "material_unit_choices": PriceListItem.MaterialUnit.choices,
        "external_cost_type_choices": PriceListItem.ExternalCostType.choices,
        "external_cost_base_choices": PriceListItem.ExternalCostBase.choices,
        "work_presets": WORK_PRESETS,
        "external_cost_presets": EXTERNAL_COST_PRESETS,
        "active_tab": active_tab,
        "editor_message": editor_message,
        "editor_message_tag": editor_message_tag,
    }


def render_price_list_item_editor_partial(
    request,
    price_list,
    active_item,
    active_tab="general",
    editor_message=None,
    editor_message_tag="success",
    status=200,
):
    context = build_price_list_item_editor_context(
        price_list,
        active_item,
        active_tab=active_tab,
        editor_message=editor_message,
        editor_message_tag=editor_message_tag,
    )
    return render(request, "user_profile/price_list_item_editor_partial.html", context, status=status)


def redirect_to_price_list_editor(
    request,
    price_list,
    active_item=None,
    editor_message=None,
    editor_message_tag="success",
    status=200,
    active_tab="general",
):
    if active_item is not None and is_dynamic_request(request):
        return render_price_list_item_editor_partial(
            request,
            price_list,
            active_item,
            active_tab=active_tab,
            editor_message=editor_message,
            editor_message_tag=editor_message_tag,
            status=status,
        )

    if editor_message:
        add_editor_message(request, editor_message, editor_message_tag)

    redirect_url = get_price_list_detail_url(price_list, active_item=active_item)
    if active_item is not None and active_tab:
        redirect_url = f"{redirect_url}?tab={active_tab}"
    return redirect(redirect_url)


def get_price_list_item_or_404(price_list_pk, item_pk):
    price_list = get_object_or_404(PriceList, pk=price_list_pk)
    price_list_item = get_object_or_404(PriceListItem, pk=item_pk, price_list=price_list)
    return price_list, price_list_item


def ensure_item_has_main_photo(price_list_item):
    if price_list_item.photos.filter(is_main=True).exists():
        return

    fallback_photo = price_list_item.photos.order_by("order", "id").first()
    if fallback_photo:
        fallback_photo.is_main = True
        fallback_photo.save(update_fields=["is_main"])

def generate_slip_pdf(slip):
    """
    Generates a PDF for a given slip and returns the file path.
    Returns None if generation fails.
    """
    import json
    import subprocess
    import tempfile
    import os
    from django.conf import settings
    
    # Prepare data for JSON
    items = slip.items or []
    descrizioni = [item.get("description", "") for item in items]
    qta = [str(item.get("quantity", "")) for item in items]
    um = [item.get("unit", "") for item in items]
    item_notes = [item.get("note", "---") for item in items]

    recipient_data = {
        "usr": slip.recipient.company_name,
        "riga1": slip.recipient.address_line1,
        "riga2": slip.recipient.address_line2 or "",
        "citta": slip.recipient.city,
        "prov": slip.recipient.province_sigla or "",
        "cap": slip.recipient.postal_code,
        "paese": slip.recipient.country,
    }

    same_address = not slip.different_address
    dst2_data = []
    if not same_address:
        addr = slip.different_address
        dst2_data = [
            addr.get("dest_name", ""),
            addr.get("dest_address", ""),
            addr.get("dest_city", ""),
            addr.get("dest_cap", ""),
            addr.get("dest_state", ""),
        ]

    bolla_data = {
        "data": slip.date.strftime("%d/%m/%Y"),
        "descrizioni": descrizioni,
        "qta": qta,
        "um": um,
        "note": item_notes,
        "lavorazione": slip.lavorazione or "",
        "respSpedizione": slip.resp_spedizione or "",
        "dataTrasp": slip.data_trasp.strftime("%d/%m/%Y") if slip.data_trasp else "",
        "aspetto": slip.aspetto or "",
        "dst": recipient_data,
        "sameAddress": same_address,
        "dst2": dst2_data,
        "number": str(slip.slip_number),
        "year": str(slip.slip_year),
    }

    json_string = json.dumps(bolla_data)

    jar_path = os.path.join(
        settings.BASE_DIR,
        "core",
        "static",
        "programs",
        "SlipDrawer",
        "BollaDrawer-1.0-SNAPSHOT.jar",
    )
    static_files_path = os.path.join(settings.BASE_DIR, "core", "static")

    with tempfile.TemporaryDirectory() as temp_dir:
        command = ["java", "-jar", jar_path, json_string, temp_dir, static_files_path]

        try:
            result = subprocess.run(command, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            print(f"Error generating PDF for slip {slip.full_slip_number}: {e.stderr}")
            return None

        # Log stdout/stderr for debugging
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr)

        # Search for the generated PDF
        found_pdf = None

        # Prepare candidate filenames to match (handle variants like '/' vs '-')
        normalized_full = str(slip.full_slip_number).replace("/", "-")
        candidates = {
            f"{slip.full_slip_number}.pdf",
            f"{normalized_full}.pdf",
            f"{slip.slip_number}-{slip.slip_year}.pdf",
            f"{slip.slip_number}_{slip.slip_year}.pdf",
            f"{slip.slip_number}.{slip.slip_year}.pdf",
        }

        for root, dirs, files in os.walk(temp_dir):
            for fname in files:
                if not fname.lower().endswith(".pdf"):
                    continue
                full_path = os.path.join(root, fname)
                # Exact candidate match or contains both number and year
                if fname in candidates or (
                    str(slip.slip_number) in fname and str(slip.slip_year) in fname
                ):
                    found_pdf = full_path
                    break
            if found_pdf:
                break

        if found_pdf and os.path.exists(found_pdf):
            # Read the PDF content and return it as bytes
            with open(found_pdf, "rb") as f:
                pdf_content = f.read()
            return pdf_content
        else:
            # Collect generated PDFs (if any) for diagnostics
            generated_pdfs = []
            for root, dirs, files in os.walk(temp_dir):
                for fname in files:
                    if fname.lower().endswith(".pdf"):
                        generated_pdfs.append(os.path.join(root, fname))

            print(f"PDF not found for slip {slip.full_slip_number}")
            if result.stdout:
                print(f"Stdout: {result.stdout}")
            if result.stderr:
                print(f"Stderr: {result.stderr}")
            if generated_pdfs:
                print(f"Generated PDFs found: {generated_pdfs}")

            return None

@login_required
def profile_view(request):
    """
    Renders the user's private profile page.
    For now, it will redirect to the dashboard.
    """
    return redirect("dashboard")


@login_required
def dashboard_view(request):
    """
    Displays a dashboard of delivery/shipping slips for the logged-in user.
    """
    slips = Slip.objects.all().order_by(
        "-date", "-slip_number"
    )

    context = {
        "page_title": "Dashboard Bolle",
        "slips": slips,
    }
    return render(request, "user_profile/dashboard.html", context)


@login_required
def price_list_list_view(request):
    context = {
        "page_title": "Listini Prezzi",
        "price_lists": PriceList.objects.all(),
    }
    return render(request, "user_profile/price_list_list.html", context)


@login_required
def price_list_detail_view(request, pk):
    price_list = get_object_or_404(PriceList, pk=pk)

    context = {
        "page_title": f"Listino {price_list.name}",
        "price_list": price_list,
        "price_list_items": price_list.items.prefetch_related("photos", "materials", "works", "external_costs").all(),
    }
    return render(request, "user_profile/price_list_detail.html", context)


@login_required
def price_list_item_edit_view(request, pk, item_pk):
    price_list, price_list_item = get_price_list_item_or_404(pk, item_pk)
    active_tab = get_item_editor_tab(request)

    if is_dynamic_request(request):
        return render_price_list_item_editor_partial(
            request,
            price_list,
            price_list_item,
            active_tab=active_tab,
        )

    context = build_price_list_item_editor_context(
        price_list,
        price_list_item,
        active_tab=active_tab,
    )
    context["page_title"] = f"{price_list_item.name} - {price_list.name}"
    return render(request, "user_profile/price_list_item_edit.html", context)


@login_required
def create_price_list_view(request):
    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()

        if not name:
            messages.error(request, "Inserisci un nome per il listino prezzi.")
        else:
            PriceList.objects.create(name=name)
            messages.success(request, f'Listino prezzi "{name}" creato con successo!')

    return redirect("price_list_list")


@login_required
def delete_price_list_view(request, pk):
    price_list = get_object_or_404(PriceList, pk=pk)

    if request.method == "POST":
        price_list_name = price_list.name
        price_list.delete()
        messages.success(request, f'Listino prezzi "{price_list_name}" eliminato con successo.')

    return redirect("price_list_list")


@login_required
def create_price_list_item_view(request, pk):
    price_list = get_object_or_404(PriceList, pk=pk)

    if request.method == "POST":
        sku = (request.POST.get("sku") or "").strip()
        name = (request.POST.get("name") or "").strip()
        description = (request.POST.get("description") or "").strip()

        if not sku or not name:
            return redirect_to_price_list_editor(
                request,
                price_list,
                editor_message="Inserisci sia il codice/SKU sia il nome del capo.",
                editor_message_tag="danger",
                status=400,
            )

        if price_list.items.filter(sku=sku).exists():
            return redirect_to_price_list_editor(
                request,
                price_list,
                editor_message=f'Esiste gia un capo con codice "{sku}" in questo listino.',
                editor_message_tag="danger",
                status=400,
            )

        try:
            price_list_item = PriceListItem.objects.create(
                price_list=price_list,
                sku=sku,
                name=name,
                description=description or None,
                sort_order=get_next_sort_order(price_list.items),
            )
        except IntegrityError:
            return redirect_to_price_list_editor(
                request,
                price_list,
                editor_message=f'Esiste gia un capo con codice "{sku}" in questo listino.',
                editor_message_tag="danger",
                status=400,
            )

        return redirect_to_price_list_editor(
            request,
            price_list,
            active_item=price_list_item,
            editor_message=f'Capo "{name}" aggiunto al listino "{price_list.name}".',
        )

    return redirect(get_price_list_detail_url(price_list))


@login_required
def update_price_list_item_view(request, pk, item_pk):
    price_list, price_list_item = get_price_list_item_or_404(pk, item_pk)

    if request.method == "POST":
        sku = (request.POST.get("sku") or "").strip()
        name = (request.POST.get("name") or "").strip()
        description = (request.POST.get("description") or "").strip()

        if not sku or not name:
            return redirect_to_price_list_editor(
                request,
                price_list,
                active_item=price_list_item,
                editor_message="Inserisci un codice/SKU e un nome validi per il capo.",
                editor_message_tag="danger",
                status=400,
                active_tab="general",
            )

        if price_list.items.exclude(pk=price_list_item.pk).filter(sku=sku).exists():
            return redirect_to_price_list_editor(
                request,
                price_list,
                active_item=price_list_item,
                editor_message=f'Esiste gia un capo con codice "{sku}" in questo listino.',
                editor_message_tag="danger",
                status=400,
                active_tab="general",
            )

        try:
            price_list_item.sku = sku
            price_list_item.name = name
            price_list_item.description = description or None
            price_list_item.is_active = "is_active" in request.POST
            price_list_item.save()
        except IntegrityError:
            return redirect_to_price_list_editor(
                request,
                price_list,
                active_item=price_list_item,
                editor_message=f'Esiste gia un capo con codice "{sku}" in questo listino.',
                editor_message_tag="danger",
                status=400,
                active_tab="general",
            )

        return redirect_to_price_list_editor(
            request,
            price_list,
            active_item=price_list_item,
            editor_message=f'Capo "{price_list_item.name}" aggiornato con successo.',
            active_tab="general",
        )

    return redirect(get_price_list_detail_url(price_list, active_item=price_list_item))


@login_required
def delete_price_list_item_view(request, pk, item_pk):
    price_list, price_list_item = get_price_list_item_or_404(pk, item_pk)

    if request.method == "POST":
        item_name = price_list_item.name
        price_list_item.delete()
        return redirect_to_price_list_editor(
            request,
            price_list,
            editor_message=f'Capo "{item_name}" eliminato dal listino "{price_list.name}".',
        )

    return redirect(get_price_list_detail_url(price_list, active_item=price_list_item))


@login_required
def create_price_list_item_photo_view(request, pk, item_pk):
    price_list, price_list_item = get_price_list_item_or_404(pk, item_pk)

    if request.method == "POST":
        uploaded_photos = request.FILES.getlist("original_images")
        should_be_main = "is_main" in request.POST or not price_list_item.photos.exists()

        if not uploaded_photos:
            return redirect_to_price_list_editor(
                request,
                price_list,
                active_item=price_list_item,
                editor_message="Seleziona un'immagine da caricare per il capo.",
                editor_message_tag="danger",
                status=400,
                active_tab="photos",
            )

        next_order = get_next_sort_order(price_list_item.photos, field_name="order")
        for index, uploaded_photo in enumerate(uploaded_photos):
            photo = PriceListItemPhoto.objects.create(
                item=price_list_item,
                original_image=uploaded_photo,
                is_main=should_be_main and index == 0,
                order=next_order + index,
            )
            if should_be_main and index == 0:
                photo.save(update_fields=["is_main"])

        return redirect_to_price_list_editor(
            request,
            price_list,
            active_item=price_list_item,
            editor_message=f'{len(uploaded_photos)} foto aggiunte al capo "{price_list_item.name}".',
            active_tab="photos",
        )

    return redirect(get_price_list_detail_url(price_list, active_item=price_list_item))


@login_required
def set_price_list_item_photo_main_view(request, pk, item_pk, photo_pk):
    price_list, price_list_item = get_price_list_item_or_404(pk, item_pk)
    photo = get_object_or_404(PriceListItemPhoto, pk=photo_pk, item=price_list_item)

    if request.method == "POST":
        photo.is_main = True
        photo.save(update_fields=["is_main"])
        return redirect_to_price_list_editor(
            request,
            price_list,
            active_item=price_list_item,
            editor_message=f'Foto principale aggiornata per il capo "{price_list_item.name}".',
            active_tab="photos",
        )

    return redirect(get_price_list_detail_url(price_list, active_item=price_list_item))


@login_required
def delete_price_list_item_photo_view(request, pk, item_pk, photo_pk):
    price_list, price_list_item = get_price_list_item_or_404(pk, item_pk)
    photo = get_object_or_404(PriceListItemPhoto, pk=photo_pk, item=price_list_item)

    if request.method == "POST":
        photo.delete()
        ensure_item_has_main_photo(price_list_item)
        return redirect_to_price_list_editor(
            request,
            price_list,
            active_item=price_list_item,
            editor_message=f'Foto rimossa dal capo "{price_list_item.name}".',
            active_tab="photos",
        )

    return redirect(get_price_list_detail_url(price_list, active_item=price_list_item))


@login_required
def save_price_list_item_material_view(request, pk, item_pk, material_pk=None):
    price_list, price_list_item = get_price_list_item_or_404(pk, item_pk)
    material = None
    if material_pk is not None:
        material = get_object_or_404(PriceListItemMaterial, pk=material_pk, item=price_list_item)

    if request.method == "POST":
        description = (request.POST.get("description") or "").strip()
        if not description:
            return redirect_to_price_list_editor(
                request,
                price_list,
                active_item=price_list_item,
                editor_message="Inserisci una descrizione per il materiale primario.",
                editor_message_tag="danger",
                status=400,
                active_tab="materials",
            )

        try:
            quantity = parse_decimal_input(request.POST.get("quantity"), default=Decimal("0"))
            unit_cost = parse_decimal_input(request.POST.get("unit_cost"), default=Decimal("0"))
        except ValueError:
            return redirect_to_price_list_editor(
                request,
                price_list,
                active_item=price_list_item,
                editor_message="Quantita o costo unitario non sono validi per il materiale.",
                editor_message_tag="danger",
                status=400,
                active_tab="materials",
            )

        material_unit = normalize_choice(
            request.POST.get("unit"),
            PriceListItem.MaterialUnit.choices,
            PriceListItem.MaterialUnit.PIECE,
        )

        if material is None:
            material = PriceListItemMaterial(item=price_list_item, sort_order=get_next_sort_order(price_list_item.materials))
            success_message = f'Materiale "{description}" aggiunto al capo "{price_list_item.name}".'
        else:
            success_message = f'Materiale "{description}" aggiornato con successo.'

        material.material_type = normalize_choice(
            request.POST.get("material_type"),
            PriceListItem.MaterialType.choices,
            PriceListItem.MaterialType.YARN,
        )
        material.description = description
        material.supplier = ""
        material.unit = material_unit
        material.quantity = quantity
        material.unit_cost = unit_cost
        material.waste_pct = Decimal("0")
        material.notes = ""
        material.save()

        return redirect_to_price_list_editor(
            request,
            price_list,
            active_item=price_list_item,
            editor_message=success_message,
            active_tab="materials",
        )

    return redirect(get_price_list_detail_url(price_list, active_item=price_list_item))


@login_required
def delete_price_list_item_material_view(request, pk, item_pk, material_pk):
    price_list, price_list_item = get_price_list_item_or_404(pk, item_pk)
    material = get_object_or_404(PriceListItemMaterial, pk=material_pk, item=price_list_item)

    if request.method == "POST":
        material_name = material.description
        material.delete()
        return redirect_to_price_list_editor(
            request,
            price_list,
            active_item=price_list_item,
            editor_message=f'Materiale "{material_name}" eliminato con successo.',
            active_tab="materials",
        )

    return redirect(get_price_list_detail_url(price_list, active_item=price_list_item))


@login_required
def save_price_list_item_work_view(request, pk, item_pk, work_pk=None):
    price_list, price_list_item = get_price_list_item_or_404(pk, item_pk)
    work = None
    if work_pk is not None:
        work = get_object_or_404(PriceListItemWork, pk=work_pk, item=price_list_item)

    if request.method == "POST":
        preset_code = (request.POST.get("preset_code") or "").strip()

        if work is None:
            if preset_code == "custom":
                custom_name = (request.POST.get("custom_operation_name") or "").strip()
                if not custom_name:
                    return redirect_to_price_list_editor(
                        request,
                        price_list,
                        active_item=price_list_item,
                        editor_message="Inserisci il nome della lavorazione personalizzata.",
                        editor_message_tag="danger",
                        status=400,
                        active_tab="works",
                    )
                try:
                    quantity = parse_decimal_input(request.POST.get("quantity"), default=Decimal("0"))
                    unit_cost = parse_decimal_input(request.POST.get("unit_cost"), default=Decimal("0"))
                except ValueError:
                    return redirect_to_price_list_editor(
                        request,
                        price_list,
                        active_item=price_list_item,
                        editor_message="Quantita o costo unitario non sono validi.",
                        editor_message_tag="danger",
                        status=400,
                        active_tab="works",
                    )
                work = PriceListItemWork(item=price_list_item, sort_order=get_next_sort_order(price_list_item.works))
                work.operation_name = custom_name
                work.unit = (request.POST.get("unit") or "pz").strip() or "pz"
                success_message = f'Lavorazione "{custom_name}" aggiunta al capo "{price_list_item.name}".'
            else:
                preset = WORK_PRESETS.get(preset_code)
                if preset is None:
                    return redirect_to_price_list_editor(
                        request,
                        price_list,
                        active_item=price_list_item,
                        editor_message="Seleziona una lavorazione predefinita valida.",
                        editor_message_tag="danger",
                        status=400,
                        active_tab="works",
                    )
                quantity = preset["quantity"]
                unit_cost = preset["unit_cost"]
                work = PriceListItemWork(item=price_list_item, sort_order=get_next_sort_order(price_list_item.works))
                work.operation_name = preset["label"]
                work.unit = preset["unit"]
                success_message = f'Lavorazione "{preset["label"]}" aggiunta al capo "{price_list_item.name}".'
        else:
            try:
                quantity = parse_decimal_input(request.POST.get("quantity"), default=Decimal("0"))
                unit_cost = parse_decimal_input(request.POST.get("unit_cost"), default=Decimal("0"))
            except ValueError:
                return redirect_to_price_list_editor(
                    request,
                    price_list,
                    active_item=price_list_item,
                    editor_message="Quantita o costo unitario non sono validi per la lavorazione.",
                    editor_message_tag="danger",
                    status=400,
                    active_tab="works",
                )
            operation_name_input = (request.POST.get("operation_name") or "").strip()
            if operation_name_input:
                work.operation_name = operation_name_input
            unit_input = (request.POST.get("unit") or "").strip()
            if unit_input:
                work.unit = unit_input
            success_message = f'Lavorazione "{work.operation_name}" aggiornata con successo.'

        work.quantity = quantity
        work.unit_cost = unit_cost
        work.notes = ""
        work.save()

        return redirect_to_price_list_editor(
            request,
            price_list,
            active_item=price_list_item,
            editor_message=success_message,
            active_tab="works",
        )

    return redirect(get_price_list_detail_url(price_list, active_item=price_list_item))


@login_required
def delete_price_list_item_work_view(request, pk, item_pk, work_pk):
    price_list, price_list_item = get_price_list_item_or_404(pk, item_pk)
    work = get_object_or_404(PriceListItemWork, pk=work_pk, item=price_list_item)

    if request.method == "POST":
        work_name = work.operation_name
        work.delete()
        return redirect_to_price_list_editor(
            request,
            price_list,
            active_item=price_list_item,
            editor_message=f'Lavorazione "{work_name}" eliminata con successo.',
            active_tab="works",
        )

    return redirect(get_price_list_detail_url(price_list, active_item=price_list_item))


@login_required
def save_price_list_item_external_cost_view(request, pk, item_pk, external_cost_pk=None):
    price_list, price_list_item = get_price_list_item_or_404(pk, item_pk)
    external_cost = None
    if external_cost_pk is not None:
        external_cost = get_object_or_404(PriceListItemExternalCost, pk=external_cost_pk, item=price_list_item)

    if request.method == "POST":
        try:
            amount = parse_decimal_input(request.POST.get("amount"), default=Decimal("0"))
        except ValueError:
            return redirect_to_price_list_editor(
                request,
                price_list,
                active_item=price_list_item,
                editor_message="Il valore del costo esterno non e valido.",
                editor_message_tag="danger",
                status=400,
                active_tab="external",
            )

        if external_cost is None:
            preset_code = (request.POST.get("preset_code") or "").strip()
            if preset_code == "custom":
                description = (request.POST.get("description") or "").strip()
                if not description:
                    return redirect_to_price_list_editor(
                        request,
                        price_list,
                        active_item=price_list_item,
                        editor_message="Inserisci la descrizione del costo esterno.",
                        editor_message_tag="danger",
                        status=400,
                        active_tab="external",
                    )
                cost_type = normalize_choice(
                    request.POST.get("cost_type"),
                    PriceListItem.ExternalCostType.choices,
                    PriceListItem.ExternalCostType.FIXED,
                )
                applies_to = normalize_choice(
                    request.POST.get("applies_to"),
                    PriceListItem.ExternalCostBase.choices,
                    PriceListItem.ExternalCostBase.SUBTOTAL,
                )
                external_cost = PriceListItemExternalCost(
                    item=price_list_item,
                    sort_order=get_next_sort_order(price_list_item.external_costs),
                )
                external_cost.description = description
                external_cost.cost_type = cost_type
                external_cost.applies_to = applies_to
                external_cost.amount = amount
                external_cost.notes = ""
                success_message = f'Costo esterno "{description}" aggiunto al capo "{price_list_item.name}".'
            else:
                preset = EXTERNAL_COST_PRESETS.get(preset_code)
                if preset is None:
                    return redirect_to_price_list_editor(
                        request,
                        price_list,
                        active_item=price_list_item,
                        editor_message="Seleziona un costo esterno predefinito valido.",
                        editor_message_tag="danger",
                        status=400,
                        active_tab="external",
                    )

                if price_list_item.external_costs.filter(description=preset["label"]).exists():
                    return redirect_to_price_list_editor(
                        request,
                        price_list,
                        active_item=price_list_item,
                        editor_message=f'Il costo esterno "{preset["label"]}" e gia presente per questo capo.',
                        editor_message_tag="warning",
                        status=400,
                        active_tab="external",
                    )

                external_cost = PriceListItemExternalCost(
                    item=price_list_item,
                    sort_order=get_next_sort_order(price_list_item.external_costs),
                )
                external_cost.description = preset["label"]
                external_cost.cost_type = preset["cost_type"]
                external_cost.applies_to = preset["applies_to"]
                external_cost.amount = preset["amount"]
                external_cost.notes = ""
                success_message = f'Costo esterno "{preset["label"]}" aggiunto al capo "{price_list_item.name}".'
        else:
            external_cost.amount = amount
            success_message = f'Costo esterno "{external_cost.description}" aggiornato con successo.'

        external_cost.save()

        return redirect_to_price_list_editor(
            request,
            price_list,
            active_item=price_list_item,
            editor_message=success_message,
            active_tab="external",
        )

    return redirect(get_price_list_detail_url(price_list, active_item=price_list_item))


@login_required
def delete_price_list_item_external_cost_view(request, pk, item_pk, external_cost_pk):
    price_list, price_list_item = get_price_list_item_or_404(pk, item_pk)
    external_cost = get_object_or_404(PriceListItemExternalCost, pk=external_cost_pk, item=price_list_item)

    if request.method == "POST":
        cost_name = external_cost.description
        external_cost.delete()
        return redirect_to_price_list_editor(
            request,
            price_list,
            active_item=price_list_item,
            editor_message=f'Costo esterno "{cost_name}" eliminato con successo.',
            active_tab="external",
        )

    return redirect(get_price_list_detail_url(price_list, active_item=price_list_item))


@login_required
def create_slip_view(request):
    """
    Handles the creation of a new delivery slip.
    """
    recipients = Recipient.objects.all()
    current_year = date.today().year

    # Logic to get the next available slip number
    # Find the last slip number for the current year
    last_slip = Slip.objects.filter(slip_year=current_year).aggregate(
        models.Max("slip_number")
    )
    # Assuming slip_number is an integer, get the next one.
    # If no slips exist for the current year, start from 1.
    if last_slip["slip_number__max"]:
        next_slip_number = int(last_slip["slip_number__max"]) + 1
    else:
        next_slip_number = 1

    if request.method == "POST":
        print(request.POST)
        slip_number = int(request.POST.get("slip_number"))
        slip_year = int(request.POST.get("slip_year"))
        slip_date = request.POST.get("date")
        recipient_id = request.POST.get("recipient")
        lavorazione = request.POST.get("lavorazione")
        resp_spedizione = request.POST.get("resp_spedizione")
        data_trasp = request.POST.get("data_trasp")
        aspetto = request.POST.get("aspetto")
        notes = request.POST.get("notes")

        print(f"Attempting to create slip: {slip_number}-{slip_year}")

        different_address = None
        if "different_delivery_address" in request.POST:
            different_address = {
                "dest_name": request.POST.get("dest_name"),
                "dest_address": request.POST.get("dest_address"),
                "dest_city": request.POST.get("dest_city"),
                "dest_cap": request.POST.get("dest_cap"),
                "dest_prov": request.POST.get("dest_prov"),
                "dest_state": request.POST.get("dest_state"),
            }

        items_json = request.POST.get("items", "[]")

        try:
            items = json.loads(items_json)
        except json.JSONDecodeError as e:
            messages.error(request, f"Errore nel formato JSON degli articoli: {e}")
            return redirect("create_slip")

        try:
            recipient = get_object_or_404(
                Recipient, id=recipient_id
            )
            Slip.objects.create(
                slip_number=slip_number,
                slip_year=int(slip_year),
                date=slip_date,
                recipient=recipient,
                created_by=request.user,
                lavorazione=lavorazione,
                resp_spedizione=resp_spedizione,
                data_trasp=data_trasp if data_trasp else None,
                aspetto=aspetto,
                items=items,
                notes=notes,
                different_address=different_address,
            )
            messages.success(request, "Bolla creata con successo!")
            return redirect("dashboard")
        except IntegrityError:
            messages.error(
                request,
                f"Esiste già una bolla con numero {slip_number}-{slip_year}",
            )
        except Exception as e:
            messages.error(request, f"Errore nella creazione della bolla: {e}")

    print(next_slip_number)
    context = {
        "page_title": "Crea Nuova Bolla",
        "recipients": recipients,
        "current_year": current_year,
        "next_slip_number": next_slip_number,  # Pass the new number to the template
        "form_data": {
            "date": date.today().strftime("%Y-%m-%d"),
            "data_trasp": date.today().strftime("%Y-%m-%d"),
            "slip_year": current_year,
            "items_": {},
        },
    }

    return render(request, "user_profile/slip_form.html", context)


@login_required
def edit_slip_view(request, pk):
    slip = get_object_or_404(Slip, pk=pk)
    recipients = Recipient.objects.all()

    if request.method == "POST":
        slip.slip_number = request.POST.get("slip_number")
        slip.slip_year = int(request.POST.get("slip_year"))
        slip.date = request.POST.get("date")
        recipient_id = request.POST.get("recipient")
        slip.lavorazione = request.POST.get("lavorazione")
        slip.resp_spedizione = request.POST.get("resp_spedizione")
        data_trasp = request.POST.get("data_trasp")
        slip.data_trasp = data_trasp if data_trasp else None
        slip.aspetto = request.POST.get("aspetto")
        slip.notes = request.POST.get("notes")

        if "different_delivery_address" in request.POST:
            slip.different_address = {
                "dest_name": request.POST.get("dest_name"),
                "dest_address": request.POST.get("dest_address"),
                "dest_city": request.POST.get("dest_city"),
                "dest_cap": request.POST.get("dest_cap"),
                "dest_prov": request.POST.get("dest_prov"),
                "dest_state": request.POST.get("dest_state"),
            }
        else:
            slip.different_address = None

        items_json = request.POST.get("items", "[]")

        try:
            slip.items = json.loads(items_json)
        except json.JSONDecodeError as e:
            messages.error(request, f"Errore nel formato JSON degli articoli: {e}")
            return redirect("edit_slip", pk=pk)

        slip.recipient = get_object_or_404(
            Recipient, id=recipient_id
        )

        try:
            slip.save()
            messages.success(request, "Bolla aggiornata con successo!")
            return redirect("dashboard")
        except IntegrityError:
            messages.error(
                request,
                f"Esiste già una bolla con numero {slip.slip_number}-{slip.slip_year}",
            )
        except Exception as e:
            messages.error(request, f"Errore nell'aggiornamento della bolla: {e}")

    form_data = {
        "slip_number": slip.slip_number,
        "slip_year": slip.slip_year,
        "date": slip.date.strftime("%Y-%m-%d") if slip.date else "",
        "recipient": slip.recipient.id,
        "lavorazione": slip.lavorazione,
        "resp_spedizione": slip.resp_spedizione,
        "data_trasp": slip.data_trasp.strftime("%Y-%m-%d") if slip.data_trasp else "",
        "aspetto": slip.aspetto,
        "notes": slip.notes,
        "items_": slip.items,
    }
    if slip.different_address:
        form_data.update(slip.different_address)

    context = {
        "page_title": "Modifica Bolla",
        "slip": slip,
        "next_slip_number": slip.slip_number,
        "recipients": recipients,
        "form_data": form_data,
        "is_edit": True,
    }
    return render(request, "user_profile/slip_form.html", context)


@login_required
def delete_slip_view(request, pk):
    slip = get_object_or_404(Slip, pk=pk)
    if request.method == "POST":
        slip.delete()
        messages.success(request, "Bolla eliminata con successo.")
    return redirect("dashboard")


@login_required
def download_slip_view(request, pk):
    slip = get_object_or_404(Slip, pk=pk)

    # Prepare data for JSON
    items = slip.items or []
    descrizioni = [item.get("description", "") for item in items]
    qta = [str(item.get("quantity", "")) for item in items]
    um = [item.get("unit", "") for item in items]
    item_notes = [item.get("note", "---") for item in items]

    recipient_data = {
        "usr": slip.recipient.company_name,
        "riga1": slip.recipient.address_line1,
        "riga2": slip.recipient.address_line2 or "",
        "citta": slip.recipient.city,
        "prov": slip.recipient.province_sigla or "",
        "cap": slip.recipient.postal_code,
        "paese": slip.recipient.country,
    }

    same_address = not slip.different_address
    dst2_data = []
    if not same_address:
        addr = slip.different_address
        dst2_data = [
            addr.get("dest_name", ""),
            addr.get("dest_address", ""),
            addr.get("dest_city", ""),
            addr.get("dest_cap", ""),
            addr.get("dest_state", ""),
        ]

    bolla_data = {
        "data": slip.date.strftime("%d/%m/%Y"),
        "descrizioni": descrizioni,
        "qta": qta,
        "um": um,
        "note": item_notes,
        "lavorazione": slip.lavorazione or "",
        "respSpedizione": slip.resp_spedizione or "",
        "dataTrasp": slip.data_trasp.strftime("%d/%m/%Y") if slip.data_trasp else "",
        "aspetto": slip.aspetto or "",
        "dst": recipient_data,
        "sameAddress": same_address,
        "dst2": dst2_data,
        "number": str(slip.slip_number),
        "year": str(slip.slip_year),
    }

    json_string = json.dumps(bolla_data)

    jar_path = os.path.join(
        settings.BASE_DIR,
        "core",
        "static",
        "programs",
        "SlipDrawer",
        "BollaDrawer-1.0-SNAPSHOT.jar",
    )
    static_files_path = os.path.join(settings.BASE_DIR, "core", "static")

    with tempfile.TemporaryDirectory() as temp_dir:

        command = ["java", "-jar", jar_path, json_string, temp_dir, static_files_path]

        try:
            result = subprocess.run(command, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            error_message = f"Errore nella generazione del PDF: {e.stderr}"
            if e.stdout:
                error_message += f"\nOutput: {e.stdout}"

            messages.error(request, error_message)
            return redirect("dashboard")
        # Log stdout/stderr for debugging
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr)

        # The jar may write the PDF in different locations or with slightly different
        # filename formats (for example it may create a "Bolle" subdirectory or
        # replace characters). Search the temp_dir recursively for a matching PDF
        # instead of assuming a single fixed path.
        found_pdf = None

        # Prepare candidate filenames to match (handle variants like '/' vs '-')
        normalized_full = str(slip.full_slip_number).replace("/", "-")
        candidates = {
            f"{slip.full_slip_number}.pdf",
            f"{normalized_full}.pdf",
            f"{slip.slip_number}-{slip.slip_year}.pdf",
            f"{slip.slip_number}_{slip.slip_year}.pdf",
            f"{slip.slip_number}.{slip.slip_year}.pdf",
        }

        for root, dirs, files in os.walk(temp_dir):
            for fname in files:
                if not fname.lower().endswith(".pdf"):
                    continue
                full_path = os.path.join(root, fname)
                # Exact candidate match or contains both number and year
                if fname in candidates or (
                    str(slip.slip_number) in fname and str(slip.slip_year) in fname
                ):
                    found_pdf = full_path
                    break
            if found_pdf:
                break

        if found_pdf and os.path.exists(found_pdf):
            with open(found_pdf, "rb") as f:
                pdf_content = f.read()

            disposition = "inline" if request.GET.get("view") else "attachment"
            # Use a safe filename for Content-Disposition
            safe_name = f"{normalized_full}.pdf"
            response = HttpResponse(pdf_content, content_type="application/pdf")
            response["Content-Disposition"] = (
                f'{disposition}; filename="{safe_name}"'
            )
            return response
        else:
            # Collect generated PDFs (if any) for diagnostics
            generated_pdfs = []
            for root, dirs, files in os.walk(temp_dir):
                for fname in files:
                    if fname.lower().endswith(".pdf"):
                        generated_pdfs.append(os.path.join(root, fname))

            error_message = "Il file PDF non è stato generato o non è stato trovato."
            "Controllare i log del server per maggiori dettagli."
            if result.stdout:
                error_message += f" Stdout: {result.stdout}"
            if result.stderr:
                error_message += f" Stderr: {result.stderr}"
            if generated_pdfs:
                error_message += f" PDF trovati: {generated_pdfs}"

            messages.error(request, error_message)
            return redirect("dashboard")


@login_required
def recipient_list_view(request):
    query = request.GET.get("q")
    if query:
        recipients = Recipient.objects.filter(
            company_name__icontains=query
        ).order_by("company_name")
    else:
        recipients = Recipient.objects.all().order_by(
            "company_name"
        )

    context = {
        "page_title": "Gestione Destinatari",
        "recipients": recipients,
        "query": query,
    }
    return render(request, "user_profile/recipient_list.html", context)


@login_required
def add_recipient_view(request):
    if request.method == "POST":
        company_name = request.POST.get("company_name")
        address_line1 = request.POST.get("address_line1")
        address_line2 = request.POST.get("address_line2")
        city = request.POST.get("city")
        postal_code = request.POST.get("postal_code")
        province_sigla = request.POST.get("province_sigla")
        country = request.POST.get("country")
        phone = request.POST.get("phone")
        email = request.POST.get("email")
        vat_number = request.POST.get("vat_number")

        try:
            Recipient.objects.create(
                company_name=company_name,
                address_line1=address_line1,
                address_line2=address_line2,
                city=city,
                postal_code=postal_code,
                province_sigla=province_sigla,
                country=country,
                phone=phone,
                email=email,
                vat_number=vat_number,
            )
            messages.success(request, "Destinatario aggiunto con successo!")
            return redirect("recipient_list")
        except Exception as e:
            messages.error(request, f"Errore nell'aggiunta del destinatario: {e}")

    context = {"page_title": "Aggiungi Destinatario", "is_edit": False}
    return render(request, "user_profile/recipient_form.html", context)


@login_required
def edit_recipient_view(request, pk):
    recipient = get_object_or_404(Recipient, pk=pk)

    if request.method == "POST":
        recipient.company_name = request.POST.get("company_name")
        recipient.address_line1 = request.POST.get("address_line1")
        recipient.address_line2 = request.POST.get("address_line2")
        recipient.city = request.POST.get("city")
        recipient.postal_code = request.POST.get("postal_code")
        recipient.province_sigla = request.POST.get("province_sigla")
        recipient.country = request.POST.get("country")
        recipient.phone = request.POST.get("phone")
        recipient.email = request.POST.get("email")
        recipient.vat_number = request.POST.get("vat_number")

        try:
            recipient.save()
            messages.success(request, "Destinatario aggiornato con successo!")
            return redirect("recipient_list")
        except Exception as e:
            messages.error(request, f"Errore nell'aggiornamento del destinatario: {e}")

    context = {
        "page_title": "Modifica Destinatario",
        "recipient": recipient,
        "is_edit": True,
    }
    return render(request, "user_profile/recipient_form.html", context)


@login_required
def delete_recipient_view(request, pk):
    recipient = get_object_or_404(Recipient, pk=pk)
    if request.method == "POST":
        recipient.delete()
        messages.success(request, "Destinatario eliminato con successo.")
    return redirect("recipient_list")


@login_required
def custom_print_view(request):
    if request.method == "POST":
        selected_slips_str = request.POST.get("selected_slips")
        print(selected_slips_str)
        print(request.POST)
        if not selected_slips_str:
            messages.error(request, "Nessuna bolla selezionata.")
            return redirect("custom_print")

        selected_ids = [int(pk) for pk in selected_slips_str.split(",")]
        slips_to_print = [get_object_or_404(Slip, pk=pk) for pk in selected_ids]
        print(f"Slips to print: {slips_to_print}")

        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [executor.submit(generate_slip_pdf, slip) for slip in slips_to_print]

        merger = PdfMerger(strict=False)
        successful_merges = 0

        for i, future in enumerate(futures):
            slip = slips_to_print[i]
            pdf_content = future.result()
            if pdf_content:
                try:
                    pdf_buffer = BytesIO(pdf_content)
                    pdf_buffer.seek(0)
                    merger.append(pdf_buffer)
                    successful_merges += 1
                    print(f"Successfully added PDF for slip {slip.full_slip_number}")
                except Exception as e:
                    print(f"Error adding PDF for slip {slip.full_slip_number}: {e}")
                    messages.warning(request, f"Impossibile aggiungere il PDF per la bolla {slip.full_slip_number}.")
            else:
                print(f"Failed to generate PDF for slip {slip.full_slip_number}")
                messages.warning(request, f"Impossibile generare il PDF per la bolla {slip.full_slip_number}.")

        if successful_merges > 0:
            try:
                output_pdf = BytesIO()
                merger.write(output_pdf)
                merger.close()
                
                # Reset buffer position to beginning
                output_pdf.seek(0)
                pdf_data = output_pdf.getvalue()
                
                # Check if we actually have PDF data
                if len(pdf_data) > 0:
                    response = HttpResponse(pdf_data, content_type="application/pdf")
                    response["Content-Disposition"] = 'attachment; filename="bolle_selezionate.pdf"'
                    return response
                else:
                    messages.error(request, "Il PDF generato è vuoto.")
                    return redirect("custom_print")
                    
            except Exception as e:
                print(f"Error creating merged PDF: {e}")
                messages.error(request, f"Errore durante la creazione del PDF unito: {e}")
                return redirect("custom_print")
        else:
            messages.error(request, "Nessun PDF è stato generato.")
            return redirect("custom_print")

    slips = Slip.objects.all().order_by("-date", "-slip_number")
    
    context = {
        "page_title": "Stampa Personalizzata",
        "slips": slips,
        "form_data": request.GET,
    }
    return render(request, "user_profile/custom_print.html", context)

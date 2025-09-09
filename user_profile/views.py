# file: user_profile/views.py
from django.db import models
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from core.models import Slip, Recipient
import json
from django.http import HttpResponse
from datetime import date
from django.db import IntegrityError
from django.db.models import Max, Q
from django.conf import settings
import subprocess
import tempfile
import os
from io import BytesIO
from PyPDF2 import PdfMerger
import concurrent.futures

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
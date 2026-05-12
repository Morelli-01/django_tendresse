from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import PriceList, PriceListItem


class PriceListItemEditorTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="tester",
            password="secret123",
        )
        self.client.force_login(self.user)
        self.price_list = PriceList.objects.create(name="Maglieria AI")
        self.item = PriceListItem.objects.create(
            price_list=self.price_list,
            sku="ART-001",
            name="Cardigan",
        )

    def test_item_edit_page_contains_pdf_preview_tab(self):
        response = self.client.get(
            reverse(
                "price_list_item_edit",
                kwargs={"pk": self.price_list.pk, "item_pk": self.item.pk},
            ),
            {"tab": "pdf"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-tab-key="pdf"')
        self.assertContains(response, 'id="pdf-pane"')
        self.assertContains(response, 'js-item-editor-pdf-preview')
        self.assertContains(
            response,
            reverse(
                "price_list_item_pdf",
                kwargs={"pk": self.price_list.pk, "item_pk": self.item.pk},
            ),
        )

    def test_item_pdf_view_returns_inline_pdf(self):
        response = self.client.get(
            reverse(
                "price_list_item_pdf",
                kwargs={"pk": self.price_list.pk, "item_pk": self.item.pk},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response["Content-Disposition"].startswith("inline;"))
        self.assertEqual(response["X-Frame-Options"], "SAMEORIGIN")
        self.assertEqual(response.content[:4], b"%PDF")

"""
Abstract base class for all portal order imports.

Each portal (Amazon, Flipkart, Shopify, etc.) implements:
  - authenticate()        → get access token / credentials
  - fetch_orders(params)  → raw list of order dicts from the API
  - map_order(data)       → dict compatible with Order model
  - map_order_items(data) → list of dicts compatible with OrderItem model
  - import_orders(params) → fetch + map + save to DB, returns ImportResult
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import date, datetime

from django.db import transaction
from django.core.exceptions import ValidationError


@dataclass
class ImportResult:
    """Standard result for all portal import operations."""
    portal: str = ""
    found_count: int = 0
    created_count: int = 0
    updated_count: int = 0
    skipped_count: int = 0
    item_count: int = 0
    item_updated_count: int = 0
    failed_count: int = 0
    unmapped_skus: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    skipped_orders: list[str] = field(default_factory=list)
    created_orders: list[str] = field(default_factory=list)
    updated_orders: list[str] = field(default_factory=list)


class PortalImport(ABC):
    """Abstract base for importing orders from external portals."""

    PORTAL_NAME = "unknown"

    @abstractmethod
    def authenticate(self) -> str:
        """
        Authenticate with the portal API and return an access token.
        Raises an exception on failure.
        """
        ...

    @abstractmethod
    def fetch_orders(self, from_date: date, to_date: date, access_token: str) -> list[dict]:
        """
        Fetch orders from the portal API within the given date range.
        Returns a list of raw order dicts from the API response.
        Subclasses must override this.
        """
        ...

    @abstractmethod
    def map_order(self, raw_order: dict) -> dict:
        """
        Map a raw API order dict to fields compatible with the Order model.
        Returns a dict with keys matching Order field names.
        """
        ...

    @abstractmethod
    def map_order_items(self, raw_order: dict) -> list[dict]:
        """
        Map raw order items from API response to dicts compatible with OrderItem.
        Returns a list of dicts with keys: product, quantity, price.
        (product can be a Product instance or None)
        """
        ...

    def import_orders(self, from_date: date, to_date: date) -> ImportResult:
        """
        Fetch orders from the portal API, map them, and save to database.
        Returns an ImportResult with summary stats.
        """
        result = ImportResult(portal=self.PORTAL_NAME)

        try:
            access_token = self.authenticate()
        except Exception as exc:
            result.errors.append(f"Authentication failed: {exc}")
            return result

        try:
            raw_orders = self.fetch_orders(from_date, to_date, access_token)
        except Exception as exc:
            result.errors.append(f"Fetch orders failed: {exc}")
            return result

        from master.models import Order, OrderItem

        for raw_order in raw_orders:
            order_number = raw_order.get("AmazonOrderId") or raw_order.get("id", "")

            # Skip if already exists
            if Order.objects.filter(order_number=order_number).exists():
                result.skipped_count += 1
                result.skipped_orders.append(f"{order_number}: already exists")
                continue

            try:
                order_data = self.map_order(raw_order)
                items_data = self.map_order_items(raw_order)

                # Validate items have products
                has_missing_product = False
                for item_data in items_data:
                    if item_data.get("product") is None:
                        result.errors.append(
                            f"Order {order_number}: product not found for SKU '{item_data.get('sku', 'N/A')}'"
                        )
                        has_missing_product = True

                if has_missing_product:
                    result.skipped_count += 1
                    result.skipped_orders.append(f"{order_number}: missing product SKU")
                    continue

                with transaction.atomic():
                    order = Order.objects.create(**order_data)

                    for item_data in items_data:
                        OrderItem.objects.create(
                            order=order,
                            product=item_data["product"],
                            quantity=item_data["quantity"],
                            price=item_data["price"],
                        )
                        result.item_count += 1

                result.created_count += 1
                result.created_orders.append(order_number)

            except ValidationError as exc:
                result.skipped_count += 1
                result.skipped_orders.append(f"{order_number}: validation failed")
                result.errors.append(f"Order {order_number}: {exc}")
                continue
            except Exception as exc:
                result.skipped_count += 1
                result.skipped_orders.append(f"{order_number}: error - {exc}")
                result.errors.append(f"Order {order_number}: {exc}")
                continue

        return result


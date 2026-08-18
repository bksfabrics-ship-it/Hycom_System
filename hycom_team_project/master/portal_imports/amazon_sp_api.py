"""
Amazon Selling Partner API (SP-API) integration for importing orders.

Uses the Orders API 2026-01-01 endpoints currently working for Amazon India:
  - GET /orders/2026-01-01/orders
  - GET /orders/2026-01-01/orders/{orderId}

Credentials are loaded from environment variables:
  - SP_API_CLIENT_ID
  - SP_API_CLIENT_SECRET
  - SP_API_REFRESH_TOKEN
  - SP_API_MARKETPLACE_ID
  - SP_API_ENDPOINT
"""

import logging
import os
import time
from dataclasses import dataclass
from datetime import date, datetime, time as datetime_time, timezone
from decimal import Decimal, InvalidOperation
from typing import Optional

import requests
from django.core.exceptions import ValidationError
from django.db import transaction

from master.models import Order, OrderItem, State
from stock.models import Product

from .base import ImportResult, PortalImport

logger = logging.getLogger(__name__)

DEFAULT_SP_API_ENDPOINT = "https://sellingpartnerapi-eu.amazon.com"
SP_API_TOKEN_URL = "https://api.amazon.com/auth/o2/token"
MARKETPLACE_ID_INDIA = "A21TJRUUN4KGV"
ORDERS_API_VERSION = "2026-01-01"
RETRY_STATUS_CODES = {429, 500, 502, 503, 504}
INCLUDED_ORDER_DATA = [
    "BUYER",
    "RECIPIENT",
    "PROCEEDS",
    "EXPENSE",
    "PROMOTION",
    "CANCELLATION",
    "FULFILLMENT",
    "PACKAGES",
]


class AmazonSPAPIError(Exception):
    """Safe SP-API error that never contains credentials or access tokens."""


@dataclass
class AmazonOrderPayload:
    order: dict
    order_items: list[dict]


def get_env_or_raise(key: str) -> str:
    value = os.environ.get(key, "").strip()
    if not value:
        raise ValueError(
            f"Missing required environment variable: {key}. "
            "Please set it in your .env file."
        )
    return value


def parse_sp_api_datetime(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except (ValueError, TypeError):
        return None


def parse_sp_api_decimal(value) -> Decimal:
    if value in (None, ""):
        return Decimal("0")
    if isinstance(value, dict):
        value = value.get("amount") or value.get("Amount")
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def money_amount(value) -> Decimal:
    return parse_sp_api_decimal(value)


def round_money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


def iso_utc_start(value: date) -> str:
    return datetime.combine(value, datetime_time.min, tzinfo=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def iso_utc_end(value: date) -> str:
    return datetime.combine(value, datetime_time.max, tzinfo=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def find_state_by_name(name: Optional[str]) -> Optional[State]:
    if not name:
        return None
    return State.objects.filter(name__iexact=str(name).strip()).first()


def find_product_by_sku(sku: Optional[str]) -> Optional[Product]:
    sku = str(sku or "").strip()
    if not sku:
        return None

    product = Product.objects.filter(sku__iexact=sku).first()
    if product:
        return product

    if sku.upper().endswith("_FBA"):
        return Product.objects.filter(sku__iexact=sku[:-4]).first()

    return None


def map_amazon_status_to_hycom_status(status: Optional[str]) -> str:
    raw_status = str(status or "").strip().upper()
    if "CANCEL" in raw_status:
        return "Cancelled"
    if "RETURN" in raw_status and "ARRIVED" in raw_status:
        return "Return Arrived"
    if "RETURN" in raw_status:
        return "Return In Transit"
    if "SHIP" in raw_status and "UNSHIPPED" not in raw_status:
        return "Shipped"
    return "Pending"


def seller_order_alias(order_data: dict) -> Optional[str]:
    for alias in order_data.get("orderAliases") or []:
        if alias.get("aliasType") == "SELLER_ORDER_ID" and alias.get("aliasId"):
            return alias["aliasId"]
    return None


def recipient_address(order_data: dict) -> dict:
    recipient = order_data.get("recipient") or {}
    return recipient.get("deliveryAddress") or recipient.get("address") or {}


def buyer_name(order_data: dict, address: dict) -> str:
    buyer = order_data.get("buyer") or {}
    return (
        address.get("name")
        or buyer.get("name")
        or buyer.get("buyerName")
        or "Amazon Customer"
    )


def fulfillment_data(order_data: dict) -> dict:
    return order_data.get("fulfillment") or {}


def amazon_fulfillment_to_hycom(order_data: dict) -> str:
    fulfilled_by = str(fulfillment_data(order_data).get("fulfilledBy") or "").upper()
    if fulfilled_by in {"AMAZON", "AFN"}:
        return "amazon"
    return "self"


def order_status_from_payload(order_data: dict) -> str:
    fulfillment = fulfillment_data(order_data)
    cancellation = order_data.get("cancellation") or {}
    return (
        cancellation.get("cancellationStatus")
        or fulfillment.get("fulfillmentStatus")
        or order_data.get("orderStatus")
        or order_data.get("status")
    )


def first_date_from_windows(order_data: dict, *keys: str) -> Optional[date]:
    fulfillment = fulfillment_data(order_data)
    for key in keys:
        window = fulfillment.get(key) or {}
        parsed = parse_sp_api_datetime(
            window.get("latestDateTime")
            or window.get("earliestDateTime")
            or fulfillment.get(key)
        )
        if parsed:
            return parsed
    return None


def breakdown_subtotal(breakdowns: list[dict], *types: str) -> Decimal:
    wanted = {value.upper() for value in types}
    total = Decimal("0")
    for breakdown in breakdowns or []:
        if str(breakdown.get("type") or "").upper() in wanted:
            total += money_amount(breakdown.get("subtotal"))
    return total


def item_quantity(item: dict) -> int:
    try:
        return int(Decimal(str(item.get("quantityOrdered") or 0)))
    except (InvalidOperation, TypeError, ValueError):
        return 0


def item_total_amount(item: dict) -> Decimal:
    proceeds = item.get("proceeds") or {}
    product = item.get("product") or {}
    price = product.get("price") or {}
    quantity = item_quantity(item)

    total = money_amount(proceeds.get("proceedsTotal"))
    if total:
        return total

    unit_price = money_amount(price.get("unitPrice"))
    if unit_price and quantity:
        return unit_price * Decimal(quantity)

    return breakdown_subtotal(proceeds.get("breakdowns") or [], "ITEM", "SHIPPING")


def item_tax_amount(item: dict) -> Decimal:
    proceeds = item.get("proceeds") or {}
    tax = breakdown_subtotal(proceeds.get("breakdowns") or [], "TAX")
    if tax:
        return tax

    tax_data = item.get("tax") or {}
    total = Decimal("0")
    for breakdown in tax_data.get("taxCalculationBreakdowns") or []:
        total += money_amount(breakdown.get("taxAmount"))
    return total


def item_seller_sku(item: dict) -> str:
    product = item.get("product") or {}
    return str(product.get("sellerSku") or item.get("sellerSku") or "").strip()


def order_tax_registration(order_data: dict) -> tuple[bool, str]:
    tax = order_data.get("tax") or {}
    for registration in tax.get("taxRegistrations") or []:
        number = registration.get("taxRegistrationNumber")
        if number:
            return True, str(number).strip()
    return False, ""


def order_amounts_from_items(order_items: list[dict]) -> tuple[Decimal, Decimal, Decimal]:
    total = sum((item_total_amount(item) for item in order_items), Decimal("0"))
    gst = sum((item_tax_amount(item) for item in order_items), Decimal("0"))

    if not total:
        return Decimal("0"), Decimal("0"), Decimal("0")

    if gst:
        amount = total - gst
    else:
        amount = total / Decimal("1.05")
        gst = total - amount

    return round_money(amount), round_money(gst), round_money(total)


def map_amazon_api_order(order_data: dict, order_items: list[dict]) -> dict:
    amazon_order_id = order_data.get("orderId")
    address = recipient_address(order_data)
    state = find_state_by_name(address.get("stateOrRegion"))
    amount, gst, total_amount = order_amounts_from_items(order_items)
    is_b2b, gst_number = order_tax_registration(order_data)
    status = map_amazon_status_to_hycom_status(order_status_from_payload(order_data))
    invoice_date = parse_sp_api_datetime(order_data.get("createdTime")) or date.today()
    ship_date = first_date_from_windows(order_data, "shipByWindow", "deliverByWindow")

    if state and state.code == "33":
        cgst = round_money(gst / Decimal("2"))
        sgst = round_money(gst / Decimal("2"))
        igst = Decimal("0")
    else:
        cgst = Decimal("0")
        sgst = Decimal("0")
        igst = gst

    return {
        "portal": "amazon",
        "order_number": amazon_order_id,
        "customer_name": buyer_name(order_data, address),
        "state": state,
        "state_code": state.code if state else "",
        "invoice_number": seller_order_alias(order_data) or amazon_order_id,
        "invoice_date": invoice_date,
        "ship_date": ship_date if status == "Shipped" else None,
        "fulfilment": amazon_fulfillment_to_hycom(order_data),
        "is_b2b": is_b2b,
        "gst_number": gst_number,
        "status": status,
        "amount": amount,
        "gst": gst,
        "cgst": cgst,
        "sgst": sgst,
        "igst": igst,
        "total_amount": total_amount,
        "remarks": "Imported from Amazon SP-API",
    }


def map_amazon_api_order_items(order_items: list[dict]) -> list[dict]:
    mapped_items = []
    for item in order_items:
        quantity = item_quantity(item)
        if quantity <= 0:
            continue

        sku = item_seller_sku(item)
        product = find_product_by_sku(sku)
        total = item_total_amount(item)
        unit_price = total / Decimal(quantity) if quantity else Decimal("0")
        mapped_items.append(
            {
                "product": product,
                "quantity": quantity,
                "price": round_money(unit_price),
                "sku": sku,
                "amazon_order_item_id": item.get("orderItemId"),
            }
        )
    return mapped_items


class AmazonSPAPIClient:
    """Reusable client for LWA auth and Orders API 2026-01-01 requests."""

    def __init__(self):
        self.client_id = get_env_or_raise("SP_API_CLIENT_ID")
        self.client_secret = get_env_or_raise("SP_API_CLIENT_SECRET")
        self.refresh_token = get_env_or_raise("SP_API_REFRESH_TOKEN")
        self.marketplace_id = os.environ.get(
            "SP_API_MARKETPLACE_ID", MARKETPLACE_ID_INDIA
        ).strip()
        self.endpoint = os.environ.get(
            "SP_API_ENDPOINT", DEFAULT_SP_API_ENDPOINT
        ).strip().rstrip("/")
        self.session = requests.Session()
        self.access_token = ""

    def authenticate(self) -> str:
        payload = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
        }
        response = requests.post(
            SP_API_TOKEN_URL,
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
        if response.status_code >= 400:
            raise AmazonSPAPIError(
                f"Amazon LWA authentication failed: HTTP {response.status_code}"
            )

        access_token = response.json().get("access_token")
        if not access_token:
            raise AmazonSPAPIError("Amazon LWA authentication failed: missing access token")

        self.access_token = access_token
        logger.info("Amazon SP-API LWA authentication succeeded")
        return access_token

    def get(self, path: str, params: Optional[dict] = None) -> dict:
        if not self.access_token:
            self.authenticate()

        url = f"{self.endpoint}{path}"
        headers = {
            "x-amz-access-token": self.access_token,
            "Accept": "application/json",
            "User-Agent": "Hycom-Order-Importer/1.0",
        }
        last_error = None

        for attempt in range(1, 4):
            try:
                response = self.session.get(
                    url, headers=headers, params=params or {}, timeout=60
                )
            except requests.exceptions.RequestException as exc:
                last_error = str(exc)
                if attempt == 3:
                    raise AmazonSPAPIError(f"Amazon SP-API network error: {exc}") from exc
                time.sleep(2 ** (attempt - 1))
                continue

            if response.status_code < 400:
                return response.json()

            message = safe_error_message(response)
            if response.status_code not in RETRY_STATUS_CODES or attempt == 3:
                raise AmazonSPAPIError(
                    f"Amazon SP-API Error: HTTP {response.status_code}. {message}"
                )

            last_error = message
            retry_after = response.headers.get("Retry-After")
            try:
                sleep_seconds = int(retry_after) if retry_after else 2 ** (attempt - 1)
            except ValueError:
                sleep_seconds = 2 ** (attempt - 1)
            time.sleep(min(sleep_seconds, 10))

        raise AmazonSPAPIError(f"Amazon SP-API request failed: {last_error}")

    def search_orders(self, from_date: date, to_date: date) -> list[dict]:
        path = f"/orders/{ORDERS_API_VERSION}/orders"
        all_orders = []
        params = {
            "createdAfter": iso_utc_start(from_date),
            "createdBefore": iso_utc_end(to_date),
            "marketplaceIds": self.marketplace_id,
            "maxResultsPerPage": 100,
        }

        while True:
            data = self.get(path, params=params)
            orders = data.get("orders") or data.get("payload", {}).get("orders") or []
            all_orders.extend(orders)

            pagination = data.get("pagination") or data.get("payload", {}).get("pagination") or {}
            next_token = pagination.get("nextToken") or data.get("nextToken")
            if not next_token:
                break

            params = {"paginationToken": next_token}

        return all_orders

    def get_order(self, order_id: str, pagination_token: str = "") -> dict:
        path = f"/orders/{ORDERS_API_VERSION}/orders/{order_id}"
        params = {"includedData": ",".join(INCLUDED_ORDER_DATA)}
        if pagination_token:
            params["paginationToken"] = pagination_token
        data = self.get(path, params=params)
        return data.get("order") or data.get("payload", {}).get("order") or {}

    def get_order_with_items(self, order_id: str) -> dict:
        order = self.get_order(order_id)
        items = list(order.get("orderItems") or [])

        pagination = order.get("pagination") or {}
        next_token = pagination.get("nextToken")
        while next_token:
            order_page = self.get_order(order_id, pagination_token=next_token)
            items.extend(order_page.get("orderItems") or [])
            pagination = order_page.get("pagination") or {}
            next_token = pagination.get("nextToken")

        order["orderItems"] = items
        return order


def safe_error_message(response: requests.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        return response.text[:500]

    errors = data.get("errors") or data.get("Errors") or []
    if errors:
        first = errors[0]
        return str(first.get("message") or first.get("Message") or first)[:500]
    return str(data)[:500]


class AmazonSPAPI(PortalImport):
    """Amazon SP-API importer using Orders API 2026-01-01."""

    PORTAL_NAME = "amazon"

    def __init__(self):
        self.client: Optional[AmazonSPAPIClient] = None

    def authenticate(self) -> str:
        self.client = AmazonSPAPIClient()
        return self.client.authenticate()

    def fetch_orders(self, from_date: date, to_date: date, access_token: str = "") -> list[dict]:
        if not self.client:
            self.authenticate()

        logger.info(
            "Amazon SP-API synchronization started. Date range: %s -> %s",
            from_date,
            to_date,
        )
        orders = self.client.search_orders(from_date, to_date)
        logger.info("Amazon orders fetched: %s", len(orders))
        return orders

    def fetch_complete_order(self, order_id: str) -> AmazonOrderPayload:
        if not self.client:
            self.authenticate()
        order = self.client.get_order_with_items(order_id)
        return AmazonOrderPayload(order=order, order_items=order.get("orderItems") or [])

    def map_order(self, raw_order: dict) -> dict:
        return map_amazon_api_order(raw_order, raw_order.get("orderItems") or [])

    def map_order_items(self, raw_order: dict) -> list[dict]:
        return map_amazon_api_order_items(raw_order.get("orderItems") or [])

    def import_orders(self, from_date: date, to_date: date) -> ImportResult:
        result = ImportResult(portal=self.PORTAL_NAME)

        try:
            self.authenticate()
            search_orders = self.fetch_orders(from_date, to_date)
        except Exception as exc:
            result.failed_count += 1
            result.errors.append(str(exc))
            return result

        result.found_count = len(search_orders)

        for search_order in search_orders:
            amazon_order_id = search_order.get("orderId")
            if not amazon_order_id:
                result.skipped_count += 1
                result.skipped_orders.append("Amazon order without orderId")
                continue

            try:
                complete = self.fetch_complete_order(amazon_order_id)
                complete.order["orderItems"] = complete.order_items
                order_data = map_amazon_api_order(complete.order, complete.order_items)
                items_data = map_amazon_api_order_items(complete.order_items)

                unmapped = sorted(
                    {
                        item.get("sku") or "UNKNOWN"
                        for item in items_data
                        if item.get("product") is None
                    }
                )
                if unmapped:
                    result.skipped_count += 1
                    for sku in unmapped:
                        if sku not in result.unmapped_skus:
                            result.unmapped_skus.append(sku)
                        result.errors.append(f"Unmapped SKU: {sku}")
                    result.skipped_orders.append(
                        f"{amazon_order_id}: missing product SKU"
                    )
                    logger.warning(
                        "Amazon order %s skipped because of unmapped SKU(s): %s",
                        amazon_order_id,
                        ", ".join(unmapped),
                    )
                    continue

                if not items_data:
                    result.skipped_count += 1
                    result.skipped_orders.append(f"{amazon_order_id}: no valid items")
                    result.errors.append(
                        f"Order {amazon_order_id}: no valid order items returned"
                    )
                    continue

                with transaction.atomic():
                    order, created = Order.objects.select_for_update().get_or_create(
                        order_number=amazon_order_id,
                        defaults=order_data,
                    )

                    if created:
                        result.created_count += 1
                        result.created_orders.append(amazon_order_id)
                        logger.info("Created Amazon order: %s", amazon_order_id)
                    else:
                        for field, value in order_data.items():
                            setattr(order, field, value)
                        order.save()
                        result.updated_count += 1
                        result.updated_orders.append(amazon_order_id)
                        logger.info("Updated Amazon order: %s", amazon_order_id)

                    existing_item_count = order.items.count()
                    if existing_item_count:
                        order.items.all().delete()

                    for item_data in items_data:
                        OrderItem.objects.create(
                            order=order,
                            product=item_data["product"],
                            quantity=item_data["quantity"],
                            price=item_data["price"],
                        )

                    if created:
                        result.item_count += len(items_data)
                    else:
                        result.item_updated_count += len(items_data)

            except ValidationError as exc:
                result.failed_count += 1
                result.errors.append(f"Order {amazon_order_id}: {exc}")
                logger.exception("Validation failed for Amazon order %s", amazon_order_id)
            except Exception as exc:
                result.failed_count += 1
                result.errors.append(
                    f"Unable to import Amazon order {amazon_order_id}: {exc}"
                )
                logger.exception("Error importing Amazon order %s", amazon_order_id)

        logger.info(
            "Amazon synchronization completed. Found=%s Created=%s Updated=%s "
            "ItemsCreated=%s ItemsUpdated=%s Skipped=%s Failed=%s UnmappedSKUs=%s",
            result.found_count,
            result.created_count,
            result.updated_count,
            result.item_count,
            result.item_updated_count,
            result.skipped_count,
            result.failed_count,
            len(result.unmapped_skus),
        )
        return result


def import_amazon_orders_via_api(from_date: date, to_date: date) -> ImportResult:
    importer = AmazonSPAPI()
    return importer.import_orders(from_date, to_date)

"""
Flipkart Marketplace Seller API integration for importing orders.

Uses the Seller API endpoints documented by Flipkart:
  - GET /oauth-service/oauth/token
  - POST /sellers/v3/shipments/filter/

Credentials are loaded from environment variables:
  - FLIPKART_APP_ID
  - FLIPKART_APP_SECRET
  - FLIPKART_REFRESH_TOKEN (optional)
  - FLIPKART_API_ENDPOINT
"""

import base64
import logging
import os
import time
from collections import defaultdict
from datetime import date, datetime, time as datetime_time
from decimal import Decimal, InvalidOperation
from typing import Optional
from urllib.parse import urljoin

import requests
from django.core.exceptions import ValidationError
from django.db import transaction

from master.models import Order, OrderItem, State
from stock.models import Product

from .base import ImportResult, PortalImport

logger = logging.getLogger(__name__)

DEFAULT_FLIPKART_ENDPOINT = "https://api.flipkart.net"
FLIPKART_TOKEN_PATH = "/oauth-service/oauth/token"
RETRY_STATUS_CODES = {429, 500, 502, 503, 504}

PREDISPATCH_STATES = [
    "APPROVED",
    "PACKING_IN_PROGRESS",
    "PACKED",
    "FORM_FAILED",
    "READY_TO_DISPATCH",
]
POSTDISPATCH_STATES = ["SHIPPED", "DELIVERED", "PICKUP_COMPLETE"]
CANCELLED_STATES = ["CANCELLED"]


class FlipkartAPIError(Exception):
    """Safe Flipkart API error that never contains credentials or access tokens."""


def get_env_or_raise(key: str) -> str:
    value = os.environ.get(key, "").strip()
    if not value:
        raise ValueError(
            f"Missing required environment variable: {key}. "
            "Please set it in your .env file."
        )
    return value


def parse_flipkart_datetime(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except (ValueError, TypeError):
        return None


def parse_decimal(value) -> Decimal:
    if value in (None, ""):
        return Decimal("0")
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def round_money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


def iso_start(value: date) -> str:
    return datetime.combine(value, datetime_time.min).isoformat()


def iso_end(value: date) -> str:
    return datetime.combine(value, datetime_time.max).isoformat()


def find_state_by_name(name: Optional[str]) -> Optional[State]:
    if not name:
        return None
    return State.objects.filter(name__iexact=str(name).strip()).first()


def find_product_by_sku(sku: Optional[str]) -> Optional[Product]:
    sku = str(sku or "").strip()
    if not sku:
        return None

    return Product.objects.filter(sku__iexact=sku).first()


def safe_error_message(response: requests.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        return response.text[:500]

    errors = data.get("errors") or data.get("Errors") or []
    if errors:
        first = errors[0]
        return str(first.get("message") or first.get("Message") or first)[:500]

    return str(
        data.get("message")
        or data.get("error_description")
        or data.get("error")
        or data
    )[:500]


def shipment_address(shipment: dict) -> dict:
    for key in ("deliveryAddress", "shippingAddress", "address", "recipientAddress"):
        address = shipment.get(key)
        if isinstance(address, dict):
            return address
    return {}


def shipment_order_items(shipment: dict) -> list[dict]:
    items = shipment.get("orderItems") or shipment.get("order_items") or []
    return items if isinstance(items, list) else []


def item_quantity(item: dict) -> int:
    try:
        return int(Decimal(str(item.get("quantity") or 0)))
    except (InvalidOperation, TypeError, ValueError):
        return 0


def price_components(item: dict) -> dict:
    components = item.get("priceComponents") or item.get("price_components") or {}
    return components if isinstance(components, dict) else {}


def item_total_amount(item: dict) -> Decimal:
    components = price_components(item)
    total = parse_decimal(components.get("totalPrice"))
    if total:
        return total

    customer_price = parse_decimal(components.get("customerPrice"))
    shipping = parse_decimal(components.get("shippingCharge"))
    if customer_price or shipping:
        return customer_price + shipping

    selling_price = parse_decimal(components.get("sellingPrice"))
    return selling_price * Decimal(item_quantity(item) or 1)


def item_sku(item: dict) -> str:
    return str(item.get("sku") or item.get("sellerSku") or "").strip()


def item_order_id(item: dict, shipment: dict) -> str:
    return str(
        item.get("orderId")
        or item.get("order_id")
        or shipment.get("orderId")
        or shipment.get("order_id")
        or shipment.get("shipmentId")
        or ""
    ).strip()


def item_status(item: dict, shipment: dict) -> str:
    return str(item.get("status") or shipment.get("status") or "").strip().upper()


def map_flipkart_status(statuses: list[str]) -> str:
    normalized = {str(status or "").upper() for status in statuses}
    if "CANCELLED" in normalized:
        return "Cancelled"
    if "RETURNED" in normalized:
        return "Return Arrived"
    if "RETURN_REQUESTED" in normalized:
        return "Return In Transit"
    if normalized & {"SHIPPED", "DELIVERED", "PICKUP_COMPLETE"}:
        return "Shipped"
    return "Pending"


def shipment_fulfilment(shipment: dict) -> str:
    shipment_type = str(shipment.get("shipmentType") or "").strip().upper()
    service_profile = str(shipment.get("serviceProfile") or "").strip().upper()
    if shipment_type == "SELF" or service_profile == "SELF":
        return "self"
    return "flipkart"


def order_amounts(items: list[dict]) -> tuple[Decimal, Decimal, Decimal]:
    total = sum((item_total_amount(item) for item in items), Decimal("0"))
    if not total:
        return Decimal("0"), Decimal("0"), Decimal("0")

    amount = total / Decimal("1.05")
    gst = total - amount
    return round_money(amount), round_money(gst), round_money(total)


def map_flipkart_order(order_id: str, shipments: list[dict], items: list[dict]) -> dict:
    first_shipment = shipments[0] if shipments else {}
    first_item = items[0] if items else {}
    address = shipment_address(first_shipment)
    state = find_state_by_name(
        address.get("state") or address.get("stateOrRegion") or address.get("state_name")
    )
    statuses = [item_status(item, first_shipment) for item in items]
    status = map_flipkart_status(statuses)
    invoice_date = (
        parse_flipkart_datetime(first_item.get("orderDate"))
        or parse_flipkart_datetime(first_shipment.get("createdAt"))
        or parse_flipkart_datetime(first_shipment.get("updatedAt"))
        or date.today()
    )
    ship_date = (
        parse_flipkart_datetime(first_shipment.get("dispatchByDate"))
        if status == "Shipped"
        else None
    )
    amount, gst, total_amount = order_amounts(items)

    if state and state.code == "33":
        cgst = round_money(gst / Decimal("2"))
        sgst = round_money(gst / Decimal("2"))
        igst = Decimal("0")
    else:
        cgst = Decimal("0")
        sgst = Decimal("0")
        igst = gst

    return {
        "portal": "flipkart",
        "order_number": order_id,
        "customer_name": address.get("name") or "Flipkart Customer",
        "state": state,
        "state_code": state.code if state else "",
        "invoice_number": order_id,
        "invoice_date": invoice_date,
        "ship_date": ship_date,
        "fulfilment": shipment_fulfilment(first_shipment),
        "is_b2b": False,
        "gst_number": "",
        "status": status,
        "amount": amount,
        "gst": gst,
        "cgst": cgst,
        "sgst": sgst,
        "igst": igst,
        "total_amount": total_amount,
        "remarks": "Imported from Flipkart API",
    }


def map_flipkart_order_items(items: list[dict]) -> list[dict]:
    mapped_items = []
    seen_order_item_ids = set()

    for item in items:
        order_item_id = item.get("orderItemId") or item.get("order_item_id")
        if order_item_id:
            if order_item_id in seen_order_item_ids:
                continue
            seen_order_item_ids.add(order_item_id)

        quantity = item_quantity(item)
        if quantity <= 0:
            continue

        sku = item_sku(item)
        product = find_product_by_sku(sku)
        total = item_total_amount(item)
        unit_price = total / Decimal(quantity) if quantity else Decimal("0")
        mapped_items.append(
            {
                "product": product,
                "quantity": quantity,
                "price": round_money(unit_price),
                "sku": sku,
                "flipkart_order_item_id": order_item_id,
            }
        )

    return mapped_items


class FlipkartAPIClient:
    def __init__(self):
        self.app_id = get_env_or_raise("FLIPKART_APP_ID")
        self.app_secret = get_env_or_raise("FLIPKART_APP_SECRET")
        self.refresh_token = os.environ.get("FLIPKART_REFRESH_TOKEN", "").strip()
        self.endpoint = os.environ.get(
            "FLIPKART_API_ENDPOINT", DEFAULT_FLIPKART_ENDPOINT
        ).strip().rstrip("/")
        self.session = requests.Session()
        self.access_token = ""

    def basic_auth_header(self) -> str:
        credentials = f"{self.app_id}:{self.app_secret}".encode("utf-8")
        return "Basic " + base64.b64encode(credentials).decode("ascii")

    def authenticate(self) -> str:
        params = {"scope": "Seller_Api"}
        if self.refresh_token:
            params["grant_type"] = "refresh_token"
            params["refresh_token"] = self.refresh_token
        else:
            params["grant_type"] = "client_credentials"

        response = self.session.get(
            urljoin(self.endpoint, FLIPKART_TOKEN_PATH),
            params=params,
            headers={"Authorization": self.basic_auth_header()},
            timeout=30,
        )
        if response.status_code >= 400:
            raise FlipkartAPIError(
                f"Flipkart authentication failed: HTTP {response.status_code}. "
                f"{safe_error_message(response)}"
            )

        token = response.json().get("access_token")
        if not token:
            raise FlipkartAPIError("Flipkart authentication failed: missing access token")

        self.access_token = token
        logger.info("Flipkart authentication succeeded")
        return token

    def request(
        self,
        method: str,
        path: str = "",
        *,
        url: str = "",
        json_body: Optional[dict] = None,
    ) -> dict:
        if not self.access_token:
            self.authenticate()

        request_url = url or urljoin(self.endpoint, path)
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "Hycom-Order-Importer/1.0",
        }
        last_error = None

        for attempt in range(1, 4):
            try:
                response = self.session.request(
                    method,
                    request_url,
                    headers=headers,
                    json=json_body,
                    timeout=60,
                )
            except requests.exceptions.RequestException as exc:
                last_error = str(exc)
                if attempt == 3:
                    raise FlipkartAPIError(f"Flipkart network error: {exc}") from exc
                time.sleep(2 ** (attempt - 1))
                continue

            if response.status_code < 400:
                return response.json() if response.content else {}

            message = safe_error_message(response)
            if response.status_code not in RETRY_STATUS_CODES or attempt == 3:
                raise FlipkartAPIError(
                    f"Flipkart API Error: HTTP {response.status_code}. {message}"
                )

            last_error = message
            retry_after = response.headers.get("Retry-After")
            try:
                sleep_seconds = int(retry_after) if retry_after else 2 ** (attempt - 1)
            except ValueError:
                sleep_seconds = 2 ** (attempt - 1)
            time.sleep(min(sleep_seconds, 10))

        raise FlipkartAPIError(f"Flipkart API request failed: {last_error}")

    def search_shipments_by_filter(self, filter_payload: dict) -> list[dict]:
        shipments = []
        body = {
            "filter": filter_payload,
            "pagination": {"pageSize": 20},
            "sort": {"field": "dispatchByDate", "order": "asc"},
        }

        data = self.request("POST", "/sellers/v3/shipments/filter/", json_body=body)
        shipments.extend(data.get("shipments") or [])

        next_page_url = data.get("nextPageUrl") or data.get("nextPageURL")
        while next_page_url:
            data = self.request("GET", url=next_page_url)
            shipments.extend(data.get("shipments") or [])
            next_page_url = data.get("nextPageUrl") or data.get("nextPageURL")

        return shipments

    def search_shipments(self, from_date: date, to_date: date) -> list[dict]:
        order_date = {"from": iso_start(from_date), "to": iso_end(to_date)}
        filters = [
            {
                "type": "preDispatch",
                "states": PREDISPATCH_STATES,
                "orderDate": order_date,
            },
            {
                "type": "postDispatch",
                "states": POSTDISPATCH_STATES,
                "shipmentTypes": ["NORMAL"],
                "orderDate": order_date,
            },
            {
                "type": "postDispatch",
                "states": POSTDISPATCH_STATES,
                "shipmentTypes": ["SELF"],
                "orderDate": order_date,
            },
            {
                "type": "cancelled",
                "states": CANCELLED_STATES,
                "orderDate": order_date,
            },
        ]

        shipments = []
        for filter_payload in filters:
            shipments.extend(self.search_shipments_by_filter(filter_payload))
        return shipments


class FlipkartAPI(PortalImport):
    PORTAL_NAME = "flipkart"

    def __init__(self):
        self.client: Optional[FlipkartAPIClient] = None

    def authenticate(self) -> str:
        self.client = FlipkartAPIClient()
        return self.client.authenticate()

    def fetch_orders(self, from_date: date, to_date: date, access_token: str = "") -> list[dict]:
        if not self.client:
            self.authenticate()

        logger.info(
            "Flipkart synchronization started. Date range: %s -> %s",
            from_date,
            to_date,
        )
        shipments = self.client.search_shipments(from_date, to_date)
        logger.info("Flipkart shipments fetched: %s", len(shipments))
        return shipments

    def map_order(self, raw_order: dict) -> dict:
        shipments = raw_order.get("shipments") or []
        items = raw_order.get("items") or []
        return map_flipkart_order(raw_order["order_id"], shipments, items)

    def map_order_items(self, raw_order: dict) -> list[dict]:
        return map_flipkart_order_items(raw_order.get("items") or [])

    def import_orders(self, from_date: date, to_date: date) -> ImportResult:
        result = ImportResult(portal=self.PORTAL_NAME)

        try:
            self.authenticate()
            shipments = self.fetch_orders(from_date, to_date)
        except Exception as exc:
            result.failed_count += 1
            result.errors.append(str(exc))
            return result

        grouped_shipments = defaultdict(list)
        grouped_items = defaultdict(list)

        for shipment in shipments:
            for item in shipment_order_items(shipment):
                order_id = item_order_id(item, shipment)
                if not order_id:
                    result.skipped_count += 1
                    result.skipped_orders.append(
                        f"Shipment {shipment.get('shipmentId') or 'UNKNOWN'}: missing orderId"
                    )
                    continue

                grouped_shipments[order_id].append(shipment)
                grouped_items[order_id].append(item)

        result.found_count = len(grouped_items)

        for order_id, items in grouped_items.items():
            shipments_for_order = grouped_shipments[order_id]

            try:
                order_data = map_flipkart_order(order_id, shipments_for_order, items)
                items_data = map_flipkart_order_items(items)

                unmapped = sorted(
                    {
                        item.get("sku") or "UNKNOWN"
                        for item in items_data
                        if item.get("product") is None
                    }
                )
                if unmapped:
                    result.skipped_count += 1
                    result.skipped_orders.append(f"{order_id}: missing product SKU")
                    for sku in unmapped:
                        if sku not in result.unmapped_skus:
                            result.unmapped_skus.append(sku)
                        result.errors.append(f"Unmapped Flipkart SKU: {sku}")
                    logger.warning(
                        "Flipkart order %s skipped because of unmapped SKU(s): %s",
                        order_id,
                        ", ".join(unmapped),
                    )
                    continue

                if not items_data:
                    result.skipped_count += 1
                    result.skipped_orders.append(f"{order_id}: no valid items")
                    result.errors.append(
                        f"Order {order_id}: no valid order items returned"
                    )
                    continue

                with transaction.atomic():
                    order, created = Order.objects.select_for_update().get_or_create(
                        order_number=order_id,
                        defaults=order_data,
                    )

                    if created:
                        result.created_count += 1
                        result.created_orders.append(order_id)
                        logger.info("Created Flipkart order: %s", order_id)
                    else:
                        for field, value in order_data.items():
                            setattr(order, field, value)
                        order.save()
                        result.updated_count += 1
                        result.updated_orders.append(order_id)
                        logger.info("Updated Flipkart order: %s", order_id)

                    if order.items.exists():
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
                result.errors.append(f"Order {order_id}: {exc}")
                logger.exception("Validation failed for Flipkart order %s", order_id)
            except Exception as exc:
                result.failed_count += 1
                result.errors.append(
                    f"Unable to import Flipkart order {order_id}: {exc}"
                )
                logger.exception("Error importing Flipkart order %s", order_id)

        logger.info(
            "Flipkart synchronization completed. Found=%s Created=%s Updated=%s "
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


def import_flipkart_orders_via_api(from_date: date, to_date: date) -> ImportResult:
    importer = FlipkartAPI()
    return importer.import_orders(from_date, to_date)

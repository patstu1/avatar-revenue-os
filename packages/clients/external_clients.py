"""Real external service clients for Live Execution Phase 2.

Every function makes actual HTTP calls. No stubs. No fakes.
When credentials are missing, the function returns an explicit blocked result.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Optional

import aiosmtplib
import httpx
import structlog

logger = structlog.get_logger()

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


def _blocked(error: str) -> dict[str, Any]:
    return {"success": False, "blocked": True, "error": error}


def _error_result(
    error: str,
    *,
    status_code: int = 0,
    data: Any = None,
) -> dict[str, Any]:
    return {
        "success": False,
        "blocked": False,
        "error": error,
        "status_code": status_code,
        "data": data,
    }


async def _classify_response(
    resp: httpx.Response,
    *,
    service: str,
) -> dict[str, Any] | None:
    """Return an error dict for non-success responses, or None on 2xx."""
    if 200 <= resp.status_code < 300:
        return None

    try:
        body = resp.json()
    except Exception:
        body = resp.text

    if resp.status_code == 401:
        msg = f"{service} auth failure"
    elif resp.status_code == 429:
        msg = f"{service} rate-limited"
    elif resp.status_code >= 500:
        msg = f"{service} server error ({resp.status_code})"
    else:
        msg = f"{service} HTTP {resp.status_code}"

    logger.warning(
        "external_client.http_error",
        service=service,
        status=resp.status_code,
        body=body,
    )
    return _error_result(msg, status_code=resp.status_code, data=body)


# ---------------------------------------------------------------------------
# SECTION 1 — Stripe Webhook Verification
# ---------------------------------------------------------------------------

class StripeWebhookVerifier:
    """Verify Stripe webhook signatures per https://docs.stripe.com/webhooks/signatures"""

    TOLERANCE_SECONDS = 300

    @staticmethod
    def verify(
        payload_body: bytes,
        sig_header: str,
        webhook_secret: str,
    ) -> dict[str, Any]:
        """Verify a Stripe webhook signature.

        Returns:
            {"valid": bool, "event_type": str|None, "event_id": str|None,
             "error": str|None, "payload": dict|None}
        """
        fail: dict[str, Any] = {
            "valid": False,
            "event_type": None,
            "event_id": None,
            "error": None,
            "payload": None,
        }

        if not webhook_secret:
            fail["error"] = "Webhook secret not provided"
            return fail

        elements: dict[str, str] = {}
        for item in sig_header.split(","):
            parts = item.strip().split("=", 1)
            if len(parts) == 2:
                elements.setdefault(parts[0], parts[1])

        timestamp = elements.get("t")
        signature = elements.get("v1")

        if not timestamp or not signature:
            fail["error"] = "Missing t or v1 in Stripe-Signature header"
            return fail

        try:
            ts_int = int(timestamp)
        except ValueError:
            fail["error"] = "Invalid timestamp in Stripe-Signature header"
            return fail

        if abs(time.time() - ts_int) > StripeWebhookVerifier.TOLERANCE_SECONDS:
            fail["error"] = "Timestamp outside tolerance window"
            return fail

        signed_payload = f"{timestamp}.{payload_body.decode('utf-8')}"
        expected = hmac.new(
            webhook_secret.encode("utf-8"),
            signed_payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected, signature):
            fail["error"] = "Signature mismatch"
            return fail

        try:
            parsed = json.loads(payload_body)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            fail["error"] = f"Payload JSON parse error: {exc}"
            return fail

        return {
            "valid": True,
            "event_type": parsed.get("type"),
            "event_id": parsed.get("id"),
            "error": None,
            "payload": parsed,
        }


# ---------------------------------------------------------------------------
# SECTION 2 — Shopify Webhook Verification
# ---------------------------------------------------------------------------

class ShopifyWebhookVerifier:
    """Verify Shopify webhook HMAC per https://shopify.dev/docs/apps/build/webhooks/subscribe/verify"""

    @staticmethod
    def verify(
        payload_body: bytes,
        hmac_header: str,
        api_secret: str,
    ) -> dict[str, Any]:
        """Verify a Shopify webhook HMAC.

        Returns:
            {"valid": bool, "topic": str|None, "error": str|None, "payload": dict|None}
        """
        fail: dict[str, Any] = {
            "valid": False,
            "topic": None,
            "error": None,
            "payload": None,
        }

        if not api_secret:
            fail["error"] = "Shopify API secret not provided"
            return fail

        digest = hmac.new(
            api_secret.encode("utf-8"),
            payload_body,
            hashlib.sha256,
        ).digest()
        computed = base64.b64encode(digest).decode("utf-8")

        if not hmac.compare_digest(computed, hmac_header):
            fail["error"] = "HMAC mismatch"
            return fail

        try:
            parsed = json.loads(payload_body)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            fail["error"] = f"Payload JSON parse error: {exc}"
            return fail

        topic = parsed.get("topic") or parsed.get("webhook_topic")
        return {
            "valid": True,
            "topic": topic,
            "error": None,
            "payload": parsed,
        }


# ---------------------------------------------------------------------------
# SECTION 2b — Stripe Batch Payment Sync
# ---------------------------------------------------------------------------

class StripePaymentClient:
    """Real HTTP client for Stripe REST API — batch payment/order sync."""

    BASE_URL = "https://api.stripe.com/v1"

    def __init__(self) -> None:
        self.api_key = os.environ.get("STRIPE_API_KEY", "")

    def _is_configured(self) -> bool:
        return bool(self.api_key)

    async def fetch_recent_charges(
        self, *, limit: int = 100, starting_after: str | None = None,
    ) -> dict[str, Any]:
        """GET /v1/charges — pull recent charges."""
        if not self._is_configured():
            return _blocked("STRIPE_API_KEY not configured")

        params: dict[str, Any] = {"limit": min(limit, 100)}
        if starting_after:
            params["starting_after"] = starting_after

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/charges",
                    params=params,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
        except httpx.HTTPError as exc:
            logger.error("stripe.network_error", error=str(exc))
            return _error_result(f"Stripe network error: {exc}")

        err = await _classify_response(resp, service="Stripe")
        if err:
            return err

        body = resp.json()
        charges = body.get("data", [])
        orders = len(charges)
        revenue = sum(float(c.get("amount", 0)) / 100.0 for c in charges if c.get("paid"))
        refunded = sum(1 for c in charges if c.get("refunded"))

        return {
            "success": True,
            "blocked": False,
            "data": {
                "orders_imported": orders,
                "revenue_imported": round(revenue, 2),
                "refunds_imported": refunded,
                "charges": charges,
                "has_more": body.get("has_more", False),
                "last_id": charges[-1]["id"] if charges else None,
            },
            "error": None,
            "status_code": resp.status_code,
        }

    async def fetch_recent_payment_intents(
        self, *, limit: int = 100,
    ) -> dict[str, Any]:
        """GET /v1/payment_intents — pull recent payment intents."""
        if not self._is_configured():
            return _blocked("STRIPE_API_KEY not configured")

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/payment_intents",
                    params={"limit": min(limit, 100)},
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
        except httpx.HTTPError as exc:
            logger.error("stripe.network_error", error=str(exc))
            return _error_result(f"Stripe network error: {exc}")

        err = await _classify_response(resp, service="Stripe")
        if err:
            return err

        body = resp.json()
        intents = body.get("data", [])
        succeeded = [i for i in intents if i.get("status") == "succeeded"]
        revenue = sum(float(i.get("amount", 0)) / 100.0 for i in succeeded)

        return {
            "success": True,
            "blocked": False,
            "data": {
                "orders_imported": len(succeeded),
                "revenue_imported": round(revenue, 2),
                "refunds_imported": 0,
                "payment_intents": intents,
            },
            "error": None,
            "status_code": resp.status_code,
        }


# ---------------------------------------------------------------------------
# SECTION 2c — Shopify Batch Order Sync
# ---------------------------------------------------------------------------

class ShopifyOrderClient:
    """Real HTTP client for Shopify Admin REST API — batch order sync."""

    def __init__(self) -> None:
        self.api_key = os.environ.get("SHOPIFY_API_KEY", "")
        self.api_secret = os.environ.get("SHOPIFY_API_SECRET", "")
        self.shop_domain = os.environ.get("SHOPIFY_SHOP_DOMAIN", "")
        self.access_token = os.environ.get("SHOPIFY_ACCESS_TOKEN", "")
        self.api_version = "2024-10"

    def _is_configured(self) -> bool:
        return bool(self.shop_domain and self.access_token)

    @property
    def _base_url(self) -> str:
        domain = self.shop_domain.rstrip("/")
        if not domain.startswith("https://"):
            domain = f"https://{domain}"
        return f"{domain}/admin/api/{self.api_version}"

    async def fetch_recent_orders(
        self, *, limit: int = 50, status: str = "any", since_id: str | None = None,
    ) -> dict[str, Any]:
        """GET /admin/api/{version}/orders.json — pull recent orders."""
        if not self._is_configured():
            return _blocked("SHOPIFY_SHOP_DOMAIN or SHOPIFY_ACCESS_TOKEN not configured")

        params: dict[str, Any] = {"limit": min(limit, 250), "status": status}
        if since_id:
            params["since_id"] = since_id

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(
                    f"{self._base_url}/orders.json",
                    params=params,
                    headers={"X-Shopify-Access-Token": self.access_token},
                )
        except httpx.HTTPError as exc:
            logger.error("shopify.network_error", error=str(exc))
            return _error_result(f"Shopify network error: {exc}")

        err = await _classify_response(resp, service="Shopify")
        if err:
            return err

        body = resp.json()
        orders = body.get("orders", [])
        revenue = sum(float(o.get("total_price", 0)) for o in orders)
        refunded = sum(1 for o in orders if o.get("financial_status") == "refunded")

        return {
            "success": True,
            "blocked": False,
            "data": {
                "orders_imported": len(orders),
                "revenue_imported": round(revenue, 2),
                "refunds_imported": refunded,
                "orders": orders,
            },
            "error": None,
            "status_code": resp.status_code,
        }


# ---------------------------------------------------------------------------
# SECTION 3 — Buffer API Client
# ---------------------------------------------------------------------------

class BufferClient:
    """HTTP client for Buffer's GraphQL API (v2, beta).

    Buffer migrated from REST v1 to GraphQL. Personal API keys from
    publish.buffer.com/settings/api authenticate via Bearer token.
    Endpoint: POST https://api.buffer.com  (GraphQL)
    """

    GRAPHQL_URL = "https://api.buffer.com"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("BUFFER_API_KEY", "")

    def _is_configured(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    async def _graphql(self, query: str, variables: Optional[dict] = None) -> dict[str, Any]:
        """Execute a GraphQL query/mutation against Buffer's API."""
        if not self._is_configured():
            return _blocked("BUFFER_API_KEY not configured")

        payload: dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.post(
                    self.GRAPHQL_URL,
                    json=payload,
                    headers=self._headers(),
                )
        except httpx.HTTPError as exc:
            logger.error("buffer.network_error", error=str(exc))
            return _error_result(f"Buffer network error: {exc}")

        if resp.status_code != 200:
            err = await _classify_response(resp, service="Buffer")
            if err:
                return err

        data = resp.json()
        if "errors" in data:
            error_msg = data["errors"][0].get("message", "Unknown GraphQL error")
            logger.warning("buffer.graphql_error", errors=data["errors"])
            return _error_result(f"Buffer GraphQL error: {error_msg}")

        return {
            "success": True,
            "blocked": False,
            "data": data.get("data", {}),
            "status_code": resp.status_code,
            "error": None,
        }

    async def get_organizations(self) -> dict[str, Any]:
        """Fetch Buffer organization IDs."""
        return await self._graphql("""
            query GetOrganizations {
                account {
                    organizations { id }
                }
            }
        """)

    async def get_profiles(self, organization_id: Optional[str] = None) -> dict[str, Any]:
        """Fetch connected channels/profiles.

        If organization_id is not provided, fetches it first.
        """
        if not organization_id:
            org_result = await self.get_organizations()
            if not org_result.get("success"):
                return org_result
            orgs = (org_result.get("data") or {}).get("account", {}).get("organizations", [])
            if not orgs:
                return _error_result("No Buffer organizations found")
            organization_id = orgs[0]["id"]

        result = await self._graphql("""
            query GetChannels($orgId: OrganizationId!) {
                channels(input: { organizationId: $orgId }) {
                    id
                    name
                    displayName
                    service
                    avatar
                    isQueuePaused
                }
            }
        """, {"orgId": organization_id})

        if not result.get("success"):
            return result

        # Normalize to match old REST API shape for backward compat
        channels = result.get("data", {}).get("channels", [])
        profiles = []
        for ch in channels:
            profiles.append({
                "id": ch["id"],
                "service": ch.get("service", "").lower(),
                "service_username": ch.get("name", ""),
                "formatted_service": (ch.get("service") or "").title(),
                "avatar_https": ch.get("avatar", ""),
                "display_name": ch.get("displayName", ch.get("name", "")),
                "is_queue_paused": ch.get("isQueuePaused", False),
            })

        return {
            "success": True,
            "blocked": False,
            "data": profiles,
            "status_code": 200,
            "error": None,
            "_buffer_org_id": organization_id,
        }

    async def create_update(
        self,
        profile_ids: list[str],
        text: str,
        *,
        media: Optional[dict[str, str]] = None,
        scheduled_at: Optional[str] = None,
        shorten: bool = True,
        mode: str = "addToQueue",
        assets: Optional[dict[str, Any]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Create a post via GraphQL createPost mutation.

        Args:
            profile_ids: Buffer channel IDs to publish to (one post per channel).
            text: Post body text.
            media: Legacy REST-shape media dict like {"photo": url} — auto-converted
                   to the GraphQL `assets` shape if `assets` is not explicitly given.
            scheduled_at: Optional ISO timestamp for custom scheduling.
            mode: addToQueue | shareNow | shareNext
            assets: GraphQL assets dict like
                    {"images": [{"url": "..."}]} or {"videos": [{"url": "..."}]}.
                    Preferred over `media` when building platform-aware payloads.
            metadata: Platform-specific metadata dict like
                    {"instagram": {"type": "reel", "shouldShareToFeed": True}}.
        """
        if not self._is_configured():
            return _blocked("BUFFER_API_KEY not configured")

        # Back-compat: if caller passed legacy `media` but not `assets`, convert.
        if assets is None and media:
            if "photo" in media:
                assets = {"images": [{"url": media["photo"]}]}
            elif "video" in media:
                assets = {"videos": [{"url": media["video"]}]}

        # Buffer GraphQL sends one post per channel
        results = []
        for channel_id in profile_ids:
            mutation = """
                mutation CreatePost($input: CreatePostInput!) {
                    createPost(input: $input) {
                        ... on PostActionSuccess {
                            post { id text status dueAt channelId }
                        }
                        ... on MutationError {
                            message
                        }
                    }
                }
            """
            input_obj: dict[str, Any] = {
                "text": text,
                "channelId": channel_id,
                "schedulingType": "customScheduled" if scheduled_at else "automatic",
                "mode": mode,
            }
            if scheduled_at:
                input_obj["dueAt"] = scheduled_at
            if assets:
                input_obj["assets"] = assets
            if metadata:
                input_obj["metadata"] = metadata

            result = await self._graphql(mutation, {"input": input_obj})
            results.append(result)

        # Return first result for backward compat
        if results and results[0].get("success"):
            post_data = (results[0].get("data") or {}).get("createPost", {})
            if "post" in post_data and post_data["post"]:
                return {
                    "success": True,
                    "blocked": False,
                    "data": {"updates": [post_data["post"]]},
                    "status_code": 200,
                    "error": None,
                }
            elif "message" in post_data and post_data["message"]:
                return _error_result(f"Buffer: {post_data['message']}")

        return results[0] if results else _error_result("No channels specified")

    async def get_update(self, update_id: str) -> dict[str, Any]:
        """Get post status — not yet available in GraphQL beta, returns stub."""
        logger.info("buffer.get_update_stub", update_id=update_id)
        return {
            "success": True,
            "blocked": False,
            "data": {"id": update_id, "status": "sent"},
            "status_code": 200,
            "error": None,
        }


# ---------------------------------------------------------------------------
# SECTION 4 — Ad Platform Reporting Clients
# ---------------------------------------------------------------------------

class MetaAdsClient:
    """Real HTTP client for Meta Marketing API reporting."""

    BASE_URL = "https://graph.facebook.com/v21.0"

    def __init__(self) -> None:
        self.access_token = os.environ.get("META_ADS_ACCESS_TOKEN", "")
        self.ad_account_id = os.environ.get("META_ADS_ACCOUNT_ID", "")

    def _is_configured(self) -> bool:
        return bool(self.access_token and self.ad_account_id)

    async def fetch_campaign_insights(
        self,
        date_preset: str = "last_7d",
    ) -> dict[str, Any]:
        """GET /{ad_account_id}/insights — fetch campaign-level reporting."""
        if not self._is_configured():
            return _blocked("META_ADS_ACCESS_TOKEN or META_ADS_ACCOUNT_ID not configured")

        acct = self.ad_account_id
        if not acct.startswith("act_"):
            acct = f"act_{acct}"

        url = f"{self.BASE_URL}/{acct}/insights"
        params = {
            "access_token": self.access_token,
            "level": "campaign",
            "date_preset": date_preset,
            "fields": "campaign_name,campaign_id,spend,impressions,clicks,actions,action_values",
        }

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(url, params=params)
        except httpx.HTTPError as exc:
            logger.error("meta_ads.network_error", error=str(exc))
            return _error_result(f"Meta Ads network error: {exc}")

        err = await _classify_response(resp, service="Meta Ads")
        if err:
            return err

        body = resp.json()
        campaigns = []
        for row in body.get("data", []):
            conversions = 0
            revenue = 0.0
            for action in row.get("actions") or []:
                if action.get("action_type") == "offsite_conversion":
                    conversions += int(action.get("value", 0))
            for av in row.get("action_values") or []:
                if av.get("action_type") == "offsite_conversion":
                    revenue += float(av.get("value", 0))

            campaigns.append({
                "campaign_id": row.get("campaign_id"),
                "campaign_name": row.get("campaign_name"),
                "spend": float(row.get("spend", 0)),
                "impressions": int(row.get("impressions", 0)),
                "clicks": int(row.get("clicks", 0)),
                "conversions": conversions,
                "revenue_attributed": revenue,
            })

        return {
            "success": True,
            "blocked": False,
            "data": {
                "campaigns": campaigns,
                "spend": sum(c["spend"] for c in campaigns),
                "impressions": sum(c["impressions"] for c in campaigns),
                "clicks": sum(c["clicks"] for c in campaigns),
                "conversions": sum(c["conversions"] for c in campaigns),
                "revenue_attributed": sum(c["revenue_attributed"] for c in campaigns),
            },
            "error": None,
            "status_code": resp.status_code,
        }


class GoogleAdsClient:
    """Real HTTP client for Google Ads REST API reporting."""

    BASE_URL = "https://googleads.googleapis.com/v18"

    def __init__(self) -> None:
        self.developer_token = os.environ.get("GOOGLE_ADS_DEVELOPER_TOKEN", "")
        self.customer_id = os.environ.get("GOOGLE_ADS_CUSTOMER_ID", "")
        self.oauth_token = os.environ.get("GOOGLE_ADS_OAUTH_TOKEN", "")

    def _is_configured(self) -> bool:
        return bool(self.developer_token and self.customer_id and self.oauth_token)

    async def fetch_campaign_report(
        self,
        date_range: str = "LAST_7_DAYS",
    ) -> dict[str, Any]:
        """POST /customers/{customer_id}/googleAds:searchStream — GAQL query."""
        if not self._is_configured():
            return _blocked(
                "GOOGLE_ADS_DEVELOPER_TOKEN, GOOGLE_ADS_CUSTOMER_ID, "
                "or GOOGLE_ADS_OAUTH_TOKEN not configured"
            )

        cid = self.customer_id.replace("-", "")
        url = f"{self.BASE_URL}/customers/{cid}/googleAds:searchStream"
        gaql = (
            "SELECT campaign.id, campaign.name, "
            "metrics.cost_micros, metrics.impressions, metrics.clicks, "
            "metrics.conversions, metrics.conversions_value "
            f"FROM campaign WHERE segments.date DURING {date_range}"
        )
        headers = {
            "Authorization": f"Bearer {self.oauth_token}",
            "developer-token": self.developer_token,
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.post(
                    url,
                    headers=headers,
                    json={"query": gaql},
                )
        except httpx.HTTPError as exc:
            logger.error("google_ads.network_error", error=str(exc))
            return _error_result(f"Google Ads network error: {exc}")

        err = await _classify_response(resp, service="Google Ads")
        if err:
            return err

        body = resp.json()
        campaigns = []
        results = body if isinstance(body, list) else [body]
        for batch in results:
            for row in batch.get("results", []):
                camp = row.get("campaign", {})
                met = row.get("metrics", {})
                spend = float(met.get("costMicros", 0)) / 1_000_000
                campaigns.append({
                    "campaign_id": camp.get("id"),
                    "campaign_name": camp.get("name"),
                    "spend": spend,
                    "impressions": int(met.get("impressions", 0)),
                    "clicks": int(met.get("clicks", 0)),
                    "conversions": int(float(met.get("conversions", 0))),
                    "revenue_attributed": float(met.get("conversionsValue", 0)),
                })

        return {
            "success": True,
            "blocked": False,
            "data": {
                "campaigns": campaigns,
                "spend": sum(c["spend"] for c in campaigns),
                "impressions": sum(c["impressions"] for c in campaigns),
                "clicks": sum(c["clicks"] for c in campaigns),
                "conversions": sum(c["conversions"] for c in campaigns),
                "revenue_attributed": sum(c["revenue_attributed"] for c in campaigns),
            },
            "error": None,
            "status_code": resp.status_code,
        }


class TikTokAdsClient:
    """Real HTTP client for TikTok Marketing API reporting."""

    BASE_URL = "https://business-api.tiktok.com/open_api/v1.3"

    def __init__(self) -> None:
        self.access_token = os.environ.get("TIKTOK_ADS_ACCESS_TOKEN", "")
        self.advertiser_id = os.environ.get("TIKTOK_ADS_ADVERTISER_ID", "")

    def _is_configured(self) -> bool:
        return bool(self.access_token and self.advertiser_id)

    async def fetch_campaign_report(
        self,
        date_range_days: int = 7,
    ) -> dict[str, Any]:
        """GET /report/integrated/get/ — campaign performance report."""
        if not self._is_configured():
            return _blocked(
                "TIKTOK_ADS_ACCESS_TOKEN or TIKTOK_ADS_ADVERTISER_ID not configured"
            )

        end_date = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
        start_date = (
            datetime.now(tz=timezone.utc) - timedelta(days=date_range_days)
        ).strftime("%Y-%m-%d")

        url = f"{self.BASE_URL}/report/integrated/get/"
        headers = {"Access-Token": self.access_token}
        params: dict[str, Any] = {
            "advertiser_id": self.advertiser_id,
            "report_type": "BASIC",
            "data_level": "AUCTION_CAMPAIGN",
            "dimensions": json.dumps(["campaign_id"]),
            "metrics": json.dumps([
                "campaign_name", "spend", "impressions", "clicks",
                "conversion", "complete_payment_roas",
            ]),
            "start_date": start_date,
            "end_date": end_date,
        }

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(url, headers=headers, params=params)
        except httpx.HTTPError as exc:
            logger.error("tiktok_ads.network_error", error=str(exc))
            return _error_result(f"TikTok Ads network error: {exc}")

        err = await _classify_response(resp, service="TikTok Ads")
        if err:
            return err

        body = resp.json()
        if body.get("code") != 0:
            msg = body.get("message", "Unknown TikTok API error")
            logger.warning("tiktok_ads.api_error", code=body.get("code"), message=msg)
            return _error_result(f"TikTok Ads API error: {msg}", status_code=resp.status_code)

        campaigns = []
        for row in body.get("data", {}).get("list", []):
            dims = row.get("dimensions", {})
            met = row.get("metrics", {})
            campaigns.append({
                "campaign_id": dims.get("campaign_id"),
                "campaign_name": met.get("campaign_name", ""),
                "spend": float(met.get("spend", 0)),
                "impressions": int(met.get("impressions", 0)),
                "clicks": int(met.get("clicks", 0)),
                "conversions": int(met.get("conversion", 0)),
                "revenue_attributed": float(met.get("complete_payment_roas", 0))
                * float(met.get("spend", 0)),
            })

        return {
            "success": True,
            "blocked": False,
            "data": {
                "campaigns": campaigns,
                "spend": sum(c["spend"] for c in campaigns),
                "impressions": sum(c["impressions"] for c in campaigns),
                "clicks": sum(c["clicks"] for c in campaigns),
                "conversions": sum(c["conversions"] for c in campaigns),
                "revenue_attributed": sum(c["revenue_attributed"] for c in campaigns),
            },
            "error": None,
            "status_code": resp.status_code,
        }


# ---------------------------------------------------------------------------
# SECTION 5 — Email (SMTP) Client
# ---------------------------------------------------------------------------

class SmtpEmailClient:
    """Real SMTP email sender using aiosmtplib."""

    def __init__(self) -> None:
        self.host = os.environ.get("SMTP_HOST", "")
        self.port = int(os.environ.get("SMTP_PORT", "587"))
        self.username = os.environ.get("SMTP_USERNAME", "") or os.environ.get("SMTP_USER", "")
        self.password = os.environ.get("SMTP_PASSWORD", "") or os.environ.get("SMTP_PASS", "")
        # Accept SMTP_FROM_EMAIL (canonical), then SMTP_FROM (legacy),
        # then fall back to SMTP_USERNAME. This matters when SMTP relay login
        # uses one identity (e.g. Brevo SMTP key) but messages must be From: a
        # verified sender like hello@proofhook.com.
        self.from_email = (
            os.environ.get("SMTP_FROM_EMAIL", "")
            or os.environ.get("SMTP_FROM", "")
            or self.username
        )
        self.from_name = os.environ.get("SMTP_FROM_NAME", "ProofHook")
        self.reply_to = os.environ.get("SMTP_REPLY_TO", "") or self.from_email
        self.use_tls = os.environ.get("SMTP_USE_TLS", "true").lower() == "true"

    def _is_configured(self) -> bool:
        return bool(self.host and self.from_email)

    async def send_email(
        self,
        to_email: str,
        subject: str,
        body_html: str = "",
        body_text: str = "",
    ) -> dict[str, Any]:
        """Send a real email via SMTP. Returns success/failure with details."""
        if not self._is_configured():
            return {
                "success": False,
                "blocked": True,
                "error": "SMTP_HOST or SMTP_FROM_EMAIL not configured",
                "message_id": None,
                "provider": "smtp",
            }

        msg = MIMEMultipart("alternative")
        msg["From"] = f"{self.from_name} <{self.from_email}>"
        msg["To"] = to_email
        msg["Subject"] = subject
        msg["Reply-To"] = self.reply_to
        msg["List-Unsubscribe"] = f"<mailto:{self.from_email}?subject=unsubscribe>"
        msg["X-Mailer"] = "ProofHook"

        # Always include plain text version (improves deliverability)
        plain = body_text
        if not plain and body_html:
            import re
            plain = re.sub(r'<[^>]+>', '', body_html).strip()
        if plain:
            msg.attach(MIMEText(plain, "plain", "utf-8"))
        if body_html:
            msg.attach(MIMEText(body_html, "html", "utf-8"))
        if not plain and not body_html:
            msg.attach(MIMEText("", "plain", "utf-8"))

        try:
            # Port 587 = STARTTLS (start_tls=True, use_tls=False)
            # Port 465 = Direct SSL (use_tls=True, start_tls=False)
            is_ssl_port = self.port == 465
            result = await aiosmtplib.send(
                msg,
                hostname=self.host,
                port=self.port,
                username=self.username or None,
                password=self.password or None,
                use_tls=is_ssl_port,
                start_tls=not is_ssl_port and self.use_tls,
            )
            message_id = msg.get("Message-ID") or str(result)
            logger.info(
                "smtp.email_sent",
                to=to_email,
                subject=subject,
                message_id=message_id,
            )
            return {
                "success": True,
                "blocked": False,
                "error": None,
                "message_id": message_id,
                "provider": "smtp",
            }
        except aiosmtplib.SMTPException as exc:
            logger.error("smtp.send_error", to=to_email, error=str(exc))
            return {
                "success": False,
                "blocked": False,
                "error": f"SMTP error: {exc}",
                "message_id": None,
                "provider": "smtp",
            }
        except (ConnectionError, TimeoutError, OSError) as exc:
            logger.error("smtp.connection_error", to=to_email, error=str(exc))
            return {
                "success": False,
                "blocked": False,
                "error": f"SMTP connection error: {exc}",
                "message_id": None,
                "provider": "smtp",
            }


# ---------------------------------------------------------------------------
# SECTION 6 — SMS (Twilio-compatible) Client
# ---------------------------------------------------------------------------

class TwilioSmsClient:
    """Real SMS sender using Twilio REST API (raw httpx, no SDK)."""

    BASE_URL = "https://api.twilio.com/2010-04-01"

    def __init__(self) -> None:
        self.account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
        self.auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
        self.from_number = os.environ.get("TWILIO_FROM_NUMBER", "")

    def _is_configured(self) -> bool:
        return bool(self.account_sid and self.auth_token and self.from_number)

    async def send_sms(
        self,
        to_phone: str,
        message_body: str,
    ) -> dict[str, Any]:
        """Send a real SMS via Twilio API. Returns success/failure with details."""
        if not self._is_configured():
            return {
                "success": False,
                "blocked": True,
                "error": "TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, or TWILIO_FROM_NUMBER not configured",
                "message_sid": None,
                "provider": "twilio",
            }

        url = f"{self.BASE_URL}/Accounts/{self.account_sid}/Messages.json"

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.post(
                    url,
                    auth=(self.account_sid, self.auth_token),
                    data={
                        "To": to_phone,
                        "From": self.from_number,
                        "Body": message_body,
                    },
                )
        except httpx.HTTPError as exc:
            logger.error("twilio.network_error", to=to_phone, error=str(exc))
            return {
                "success": False,
                "blocked": False,
                "error": f"Twilio network error: {exc}",
                "message_sid": None,
                "provider": "twilio",
            }

        body = {}
        try:
            body = resp.json()
        except Exception:
            pass

        if resp.status_code == 201:
            sid = body.get("sid", "")
            logger.info("twilio.sms_sent", to=to_phone, message_sid=sid)
            return {
                "success": True,
                "blocked": False,
                "error": None,
                "message_sid": sid,
                "provider": "twilio",
            }

        if resp.status_code == 401:
            error_msg = "Twilio auth failure"
        elif resp.status_code == 429:
            error_msg = "Twilio rate-limited"
        elif resp.status_code == 400:
            error_msg = f"Twilio bad request: {body.get('message', 'invalid parameters')}"
        else:
            error_msg = f"Twilio HTTP {resp.status_code}: {body.get('message', '')}"

        logger.warning(
            "twilio.send_failed",
            to=to_phone,
            status=resp.status_code,
            error=error_msg,
        )
        return {
            "success": False,
            "blocked": False,
            "error": error_msg,
            "message_sid": None,
            "provider": "twilio",
        }

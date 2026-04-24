"""AI provider clients for the tiered content routing stack.

Text:  Claude (hero) / Gemini Flash (standard) / DeepSeek (bulk)
Image: GPT Image 1.5 (hero) / Imagen 4 Fast (bulk) / Flux 2 Pro (variety)
Video: Runway Gen-4 (hero) / Kling AI (bulk)
Avatar: HeyGen (all tiers) / D-ID (budget fallback)
Voice: ElevenLabs (hero) / Fish Audio (standard) / Voxtral (bulk)
Music: Suno (all tiers)

Every client: real httpx calls, blocked result on missing key, structured response.
"""
from __future__ import annotations

import asyncio
import os
import time
from typing import Any

import httpx
import structlog

logger = structlog.get_logger()

_TIMEOUT = httpx.Timeout(60.0, connect=10.0)
_POLL_TIMEOUT = httpx.Timeout(300.0, connect=10.0)


def _webhook_url(provider_key: str, webhook_url: str | None = None) -> str | None:
    """Build the webhook callback URL for a provider.

    If an explicit *webhook_url* is passed, use it as-is.
    Otherwise construct from WEBHOOK_BASE_URL env var:
        {WEBHOOK_BASE_URL}/webhooks/media/{provider_key}

    Returns None when no URL can be determined (caller should set
    requires_polling=True).
    """
    if webhook_url:
        return webhook_url
    base = os.environ.get("WEBHOOK_BASE_URL", "")
    if base:
        return f"{base.rstrip('/')}/webhooks/media/{provider_key}"
    return None


def _blocked(error: str) -> dict[str, Any]:
    return {"success": False, "blocked": True, "error": error, "data": None, "status_code": 0}


def _ok(data: Any, status_code: int = 200) -> dict[str, Any]:
    return {"success": True, "blocked": False, "error": None, "data": data, "status_code": status_code}


def _fail(error: str, status_code: int = 0, data: Any = None) -> dict[str, Any]:
    return {"success": False, "blocked": False, "error": error, "data": data, "status_code": status_code}


async def _handle_response(resp: httpx.Response, service: str) -> dict[str, Any] | None:
    if 200 <= resp.status_code < 300:
        return None
    try:
        body = resp.json()
    except Exception:
        body = resp.text
    msg = f"{service} HTTP {resp.status_code}"
    if resp.status_code == 401:
        msg = f"{service} auth failure"
    elif resp.status_code == 429:
        msg = f"{service} rate-limited"
    elif resp.status_code >= 500:
        msg = f"{service} server error ({resp.status_code})"
    logger.warning("ai_client.http_error", service=service, status=resp.status_code)
    return _fail(msg, resp.status_code, body)


async def _request_with_retry(
    client_fn,
    service: str,
    max_retries: int = 3,
    base_delay: float = 2.0,
) -> dict[str, Any]:
    """Execute an async HTTP request with exponential backoff on 429/5xx."""
    for attempt in range(max_retries + 1):
        try:
            result = await client_fn()
            if isinstance(result, dict) and result.get("status_code") in (429, 500, 502, 503):
                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt)
                    logger.warning("ai_client.retry service=%s attempt=%d delay=%.1fs status=%s", service, attempt + 1, delay, result.get("status_code"))
                    await asyncio.sleep(delay)
                    continue
            return result
        except Exception as e:
            if attempt < max_retries:
                delay = base_delay * (2 ** attempt)
                logger.warning("ai_client.retry_on_exception service=%s attempt=%d delay=%.1fs error=%s", service, attempt + 1, delay, str(e)[:100])
                await asyncio.sleep(delay)
            else:
                return _fail(f"{service} failed after {max_retries + 1} attempts: {e}")
    return _fail(f"{service} exhausted retries")


# ── TEXT: Claude (Hero) ───────────────────────────────────────────

class ClaudeContentClient:
    """Claude content generation client — hero tier text generation."""

    def __init__(self, api_key: str | None = None, model: str = "claude-sonnet-4-20250514"):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.model = model

    def _is_configured(self) -> bool:
        return bool(self.api_key)

    async def generate(self, prompt: str, max_tokens: int = 2048, system: str = "") -> dict[str, Any]:
        if not self._is_configured():
            return _blocked("ANTHROPIC_API_KEY not configured")

        async def _call() -> dict[str, Any]:
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=self.api_key)
            t0 = time.monotonic()
            kwargs: dict[str, Any] = {
                "model": self.model,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            }
            if system:
                kwargs["system"] = system
            response = await client.messages.create(**kwargs)
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            text = response.content[0].text if response.content else ""
            return _ok({
                "text": text,
                "model": self.model,
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "elapsed_ms": elapsed_ms,
            })

        return await _request_with_retry(_call, "Claude")


# ── TEXT: Gemini Flash ────────────────────────────────────────────

class GeminiFlashClient:
    BASE_URL = "https://generativelanguage.googleapis.com"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("GOOGLE_AI_API_KEY", "")

    def _is_configured(self) -> bool:
        return bool(self.api_key)

    async def generate(self, prompt: str, max_tokens: int = 1024, system: str = "") -> dict[str, Any]:
        if not self._is_configured():
            return _blocked("GOOGLE_AI_API_KEY not configured")

        async def _call() -> dict[str, Any]:
            payload: dict[str, Any] = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"maxOutputTokens": max_tokens}}
            if system:
                payload["systemInstruction"] = {"parts": [{"text": system}]}
            try:
                async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
                    resp = await c.post(f"{self.BASE_URL}/v1beta/models/gemini-2.5-flash:generateContent?key={self.api_key}", json=payload)
            except httpx.HTTPError as e:
                return _fail(f"Gemini Flash network error: {e}")
            err = await _handle_response(resp, "Gemini Flash")
            if err:
                return err
            body = resp.json()
            text = body.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            return _ok({"text": text, "model": "gemini-2.5-flash"}, resp.status_code)

        return await _request_with_retry(_call, "Gemini Flash")


# ── TEXT: DeepSeek ────────────────────────────────────────────────

class DeepSeekClient:
    BASE_URL = "https://api.deepseek.com"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")

    def _is_configured(self) -> bool:
        return bool(self.api_key)

    async def generate(self, prompt: str, max_tokens: int = 1024) -> dict[str, Any]:
        if not self._is_configured():
            return _blocked("DEEPSEEK_API_KEY not configured")

        async def _call() -> dict[str, Any]:
            payload = {"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens}
            try:
                async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
                    resp = await c.post(f"{self.BASE_URL}/v1/chat/completions", json=payload, headers={"Authorization": f"Bearer {self.api_key}"})
            except httpx.HTTPError as e:
                return _fail(f"DeepSeek network error: {e}")
            err = await _handle_response(resp, "DeepSeek")
            if err:
                return err
            body = resp.json()
            text = body.get("choices", [{}])[0].get("message", {}).get("content", "")
            return _ok({"text": text, "model": "deepseek-chat"}, resp.status_code)

        return await _request_with_retry(_call, "DeepSeek")


# ── IMAGE: GPT Image 1.5 ─────────────────────────────────────────

class GPTImageClient:
    BASE_URL = "https://api.openai.com"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")

    def _is_configured(self) -> bool:
        return bool(self.api_key)

    async def generate(self, prompt: str, size: str = "1024x1024", quality: str = "high") -> dict[str, Any]:
        if not self._is_configured():
            return _blocked("OPENAI_API_KEY not configured")

        async def _call() -> dict[str, Any]:
            payload = {"model": "gpt-image-1", "prompt": prompt, "n": 1, "size": size, "quality": quality}
            try:
                async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
                    resp = await c.post(f"{self.BASE_URL}/v1/images/generations", json=payload, headers={"Authorization": f"Bearer {self.api_key}"})
            except httpx.HTTPError as e:
                return _fail(f"GPT Image network error: {e}")
            err = await _handle_response(resp, "GPT Image")
            if err:
                return err
            body = resp.json()
            url = body.get("data", [{}])[0].get("url", "")
            return _ok({"image_url": url, "model": "gpt-image-1"}, resp.status_code)

        return await _request_with_retry(_call, "GPT Image")

    async def submit_async(self, prompt: str, webhook_url: str | None = None, **kwargs) -> dict[str, Any]:
        """Submit a GPT Image generation and return immediately.

        OpenAI image generation is synchronous — the image URL is returned
        in the HTTP response. No webhook or polling supported.
        """
        if not self._is_configured():
            return _blocked("OPENAI_API_KEY not configured")

        size = kwargs.get("size", "1024x1024")
        quality = kwargs.get("quality", "high")
        payload = {"model": "gpt-image-1", "prompt": prompt, "n": 1, "size": size, "quality": quality}
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
                resp = await c.post(
                    f"{self.BASE_URL}/v1/images/generations",
                    json=payload,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
        except httpx.HTTPError as e:
            return _fail(f"GPT Image network error: {e}")

        err = await _handle_response(resp, "GPT Image")
        if err:
            return err

        body = resp.json()
        url = body.get("data", [{}])[0].get("url", "")
        import hashlib as _hl
        job_id = f"gpt_{_hl.md5(prompt[:50].encode()).hexdigest()[:12]}"
        return _ok({
            "provider_job_id": job_id,
            "provider": "openai_image",
            "requires_polling": False,
            "image_url": url,
        })


# ── IMAGE: Imagen 4 Fast ─────────────────────────────────────────

class Imagen4Client:
    BASE_URL = "https://generativelanguage.googleapis.com"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("GOOGLE_AI_API_KEY", "")

    def _is_configured(self) -> bool:
        return bool(self.api_key)

    async def generate(self, prompt: str) -> dict[str, Any]:
        if not self._is_configured():
            return _blocked("GOOGLE_AI_API_KEY not configured")
        payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseModalities": ["image"]}}
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
                resp = await c.post(f"{self.BASE_URL}/v1beta/models/imagen-4-fast:generateContent?key={self.api_key}", json=payload)
        except httpx.HTTPError as e:
            return _fail(f"Imagen 4 network error: {e}")
        err = await _handle_response(resp, "Imagen 4")
        if err:
            return err
        body = resp.json()
        b64 = body.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("inlineData", {}).get("data", "")
        return _ok({"image_b64": b64, "model": "imagen-4-fast"}, resp.status_code)

    async def submit_async(self, prompt: str, webhook_url: str | None = None, **kwargs) -> dict[str, Any]:
        """Submit an Imagen 4 generation and return immediately.

        Google Imagen via Generative Language API is synchronous — the
        base64 image data is returned in the HTTP response.
        No webhook or polling supported.
        """
        if not self._is_configured():
            return _blocked("GOOGLE_AI_API_KEY not configured")

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["image"]},
        }
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
                resp = await c.post(
                    f"{self.BASE_URL}/v1beta/models/imagen-4-fast:generateContent?key={self.api_key}",
                    json=payload,
                )
        except httpx.HTTPError as e:
            return _fail(f"Imagen 4 network error: {e}")

        err = await _handle_response(resp, "Imagen 4")
        if err:
            return err

        body = resp.json()
        b64 = body.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("inlineData", {}).get("data", "")
        import hashlib as _hl
        job_id = f"img4_{_hl.md5(prompt[:50].encode()).hexdigest()[:12]}"
        return _ok({
            "provider_job_id": job_id,
            "provider": "imagen4",
            "requires_polling": False,
            "image_b64": b64,
        })


# ── IMAGE: Flux 2 Pro ─────────────────────────────────────────────

class FluxClient:
    BASE_URL = "https://fal.run"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("FAL_API_KEY", "")

    def _is_configured(self) -> bool:
        return bool(self.api_key)

    async def generate(self, prompt: str, size: str = "square_hd") -> dict[str, Any]:
        if not self._is_configured():
            return _blocked("FAL_API_KEY not configured")
        payload = {"prompt": prompt, "image_size": size, "num_images": 1}
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
                resp = await c.post(f"{self.BASE_URL}/fal-ai/flux-pro/v1.1", json=payload, headers={"Authorization": f"Key {self.api_key}"})
        except httpx.HTTPError as e:
            return _fail(f"Flux network error: {e}")
        err = await _handle_response(resp, "Flux")
        if err:
            return err
        body = resp.json()
        url = body.get("images", [{}])[0].get("url", "")
        return _ok({"image_url": url, "model": "flux-pro-v1.1"}, resp.status_code)

    async def submit_async(self, prompt: str, webhook_url: str | None = None, **kwargs) -> dict[str, Any]:
        """Submit a Flux image generation job via fal.ai and return immediately.

        Uses the fal.ai queue endpoint with webhook parameter for push
        notification on completion.
        """
        if not self._is_configured():
            return _blocked("FAL_API_KEY not configured")

        size = kwargs.get("size", "square_hd")
        cb_url = _webhook_url("flux", webhook_url)

        payload: dict[str, Any] = {"prompt": prompt, "image_size": size, "num_images": 1}
        if cb_url:
            payload["webhook_url"] = cb_url

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
                resp = await c.post(
                    f"{self.BASE_URL}/fal-ai/flux-pro/v1.1",
                    json=payload,
                    headers={"Authorization": f"Key {self.api_key}"},
                )
        except httpx.HTTPError as e:
            return _fail(f"Flux network error: {e}")

        err = await _handle_response(resp, "Flux")
        if err:
            return err

        body = resp.json()
        # fal.ai sync endpoint returns the result directly; for true async
        # we could use /queue/submit. If the image is already in the response,
        # treat as completed.
        images = body.get("images", [])
        if images:
            import hashlib as _hl
            job_id = f"flux_{_hl.md5(prompt[:50].encode()).hexdigest()[:12]}"
            return _ok({
                "provider_job_id": job_id,
                "provider": "flux",
                "requires_polling": False,
                "image_url": images[0].get("url", ""),
            })
        request_id = body.get("request_id", "")
        return _ok({
            "provider_job_id": request_id,
            "provider": "flux",
            "requires_polling": cb_url is None,
        })

    async def poll_status(self, job_id: str) -> dict[str, Any]:
        """Check if an async Flux (fal.ai) job has completed."""
        if not self._is_configured():
            return _blocked("FAL_API_KEY not configured")
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
                resp = await c.get(
                    f"{self.BASE_URL}/fal-ai/flux-pro/v1.1/requests/{job_id}/status",
                    headers={"Authorization": f"Key {self.api_key}"},
                )
            if resp.status_code != 200:
                return _fail(f"Flux poll HTTP {resp.status_code}")
            data = resp.json()
            status = data.get("status", "IN_QUEUE")
            if status == "COMPLETED":
                response_url = data.get("response_url", "")
                output_url = ""
                if response_url:
                    async with httpx.AsyncClient(timeout=_TIMEOUT) as c2:
                        result_resp = await c2.get(response_url, headers={"Authorization": f"Key {self.api_key}"})
                    if result_resp.status_code == 200:
                        output_url = result_resp.json().get("images", [{}])[0].get("url", "")
                return _ok({"status": "completed", "output_url": output_url, "error": None})
            if status == "FAILED":
                return _ok({"status": "failed", "output_url": None, "error": data.get("error", "unknown")})
            return _ok({"status": "processing", "output_url": None, "error": None})
        except httpx.HTTPError as e:
            return _fail(f"Flux network error: {e}")


# ── VIDEO: Kling AI ───────────────────────────────────────────────

class KlingClient:
    BASE_URL = "https://fal.run"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("FAL_API_KEY", "")

    def _is_configured(self) -> bool:
        return bool(self.api_key)

    async def generate(self, prompt: str, duration_sec: int = 5, aspect_ratio: str = "9:16") -> dict[str, Any]:
        if not self._is_configured():
            return _blocked("FAL_API_KEY not configured")
        payload = {"prompt": prompt, "duration": duration_sec, "aspect_ratio": aspect_ratio}
        try:
            async with httpx.AsyncClient(timeout=_POLL_TIMEOUT) as c:
                resp = await c.post(f"{self.BASE_URL}/fal-ai/kling-video/v2/master", json=payload, headers={"Authorization": f"Key {self.api_key}"})
        except httpx.HTTPError as e:
            return _fail(f"Kling network error: {e}")
        err = await _handle_response(resp, "Kling")
        if err:
            return err
        body = resp.json()
        url = body.get("video", {}).get("url", "")
        return _ok({"video_url": url, "model": "kling-v2"}, resp.status_code)

    async def submit_async(self, prompt: str, webhook_url: str | None = None, **kwargs) -> dict[str, Any]:
        """Submit a Kling video generation job via fal.ai queue and return immediately.

        fal.ai exposes a queue API at /fal-ai/{model}/queue/submit that accepts
        a webhook_url parameter for push-based notification.
        """
        if not self._is_configured():
            return _blocked("FAL_API_KEY not configured")

        duration_sec = kwargs.get("duration_sec", 5)
        aspect_ratio = kwargs.get("aspect_ratio", "9:16")
        cb_url = _webhook_url("kling", webhook_url)

        payload: dict[str, Any] = {
            "prompt": prompt,
            "duration": duration_sec,
            "aspect_ratio": aspect_ratio,
        }
        if cb_url:
            payload["webhook_url"] = cb_url

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
                resp = await c.post(
                    f"{self.BASE_URL}/fal-ai/kling-video/v2/master",
                    json=payload,
                    headers={"Authorization": f"Key {self.api_key}"},
                )
        except httpx.HTTPError as e:
            return _fail(f"Kling network error: {e}")

        err = await _handle_response(resp, "Kling")
        if err:
            return err

        body = resp.json()
        request_id = body.get("request_id", "") or body.get("id", "")
        return _ok({
            "provider_job_id": request_id,
            "provider": "kling",
            "requires_polling": cb_url is None,
        })

    async def poll_status(self, job_id: str) -> dict[str, Any]:
        """Check if an async Kling (fal.ai) job has completed."""
        if not self._is_configured():
            return _blocked("FAL_API_KEY not configured")
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
                resp = await c.get(
                    f"{self.BASE_URL}/fal-ai/kling-video/v2/master/requests/{job_id}/status",
                    headers={"Authorization": f"Key {self.api_key}"},
                )
            if resp.status_code != 200:
                return _fail(f"Kling poll HTTP {resp.status_code}")
            data = resp.json()
            status = data.get("status", "IN_QUEUE")
            if status == "COMPLETED":
                output_url = ""
                response_url = data.get("response_url", "")
                if response_url:
                    # Fetch the actual result
                    async with httpx.AsyncClient(timeout=_TIMEOUT) as c2:
                        result_resp = await c2.get(response_url, headers={"Authorization": f"Key {self.api_key}"})
                    if result_resp.status_code == 200:
                        output_url = result_resp.json().get("video", {}).get("url", "")
                return _ok({"status": "completed", "output_url": output_url, "error": None})
            if status == "FAILED":
                return _ok({"status": "failed", "output_url": None, "error": data.get("error", "unknown")})
            return _ok({"status": "processing", "output_url": None, "error": None})
        except httpx.HTTPError as e:
            return _fail(f"Kling network error: {e}")


# ── VIDEO: Runway Gen-4 ──────────────────────────────────────────

class RunwayClient:
    BASE_URL = "https://api.dev.runwayml.com"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("RUNWAY_API_KEY", "")

    def _is_configured(self) -> bool:
        return bool(self.api_key)

    async def generate(self, prompt: str, duration_sec: int = 5, aspect_ratio: str = "9:16", image_url: str | None = None) -> dict[str, Any]:
        if not self._is_configured():
            return _blocked("RUNWAY_API_KEY not configured")
        payload: dict[str, Any] = {"promptText": prompt, "model": "gen4_turbo", "duration": duration_sec, "ratio": aspect_ratio}
        if image_url:
            payload["promptImage"] = image_url
        headers = {"Authorization": f"Bearer {self.api_key}", "X-Runway-Version": "2024-11-06", "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=_POLL_TIMEOUT) as c:
                resp = await c.post(f"{self.BASE_URL}/v1/image_to_video", json=payload, headers=headers)
                err = await _handle_response(resp, "Runway")
                if err:
                    return err
                task_id = resp.json().get("id")
                if not task_id:
                    return _fail("Runway returned no task ID")
                for _ in range(30):
                    await asyncio.sleep(10)
                    poll = await c.get(f"{self.BASE_URL}/v1/tasks/{task_id}", headers={"Authorization": f"Bearer {self.api_key}"})
                    data = poll.json()
                    if data.get("status") == "SUCCEEDED":
                        return _ok({"video_url": data["output"][0], "model": "gen4_turbo"}, poll.status_code)
                    if data.get("status") == "FAILED":
                        return _fail(f"Runway generation failed: {data}")
                return _fail("Runway generation timed out")
        except httpx.HTTPError as e:
            return _fail(f"Runway network error: {e}")

    async def submit_async(self, prompt: str, webhook_url: str | None = None, **kwargs) -> dict[str, Any]:
        """Submit a Runway Gen-4 video generation task and return immediately.

        Uses POST /v1/image_to_video. Runway tasks are inherently async; the
        webhook is delivered via X-Runway-Webhook header if available.
        """
        if not self._is_configured():
            return _blocked("RUNWAY_API_KEY not configured")

        duration_sec = kwargs.get("duration_sec", 5)
        aspect_ratio = kwargs.get("aspect_ratio", "9:16")
        image_url = kwargs.get("image_url")
        cb_url = _webhook_url("runway", webhook_url)

        payload: dict[str, Any] = {
            "promptText": prompt,
            "model": "gen4_turbo",
            "duration": duration_sec,
            "ratio": aspect_ratio,
        }
        if image_url:
            payload["promptImage"] = image_url

        headers: dict[str, str] = {
            "Authorization": f"Bearer {self.api_key}",
            "X-Runway-Version": "2024-11-06",
            "Content-Type": "application/json",
        }
        if cb_url:
            headers["X-Runway-Webhook"] = cb_url

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
                resp = await c.post(f"{self.BASE_URL}/v1/image_to_video", json=payload, headers=headers)
        except httpx.HTTPError as e:
            return _fail(f"Runway network error: {e}")

        err = await _handle_response(resp, "Runway")
        if err:
            return err

        task_id = resp.json().get("id", "")
        return _ok({
            "provider_job_id": task_id,
            "provider": "runway",
            "requires_polling": cb_url is None,
        })

    async def poll_status(self, job_id: str) -> dict[str, Any]:
        """Check if an async Runway task has completed."""
        if not self._is_configured():
            return _blocked("RUNWAY_API_KEY not configured")
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
                resp = await c.get(
                    f"{self.BASE_URL}/v1/tasks/{job_id}",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
            if resp.status_code != 200:
                return _fail(f"Runway poll HTTP {resp.status_code}")
            data = resp.json()
            status = data.get("status", "RUNNING")
            if status == "SUCCEEDED":
                output_url = data.get("output", [""])[0] if data.get("output") else ""
                return _ok({"status": "completed", "output_url": output_url, "error": None})
            if status == "FAILED":
                return _ok({"status": "failed", "output_url": None, "error": data.get("failure", "unknown")})
            return _ok({"status": "processing", "output_url": None, "error": None})
        except httpx.HTTPError as e:
            return _fail(f"Runway network error: {e}")


# ── VIDEO: Wan 2.2 (Bulk) ────────────────────────────────────────

# ── VIDEO: Higgsfield Cinema Studio (Premium Cinematic) ──────────

class HiggsFieldClient:
    """Higgsfield Cinema Studio — professional cinematic video with camera movements, color grading, multi-character scenes."""
    BASE_URL = "https://api.higgsfield.ai"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("HIGGSFIELD_API_KEY", "")

    def _is_configured(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    async def generate(self, prompt: str, duration_sec: int = 5, aspect_ratio: str = "16:9",
                       camera_movement: str = "auto", quality: str = "high") -> dict[str, Any]:
        """Generate cinematic video with professional camera movements."""
        if not self._is_configured():
            return _blocked("HIGGSFIELD_API_KEY not configured")
        payload = {
            "prompt": prompt,
            "duration": duration_sec,
            "aspect_ratio": aspect_ratio,
            "camera_movement": camera_movement,
            "quality": quality,
        }
        try:
            async with httpx.AsyncClient(timeout=_POLL_TIMEOUT) as c:
                resp = await c.post(f"{self.BASE_URL}/v1/videos/generate", json=payload, headers=self._headers())
            if resp.status_code not in (200, 201):
                return _fail(f"Higgsfield create HTTP {resp.status_code}: {resp.text[:200]}")
            body = resp.json()
            job_id = body.get("id") or body.get("job_id") or ""
            if not job_id:
                return _fail("Higgsfield returned no job ID")

            for _ in range(60):
                await asyncio.sleep(5)
                async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
                    poll = await c.get(f"{self.BASE_URL}/v1/videos/{job_id}", headers=self._headers())
                if poll.status_code == 200:
                    data = poll.json()
                    status = data.get("status", "")
                    if status in ("completed", "succeeded"):
                        video_url = data.get("video_url") or data.get("output", {}).get("video_url", "")
                        return _ok({"video_url": video_url, "model": "higgsfield-cinema-studio", "duration": duration_sec, "job_id": job_id})
                    if status in ("failed", "error"):
                        return _fail(f"Higgsfield generation failed: {data.get('error', '')}")
            return _fail("Higgsfield generation timed out after 300s")
        except httpx.HTTPError as e:
            return _fail(f"Higgsfield network error: {e}")

    async def generate_speech_video(self, script_text: str, character_id: str = "default",
                                     aspect_ratio: str = "9:16", quality: str = "high") -> dict[str, Any]:
        """Generate speech-to-video with character lip sync — cinematic avatar alternative."""
        if not self._is_configured():
            return _blocked("HIGGSFIELD_API_KEY not configured")
        payload = {"text": script_text[:3000], "character_id": character_id, "aspect_ratio": aspect_ratio, "quality": quality}
        try:
            async with httpx.AsyncClient(timeout=_POLL_TIMEOUT) as c:
                resp = await c.post(f"{self.BASE_URL}/v1/videos/speak", json=payload, headers=self._headers())
            if resp.status_code not in (200, 201):
                return _fail(f"Higgsfield speak HTTP {resp.status_code}")
            body = resp.json()
            job_id = body.get("id") or body.get("job_id") or ""
            if not job_id:
                return _fail("Higgsfield returned no job ID")

            for _ in range(60):
                await asyncio.sleep(5)
                async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
                    poll = await c.get(f"{self.BASE_URL}/v1/videos/{job_id}", headers=self._headers())
                if poll.status_code == 200:
                    data = poll.json()
                    if data.get("status") in ("completed", "succeeded"):
                        video_url = data.get("video_url") or data.get("output", {}).get("video_url", "")
                        return _ok({"video_url": video_url, "model": "higgsfield-speak", "job_id": job_id})
                    if data.get("status") in ("failed", "error"):
                        return _fail(f"Higgsfield speak failed: {data.get('error', '')}")
            return _fail("Higgsfield speak timed out")
        except httpx.HTTPError as e:
            return _fail(f"Higgsfield network error: {e}")

    async def submit_async(self, prompt: str, webhook_url: str | None = None, **kwargs) -> dict[str, Any]:
        """Submit a Higgsfield video generation job and return immediately.

        Posts to /v1/videos/generate. Higgsfield does not natively support
        webhooks so requires_polling is always True.
        """
        if not self._is_configured():
            return _blocked("HIGGSFIELD_API_KEY not configured")

        duration_sec = kwargs.get("duration_sec", 5)
        aspect_ratio = kwargs.get("aspect_ratio", "16:9")
        camera_movement = kwargs.get("camera_movement", "auto")
        quality = kwargs.get("quality", "high")

        payload = {
            "prompt": prompt,
            "duration": duration_sec,
            "aspect_ratio": aspect_ratio,
            "camera_movement": camera_movement,
            "quality": quality,
        }
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
                resp = await c.post(f"{self.BASE_URL}/v1/videos/generate", json=payload, headers=self._headers())
        except httpx.HTTPError as e:
            return _fail(f"Higgsfield network error: {e}")

        if resp.status_code not in (200, 201):
            return _fail(f"Higgsfield create HTTP {resp.status_code}: {resp.text[:200]}")

        body = resp.json()
        job_id = body.get("id") or body.get("job_id") or ""
        return _ok({
            "provider_job_id": job_id,
            "provider": "higgsfield",
            "requires_polling": True,
        })

    async def poll_status(self, job_id: str) -> dict[str, Any]:
        """Check if an async Higgsfield job has completed."""
        if not self._is_configured():
            return _blocked("HIGGSFIELD_API_KEY not configured")
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
                resp = await c.get(f"{self.BASE_URL}/v1/videos/{job_id}", headers=self._headers())
            if resp.status_code != 200:
                return _fail(f"Higgsfield poll HTTP {resp.status_code}")
            data = resp.json()
            status = data.get("status", "processing")
            if status in ("completed", "succeeded"):
                video_url = data.get("video_url") or data.get("output", {}).get("video_url", "")
                return _ok({"status": "completed", "output_url": video_url, "error": None})
            if status in ("failed", "error"):
                return _ok({"status": "failed", "output_url": None, "error": data.get("error", "unknown")})
            return _ok({"status": "processing", "output_url": None, "error": None})
        except httpx.HTTPError as e:
            return _fail(f"Higgsfield network error: {e}")

    async def create_character(self, name: str, image_url: str = "") -> dict[str, Any]:
        """Create a persistent character (Soul ID) for consistent appearance across videos."""
        if not self._is_configured():
            return _blocked("HIGGSFIELD_API_KEY not configured")
        payload = {"name": name}
        if image_url:
            payload["image_url"] = image_url
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
                resp = await c.post(f"{self.BASE_URL}/v1/characters", json=payload, headers=self._headers())
            if resp.status_code in (200, 201):
                return _ok(resp.json())
            return _fail(f"Higgsfield create character HTTP {resp.status_code}")
        except httpx.HTTPError as e:
            return _fail(f"Higgsfield network error: {e}")


class WanClient:
    """Wan 2.2 video generation via fal.ai — cheapest option for bulk video."""
    BASE_URL = "https://fal.run/fal-ai/wan/v2.2"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("FAL_API_KEY", "")

    def _is_configured(self) -> bool:
        return bool(self.api_key)

    async def generate(self, prompt: str, duration_sec: int = 5, aspect_ratio: str = "9:16") -> dict[str, Any]:
        if not self._is_configured():
            return _blocked("FAL_API_KEY not configured (Wan uses fal.ai)")
        payload = {"prompt": prompt, "num_frames": duration_sec * 24, "aspect_ratio": aspect_ratio}
        try:
            async with httpx.AsyncClient(timeout=_POLL_TIMEOUT) as c:
                resp = await c.post(self.BASE_URL, json=payload, headers={"Authorization": f"Key {self.api_key}", "Content-Type": "application/json"})
            err = await _handle_response(resp, "Wan")
            if err:
                return err
            body = resp.json()
            video_url = body.get("video", {}).get("url", "") or body.get("url", "")
            return _ok({"video_url": video_url, "model": "wan-2.2"}, resp.status_code)
        except httpx.HTTPError as e:
            return _fail(f"Wan network error: {e}")

    async def submit_async(self, prompt: str, webhook_url: str | None = None, **kwargs) -> dict[str, Any]:
        """Submit a Wan 2.2 video generation job via fal.ai and return immediately."""
        if not self._is_configured():
            return _blocked("FAL_API_KEY not configured (Wan uses fal.ai)")

        duration_sec = kwargs.get("duration_sec", 5)
        aspect_ratio = kwargs.get("aspect_ratio", "9:16")
        cb_url = _webhook_url("wan", webhook_url)

        payload: dict[str, Any] = {"prompt": prompt, "num_frames": duration_sec * 24, "aspect_ratio": aspect_ratio}
        if cb_url:
            payload["webhook_url"] = cb_url

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
                resp = await c.post(
                    self.BASE_URL,
                    json=payload,
                    headers={"Authorization": f"Key {self.api_key}", "Content-Type": "application/json"},
                )
        except httpx.HTTPError as e:
            return _fail(f"Wan network error: {e}")

        err = await _handle_response(resp, "Wan")
        if err:
            return err

        body = resp.json()
        request_id = body.get("request_id", "") or body.get("id", "")
        video_url = body.get("video", {}).get("url", "") or body.get("url", "")
        if video_url:
            import hashlib as _hl
            job_id = f"wan_{_hl.md5(prompt[:50].encode()).hexdigest()[:12]}"
            return _ok({
                "provider_job_id": job_id,
                "provider": "wan",
                "requires_polling": False,
                "video_url": video_url,
            })
        return _ok({
            "provider_job_id": request_id,
            "provider": "wan",
            "requires_polling": cb_url is None,
        })

    async def poll_status(self, job_id: str) -> dict[str, Any]:
        """Check if an async Wan (fal.ai) job has completed."""
        if not self._is_configured():
            return _blocked("FAL_API_KEY not configured")
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
                resp = await c.get(
                    f"https://fal.run/fal-ai/wan/v2.2/requests/{job_id}/status",
                    headers={"Authorization": f"Key {self.api_key}"},
                )
            if resp.status_code != 200:
                return _fail(f"Wan poll HTTP {resp.status_code}")
            data = resp.json()
            status = data.get("status", "IN_QUEUE")
            if status == "COMPLETED":
                output_url = ""
                response_url = data.get("response_url", "")
                if response_url:
                    async with httpx.AsyncClient(timeout=_TIMEOUT) as c2:
                        result_resp = await c2.get(response_url, headers={"Authorization": f"Key {self.api_key}"})
                    if result_resp.status_code == 200:
                        output_url = result_resp.json().get("video", {}).get("url", "")
                return _ok({"status": "completed", "output_url": output_url, "error": None})
            if status == "FAILED":
                return _ok({"status": "failed", "output_url": None, "error": data.get("error", "unknown")})
            return _ok({"status": "processing", "output_url": None, "error": None})
        except httpx.HTTPError as e:
            return _fail(f"Wan network error: {e}")


# ── AVATAR: D-ID ─────────────────────────────────────────────────

class DIDClient:
    BASE_URL = "https://api.d-id.com"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("DID_API_KEY", "")

    def _is_configured(self) -> bool:
        return bool(self.api_key)

    async def generate(self, script: str, source_url: str = "https://d-id-public-bucket.s3.us-west-2.amazonaws.com/alice.jpg") -> dict[str, Any]:
        if not self._is_configured():
            return _blocked("DID_API_KEY not configured")
        payload = {"script": {"type": "text", "input": script}, "source_url": source_url}
        headers = {"Authorization": f"Basic {self.api_key}", "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=_POLL_TIMEOUT) as c:
                resp = await c.post(f"{self.BASE_URL}/talks", json=payload, headers=headers)
                err = await _handle_response(resp, "D-ID")
                if err:
                    return err
                talk_id = resp.json().get("id")
                if not talk_id:
                    return _fail("D-ID returned no talk ID")
                for _ in range(30):
                    await asyncio.sleep(10)
                    poll = await c.get(f"{self.BASE_URL}/talks/{talk_id}", headers=headers)
                    data = poll.json()
                    if data.get("status") == "done":
                        return _ok({"video_url": data.get("result_url", ""), "model": "d-id"}, poll.status_code)
                    if data.get("status") == "error":
                        return _fail(f"D-ID generation failed: {data}")
                return _fail("D-ID generation timed out")
        except httpx.HTTPError as e:
            return _fail(f"D-ID network error: {e}")

    async def submit_async(self, prompt: str, webhook_url: str | None = None, **kwargs) -> dict[str, Any]:
        """Submit a D-ID talks job and return immediately.

        Uses POST /talks with a webhook field so D-ID can notify on completion.
        """
        if not self._is_configured():
            return _blocked("DID_API_KEY not configured")

        source_url = kwargs.get("source_url", "https://d-id-public-bucket.s3.us-west-2.amazonaws.com/alice.jpg")
        cb_url = _webhook_url("did", webhook_url)

        payload: dict[str, Any] = {
            "script": {"type": "text", "input": prompt},
            "source_url": source_url,
        }
        if cb_url:
            payload["webhook"] = cb_url

        headers = {"Authorization": f"Basic {self.api_key}", "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
                resp = await c.post(f"{self.BASE_URL}/talks", json=payload, headers=headers)
        except httpx.HTTPError as e:
            return _fail(f"D-ID network error: {e}")

        err = await _handle_response(resp, "D-ID")
        if err:
            return err

        talk_id = resp.json().get("id", "")
        return _ok({
            "provider_job_id": talk_id,
            "provider": "did",
            "requires_polling": cb_url is None,
        })

    async def poll_status(self, job_id: str) -> dict[str, Any]:
        """Check if an async D-ID job has completed."""
        if not self._is_configured():
            return _blocked("DID_API_KEY not configured")
        headers = {"Authorization": f"Basic {self.api_key}", "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
                resp = await c.get(f"{self.BASE_URL}/talks/{job_id}", headers=headers)
            if resp.status_code != 200:
                return _fail(f"D-ID poll HTTP {resp.status_code}")
            data = resp.json()
            status = data.get("status", "started")
            if status == "done":
                return _ok({"status": "completed", "output_url": data.get("result_url", ""), "error": None})
            if status == "error":
                return _ok({"status": "failed", "output_url": None, "error": data.get("error", {}).get("description", "unknown")})
            return _ok({"status": "processing", "output_url": None, "error": None})
        except httpx.HTTPError as e:
            return _fail(f"D-ID network error: {e}")


# ── VOICE: Fish Audio ─────────────────────────────────────────────

class FishAudioClient:
    BASE_URL = "https://api.fish.audio"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("FISH_AUDIO_API_KEY", "")

    def _is_configured(self) -> bool:
        return bool(self.api_key)

    async def generate(self, text: str, voice_id: str = "default") -> dict[str, Any]:
        if not self._is_configured():
            return _blocked("FISH_AUDIO_API_KEY not configured")
        payload = {"text": text, "reference_id": voice_id, "format": "mp3"}
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
                resp = await c.post(f"{self.BASE_URL}/v1/tts", json=payload, headers={"Authorization": f"Bearer {self.api_key}"})
        except httpx.HTTPError as e:
            return _fail(f"Fish Audio network error: {e}")
        if resp.status_code != 200:
            return _fail(f"Fish Audio HTTP {resp.status_code}", resp.status_code)
        return _ok({"audio_bytes_len": len(resp.content), "model": "fish-audio", "format": "mp3"}, resp.status_code)

    async def submit_async(self, prompt: str, webhook_url: str | None = None, **kwargs) -> dict[str, Any]:
        """Submit a Fish Audio TTS job and return immediately.

        Fish Audio TTS is synchronous — audio bytes come back in the HTTP
        response. No webhook or polling needed.
        """
        if not self._is_configured():
            return _blocked("FISH_AUDIO_API_KEY not configured")

        voice_id = kwargs.get("voice_id", "default")
        payload = {"text": prompt, "reference_id": voice_id, "format": "mp3"}
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
                resp = await c.post(
                    f"{self.BASE_URL}/v1/tts",
                    json=payload,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
        except httpx.HTTPError as e:
            return _fail(f"Fish Audio network error: {e}")

        if resp.status_code != 200:
            return _fail(f"Fish Audio HTTP {resp.status_code}", resp.status_code)

        import hashlib as _hl
        job_id = f"fa_{_hl.md5(prompt[:100].encode()).hexdigest()[:12]}"
        return _ok({
            "provider_job_id": job_id,
            "provider": "fish_audio",
            "requires_polling": False,
            "audio_bytes_len": len(resp.content),
        })


# ── VOICE: Voxtral TTS ───────────────────────────────────────────

class VoxtralClient:
    BASE_URL = "https://api.mistral.ai"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("MISTRAL_API_KEY", "")

    def _is_configured(self) -> bool:
        return bool(self.api_key)

    async def generate(self, text: str, voice_id: str | None = None) -> dict[str, Any]:
        if not self._is_configured():
            return _blocked("MISTRAL_API_KEY not configured")
        payload: dict[str, Any] = {"model": "voxtral-mini-latest", "inputs": [{"type": "text", "content": text}]}
        if voice_id:
            payload["voice"] = {"voice_id": voice_id}
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
                resp = await c.post(f"{self.BASE_URL}/v1/audio/speech", json=payload, headers={"Authorization": f"Bearer {self.api_key}"})
        except httpx.HTTPError as e:
            return _fail(f"Voxtral network error: {e}")
        if resp.status_code != 200:
            return _fail(f"Voxtral HTTP {resp.status_code}", resp.status_code)
        return _ok({"audio_bytes_len": len(resp.content), "model": "voxtral-mini", "format": "mp3"}, resp.status_code)

    async def submit_async(self, prompt: str, webhook_url: str | None = None, **kwargs) -> dict[str, Any]:
        """Submit a Voxtral TTS job and return immediately.

        Voxtral TTS is synchronous — audio bytes come back in the HTTP
        response. No webhook or polling needed.
        """
        if not self._is_configured():
            return _blocked("MISTRAL_API_KEY not configured")

        voice_id = kwargs.get("voice_id")
        payload: dict[str, Any] = {"model": "voxtral-mini-latest", "inputs": [{"type": "text", "content": prompt}]}
        if voice_id:
            payload["voice"] = {"voice_id": voice_id}
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
                resp = await c.post(
                    f"{self.BASE_URL}/v1/audio/speech",
                    json=payload,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
        except httpx.HTTPError as e:
            return _fail(f"Voxtral network error: {e}")

        if resp.status_code != 200:
            return _fail(f"Voxtral HTTP {resp.status_code}", resp.status_code)

        import hashlib as _hl
        job_id = f"vx_{_hl.md5(prompt[:100].encode()).hexdigest()[:12]}"
        return _ok({
            "provider_job_id": job_id,
            "provider": "voxtral",
            "requires_polling": False,
            "audio_bytes_len": len(resp.content),
        })


# ── MUSIC: Suno ───────────────────────────────────────────────────

# ── VOICE: ElevenLabs (Hero) ──────────────────────────────────────

class ElevenLabsClient:
    BASE_URL = "https://api.elevenlabs.io"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("ELEVENLABS_API_KEY", "")

    def _is_configured(self) -> bool:
        return bool(self.api_key)

    async def generate(self, text: str, voice_id: str = "21m00Tcm4TlvDq8ikWAM", model_id: str = "eleven_multilingual_v2", stability: float = 0.5, similarity_boost: float = 0.75) -> dict[str, Any]:
        """Generate speech audio from text. Returns audio URL or bytes."""
        if not self._is_configured():
            return _blocked("ELEVENLABS_API_KEY not configured")

        async def _call() -> dict[str, Any]:
            payload = {"text": text, "model_id": model_id, "voice_settings": {"stability": stability, "similarity_boost": similarity_boost}}
            try:
                async with httpx.AsyncClient(timeout=_POLL_TIMEOUT) as c:
                    resp = await c.post(f"{self.BASE_URL}/v1/text-to-speech/{voice_id}", json=payload, headers={"xi-api-key": self.api_key, "Content-Type": "application/json", "Accept": "audio/mpeg"})
            except httpx.HTTPError as e:
                return _fail(f"ElevenLabs network error: {e}")
            if resp.status_code != 200:
                err = await _handle_response(resp, "ElevenLabs")
                if err:
                    return err
            return _ok({"audio_bytes": resp.content, "content_type": "audio/mpeg", "voice_id": voice_id, "model": model_id, "char_count": len(text)})

        return await _request_with_retry(_call, "ElevenLabs")

    async def get_voices(self) -> dict[str, Any]:
        if not self._is_configured():
            return _blocked("ELEVENLABS_API_KEY not configured")
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
                resp = await c.get(f"{self.BASE_URL}/v1/voices", headers={"xi-api-key": self.api_key})
            if resp.status_code != 200:
                return _fail(f"ElevenLabs voices HTTP {resp.status_code}")
            return _ok(resp.json())
        except httpx.HTTPError as e:
            return _fail(f"ElevenLabs network error: {e}")

    async def submit_async(self, prompt: str, webhook_url: str | None = None, **kwargs) -> dict[str, Any]:
        """Submit an ElevenLabs TTS job and return immediately.

        ElevenLabs TTS is fundamentally synchronous (returns audio bytes in
        the response), so this method does NOT support webhooks. The caller
        should treat the result as completed immediately and read the audio
        from the response, or fall back to the synchronous generate() method.

        For long-form content, ElevenLabs has a Projects API that is truly
        async; this uses the standard TTS endpoint.
        """
        if not self._is_configured():
            return _blocked("ELEVENLABS_API_KEY not configured")

        voice_id = kwargs.get("voice_id", "21m00Tcm4TlvDq8ikWAM")
        model_id = kwargs.get("model_id", "eleven_multilingual_v2")
        stability = kwargs.get("stability", 0.5)
        similarity_boost = kwargs.get("similarity_boost", 0.75)

        payload = {
            "text": prompt,
            "model_id": model_id,
            "voice_settings": {"stability": stability, "similarity_boost": similarity_boost},
        }
        try:
            async with httpx.AsyncClient(timeout=_POLL_TIMEOUT) as c:
                resp = await c.post(
                    f"{self.BASE_URL}/v1/text-to-speech/{voice_id}",
                    json=payload,
                    headers={"xi-api-key": self.api_key, "Content-Type": "application/json", "Accept": "audio/mpeg"},
                )
        except httpx.HTTPError as e:
            return _fail(f"ElevenLabs network error: {e}")

        if resp.status_code != 200:
            err = await _handle_response(resp, "ElevenLabs")
            if err:
                return err

        # ElevenLabs TTS is synchronous — audio is in the response body.
        # We return requires_polling=False since the job is already done.
        import hashlib as _hl
        job_id = f"el_{_hl.md5(prompt[:100].encode()).hexdigest()[:12]}"
        return _ok({
            "provider_job_id": job_id,
            "provider": "elevenlabs",
            "requires_polling": False,
            "audio_bytes": resp.content,
            "content_type": "audio/mpeg",
        })

    async def clone_voice(self, name: str, audio_file_bytes: bytes, description: str = "") -> dict[str, Any]:
        if not self._is_configured():
            return _blocked("ELEVENLABS_API_KEY not configured")
        try:
            async with httpx.AsyncClient(timeout=_POLL_TIMEOUT) as c:
                files = {"files": ("sample.mp3", audio_file_bytes, "audio/mpeg")}
                data = {"name": name, "description": description}
                resp = await c.post(f"{self.BASE_URL}/v1/voices/add", files=files, data=data, headers={"xi-api-key": self.api_key})
            if resp.status_code not in (200, 201):
                return _fail(f"ElevenLabs clone HTTP {resp.status_code}")
            return _ok(resp.json())
        except httpx.HTTPError as e:
            return _fail(f"ElevenLabs network error: {e}")


# ── AVATAR: HeyGen ───────────────────────────────────────────────

class HeyGenClient:
    BASE_URL = "https://api.heygen.com"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("HEYGEN_API_KEY", "")

    def _is_configured(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict:
        return {"X-Api-Key": self.api_key, "Content-Type": "application/json", "Accept": "application/json"}

    async def create_video(self, script_text: str, avatar_id: str = "default", voice_id: str = "", voice_url: str = "") -> dict[str, Any]:
        """Create an avatar video. Returns video_id for polling."""
        if not self._is_configured():
            return _blocked("HEYGEN_API_KEY not configured")
        clip = {"avatar_id": avatar_id, "input_text": script_text[:3000]}
        if voice_id:
            clip["voice_id"] = voice_id
        if voice_url:
            clip["input_audio"] = voice_url
        payload = {"video_inputs": [{"character": {"type": "avatar", "avatar_id": avatar_id}, "voice": {"type": "text", "input_text": script_text[:3000]}}], "dimension": {"width": 1080, "height": 1920}}
        if voice_url:
            payload["video_inputs"][0]["voice"] = {"type": "audio", "audio_url": voice_url}
        elif voice_id:
            payload["video_inputs"][0]["voice"]["voice_id"] = voice_id
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
                resp = await c.post(f"{self.BASE_URL}/v2/video/generate", json=payload, headers=self._headers())
        except httpx.HTTPError as e:
            return _fail(f"HeyGen network error: {e}")
        if resp.status_code not in (200, 201):
            return _fail(f"HeyGen create HTTP {resp.status_code}: {resp.text[:200]}", resp.status_code)
        body = resp.json()
        video_id = body.get("data", {}).get("video_id", "")
        return _ok({"video_id": video_id, "status": "processing"})

    async def poll_video(self, video_id: str, max_wait: int = 300) -> dict[str, Any]:
        """Poll until video is ready. Returns video_url on success."""
        if not self._is_configured():
            return _blocked("HEYGEN_API_KEY not configured")
        import asyncio as aio
        elapsed = 0
        interval = 10
        while elapsed < max_wait:
            try:
                async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
                    resp = await c.get(f"{self.BASE_URL}/v1/video_status.get", params={"video_id": video_id}, headers=self._headers())
                if resp.status_code == 200:
                    data = resp.json().get("data", {})
                    status = data.get("status", "")
                    if status == "completed":
                        return _ok({"video_url": data.get("video_url", ""), "video_id": video_id, "status": "completed", "duration": data.get("duration")})
                    if status in ("failed", "error"):
                        return _fail(f"HeyGen video failed: {data.get('error', 'unknown')}")
            except httpx.HTTPError:
                pass
            await aio.sleep(interval)
            elapsed += interval
        return _fail(f"HeyGen poll timeout after {max_wait}s")

    async def generate(self, script_text: str, avatar_id: str = "default", voice_id: str = "", voice_url: str = "") -> dict[str, Any]:
        """Full flow: create + poll until done."""
        create_result = await self.create_video(script_text, avatar_id, voice_id, voice_url)
        if not create_result.get("success"):
            return create_result
        video_id = create_result["data"]["video_id"]
        if not video_id:
            return _fail("HeyGen returned no video_id")
        return await self.poll_video(video_id)

    async def submit_async(self, prompt: str, webhook_url: str | None = None, **kwargs) -> dict[str, Any]:
        """Submit a HeyGen video generation job and return immediately.

        Uses POST /v2/video/generate with callback_url so HeyGen notifies us
        when the video is ready instead of requiring polling.
        """
        if not self._is_configured():
            return _blocked("HEYGEN_API_KEY not configured")

        avatar_id = kwargs.get("avatar_id", "default")
        voice_id = kwargs.get("voice_id", "")
        voice_url = kwargs.get("voice_url", "")
        cb_url = _webhook_url("heygen", webhook_url)

        payload: dict[str, Any] = {
            "video_inputs": [{
                "character": {"type": "avatar", "avatar_id": avatar_id},
                "voice": {"type": "text", "input_text": prompt[:3000]},
            }],
            "dimension": {"width": 1080, "height": 1920},
        }
        if voice_url:
            payload["video_inputs"][0]["voice"] = {"type": "audio", "audio_url": voice_url}
        elif voice_id:
            payload["video_inputs"][0]["voice"]["voice_id"] = voice_id
        if cb_url:
            payload["callback_url"] = cb_url

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
                resp = await c.post(f"{self.BASE_URL}/v2/video/generate", json=payload, headers=self._headers())
        except httpx.HTTPError as e:
            return _fail(f"HeyGen network error: {e}")

        if resp.status_code not in (200, 201):
            return _fail(f"HeyGen create HTTP {resp.status_code}: {resp.text[:200]}", resp.status_code)

        body = resp.json()
        video_id = body.get("data", {}).get("video_id", "")
        return _ok({
            "provider_job_id": video_id,
            "provider": "heygen",
            "requires_polling": cb_url is None,
        })

    async def poll_status(self, job_id: str) -> dict[str, Any]:
        """Check if an async HeyGen job has completed."""
        if not self._is_configured():
            return _blocked("HEYGEN_API_KEY not configured")
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
                resp = await c.get(
                    f"{self.BASE_URL}/v1/video_status.get",
                    params={"video_id": job_id},
                    headers=self._headers(),
                )
            if resp.status_code != 200:
                return _fail(f"HeyGen poll HTTP {resp.status_code}")
            data = resp.json().get("data", {})
            status = data.get("status", "processing")
            if status == "completed":
                return _ok({"status": "completed", "output_url": data.get("video_url", ""), "error": None})
            if status in ("failed", "error"):
                return _ok({"status": "failed", "output_url": None, "error": data.get("error", "unknown")})
            return _ok({"status": "processing", "output_url": None, "error": None})
        except httpx.HTTPError as e:
            return _fail(f"HeyGen network error: {e}")

    async def list_avatars(self) -> dict[str, Any]:
        if not self._is_configured():
            return _blocked("HEYGEN_API_KEY not configured")
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
                resp = await c.get(f"{self.BASE_URL}/v2/avatars", headers=self._headers())
            if resp.status_code != 200:
                return _fail(f"HeyGen avatars HTTP {resp.status_code}")
            return _ok(resp.json().get("data", {}).get("avatars", []))
        except httpx.HTTPError as e:
            return _fail(f"HeyGen network error: {e}")


# ── AVATAR: Synthesia ────────────────────────────────────────────

class SynthesiaClient:
    BASE_URL = "https://api.synthesia.io"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("SYNTHESIA_API_KEY", "")

    def _is_configured(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict:
        return {"Authorization": self.api_key, "Content-Type": "application/json"}

    async def create_video(self, script_text: str, avatar_id: str = "anna_costume1_cameraA", language: str = "en-US") -> dict[str, Any]:
        if not self._is_configured():
            return _blocked("SYNTHESIA_API_KEY not configured")
        payload = {"input": [{"scriptText": script_text[:5000], "avatar": avatar_id, "avatarSettings": {"horizontalAlign": "center"}}], "aspectRatio": "9:16"}
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
                resp = await c.post(f"{self.BASE_URL}/v2/videos", json=payload, headers=self._headers())
        except httpx.HTTPError as e:
            return _fail(f"Synthesia network error: {e}")
        if resp.status_code not in (200, 201):
            return _fail(f"Synthesia create HTTP {resp.status_code}: {resp.text[:200]}")
        body = resp.json()
        return _ok({"video_id": body.get("id", ""), "status": "processing"})

    async def poll_video(self, video_id: str, max_wait: int = 600) -> dict[str, Any]:
        if not self._is_configured():
            return _blocked("SYNTHESIA_API_KEY not configured")
        import asyncio as aio
        elapsed = 0
        interval = 15
        while elapsed < max_wait:
            try:
                async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
                    resp = await c.get(f"{self.BASE_URL}/v2/videos/{video_id}", headers=self._headers())
                if resp.status_code == 200:
                    data = resp.json()
                    status = data.get("status", "")
                    if status == "complete":
                        return _ok({"video_url": data.get("download", ""), "video_id": video_id, "status": "completed", "duration": data.get("duration")})
                    if status == "error":
                        return _fail(f"Synthesia video failed: {data.get('errorMessage', 'unknown')}")
            except httpx.HTTPError:
                pass
            await aio.sleep(interval)
            elapsed += interval
        return _fail(f"Synthesia poll timeout after {max_wait}s")

    async def generate(self, script_text: str, avatar_id: str = "anna_costume1_cameraA") -> dict[str, Any]:
        create_result = await self.create_video(script_text, avatar_id)
        if not create_result.get("success"):
            return create_result
        video_id = create_result["data"]["video_id"]
        return await self.poll_video(video_id)

    async def submit_async(self, prompt: str, webhook_url: str | None = None, **kwargs) -> dict[str, Any]:
        """Submit a Synthesia video generation job and return immediately.

        Uses POST /v2/videos with callbackUrl for webhook notification.
        """
        if not self._is_configured():
            return _blocked("SYNTHESIA_API_KEY not configured")

        avatar_id = kwargs.get("avatar_id", "anna_costume1_cameraA")
        cb_url = _webhook_url("synthesia", webhook_url)

        payload: dict[str, Any] = {
            "input": [{
                "scriptText": prompt[:5000],
                "avatar": avatar_id,
                "avatarSettings": {"horizontalAlign": "center"},
            }],
            "aspectRatio": "9:16",
        }
        if cb_url:
            payload["callbackUrl"] = cb_url

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
                resp = await c.post(f"{self.BASE_URL}/v2/videos", json=payload, headers=self._headers())
        except httpx.HTTPError as e:
            return _fail(f"Synthesia network error: {e}")

        if resp.status_code not in (200, 201):
            return _fail(f"Synthesia create HTTP {resp.status_code}: {resp.text[:200]}")

        body = resp.json()
        video_id = body.get("id", "")
        return _ok({
            "provider_job_id": video_id,
            "provider": "synthesia",
            "requires_polling": cb_url is None,
        })

    async def poll_status(self, job_id: str) -> dict[str, Any]:
        """Check if an async Synthesia job has completed."""
        if not self._is_configured():
            return _blocked("SYNTHESIA_API_KEY not configured")
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
                resp = await c.get(f"{self.BASE_URL}/v2/videos/{job_id}", headers=self._headers())
            if resp.status_code != 200:
                return _fail(f"Synthesia poll HTTP {resp.status_code}")
            data = resp.json()
            status = data.get("status", "in_progress")
            if status == "complete":
                return _ok({"status": "completed", "output_url": data.get("download", ""), "error": None})
            if status == "error":
                return _ok({"status": "failed", "output_url": None, "error": data.get("errorMessage", "unknown")})
            return _ok({"status": "processing", "output_url": None, "error": None})
        except httpx.HTTPError as e:
            return _fail(f"Synthesia network error: {e}")


# ── MUSIC: Suno ──────────────────────────────────────────────────

class SunoClient:
    """Suno — AI music generation. Hero tier for full songs with vocals."""
    BASE_URL = "https://api.suno.ai"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("SUNO_API_KEY", "")

    def _is_configured(self) -> bool:
        return bool(self.api_key)

    async def generate(self, prompt: str, duration_sec: int = 30, genre: str = "electronic") -> dict[str, Any]:
        if not self._is_configured():
            return _blocked("SUNO_API_KEY not configured")
        payload = {"prompt": prompt, "duration": duration_sec, "genre": genre}
        try:
            async with httpx.AsyncClient(timeout=_POLL_TIMEOUT) as c:
                resp = await c.post(f"{self.BASE_URL}/v1/generate", json=payload, headers={"Authorization": f"Bearer {self.api_key}"})
        except httpx.HTTPError as e:
            return _fail(f"Suno network error: {e}")
        err = await _handle_response(resp, "Suno")
        if err:
            return err
        body = resp.json()
        return _ok({"audio_url": body.get("audio_url", ""), "model": "suno"}, resp.status_code)


# ── MUSIC: Mubert ────────────────────────────────────────────────

class MubertClient:
    """Mubert — AI-generated royalty-free background music. Standard tier for ambient/looping tracks."""
    BASE_URL = "https://api.mubert.com/v2"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("MUBERT_API_KEY", "")

    def _is_configured(self) -> bool:
        return bool(self.api_key)

    async def generate(self, prompt: str, duration_sec: int = 30, intensity: str = "medium") -> dict[str, Any]:
        if not self._is_configured():
            return _blocked("MUBERT_API_KEY not configured")
        payload = {"method": "RecordTrackTTM", "params": {"pat": self.api_key, "prompt": prompt, "duration": duration_sec, "intensity": intensity, "format": "mp3"}}
        try:
            async with httpx.AsyncClient(timeout=_POLL_TIMEOUT) as c:
                resp = await c.post(f"{self.BASE_URL}/TTMRecordTrack", json=payload)
        except httpx.HTTPError as e:
            return _fail(f"Mubert network error: {e}")
        err = await _handle_response(resp, "Mubert")
        if err:
            return err
        body = resp.json()
        task_id = body.get("data", {}).get("tasks", [{}])[0].get("task_id", "")
        if not task_id:
            return _fail("Mubert returned no task_id")
        for _ in range(20):
            await asyncio.sleep(5)
            try:
                async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
                    poll = await c.post(f"{self.BASE_URL}/TrackStatus", json={"method": "TrackStatus", "params": {"pat": self.api_key, "task_id": task_id}})
                pdata = poll.json()
                status = pdata.get("data", {}).get("tasks", [{}])[0].get("task_status_code", 0)
                if status == 2:
                    audio_url = pdata.get("data", {}).get("tasks", [{}])[0].get("download_link", "")
                    return _ok({"audio_url": audio_url, "model": "mubert", "task_id": task_id})
                if status == 3:
                    return _fail("Mubert generation failed")
            except httpx.HTTPError:
                pass
        return _fail("Mubert generation timed out")


# ── MUSIC: Stable Audio ──────────────────────────────────────────

class StableAudioClient:
    """Stable Audio (Stability AI) — high-quality AI music + sound effects. Bulk tier."""
    BASE_URL = "https://api.stability.ai"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("STABILITY_API_KEY", "")

    def _is_configured(self) -> bool:
        return bool(self.api_key)

    async def generate(self, prompt: str, duration_sec: float = 30.0, negative_prompt: str = "") -> dict[str, Any]:
        if not self._is_configured():
            return _blocked("STABILITY_API_KEY not configured")
        payload = {"prompt": prompt, "seconds_total": min(duration_sec, 180), "steps": 100}
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt
        try:
            async with httpx.AsyncClient(timeout=_POLL_TIMEOUT) as c:
                resp = await c.post(
                    f"{self.BASE_URL}/v2beta/stable-audio/generate",
                    json=payload,
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json", "Accept": "audio/*"},
                )
        except httpx.HTTPError as e:
            return _fail(f"Stable Audio network error: {e}")
        if resp.status_code != 200:
            err = await _handle_response(resp, "Stable Audio")
            if err:
                return err
        content_type = resp.headers.get("content-type", "")
        if "audio" in content_type:
            return _ok({"audio_bytes": resp.content, "content_type": content_type, "model": "stable-audio-2.0"})
        body = resp.json() if "json" in content_type else {}
        audio_url = body.get("audio_url", "") or body.get("url", "")
        return _ok({"audio_url": audio_url, "model": "stable-audio-2.0"}, resp.status_code)

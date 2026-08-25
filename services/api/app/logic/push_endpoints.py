from __future__ import annotations

import ipaddress
import socket
from queue import Empty, Queue
from threading import Thread
from urllib.parse import urlsplit

from app.config import settings


DEFAULT_PUSH_HOST_SUFFIXES = (
    "fcm.googleapis.com",
    "android.googleapis.com",
    "fcmregistrations.googleapis.com",
    "push.services.mozilla.com",
    "push.mozilla.com",
    "web.push.apple.com",
    "push.apple.com",
    "notify.windows.com",
    "wns.windows.com",
)

_METADATA_HOSTS = {
    "metadata.google.internal",
    "metadata.goog",
    "instance-data",
}
DNS_RESOLUTION_TIMEOUT_SECONDS = 2


class PushEndpointError(ValueError):
    pass


def _configured_suffixes() -> tuple[str, ...]:
    configured = getattr(settings, "web_push_allowed_host_suffixes", "")
    extra = tuple(
        item.strip().lstrip(".").lower().rstrip(".")
        for item in configured.split(",")
        if item.strip()
    )
    return DEFAULT_PUSH_HOST_SUFFIXES + extra


def _host_matches_suffix(host: str, suffix: str) -> bool:
    return host == suffix or host.endswith("." + suffix)


def _is_blocked_ip(value: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return bool(
        value.is_private
        or value.is_loopback
        or value.is_link_local
        or value.is_multicast
        or value.is_reserved
        or value.is_unspecified
    )


def _normalized_host(raw_host: str) -> str:
    try:
        return raw_host.encode("idna").decode("ascii").lower().rstrip(".")
    except UnicodeError as exc:
        raise PushEndpointError("Push endpoint host is invalid") from exc


def _reject_literal_or_metadata_host(host: str) -> None:
    if host in _METADATA_HOSTS or host.endswith(".internal"):
        raise PushEndpointError("Push endpoint host is not allowed")
    try:
        value = ipaddress.ip_address(host)
    except ValueError:
        return
    if _is_blocked_ip(value):
        raise PushEndpointError("Push endpoint host is not allowed")


def _reject_resolved_private_ips(host: str) -> None:
    result: Queue[tuple[list | None, Exception | None]] = Queue(maxsize=1)

    def resolve() -> None:
        try:
            infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        except (socket.gaierror, OSError) as exc:
            result.put((None, exc))
        else:
            result.put((infos, None))

    Thread(target=resolve, daemon=True, name="notification-dns").start()
    try:
        infos, error = result.get(timeout=DNS_RESOLUTION_TIMEOUT_SECONDS)
    except Empty as exc:
        raise PushEndpointError("Push endpoint DNS resolution timed out") from exc
    if error is not None:
        raise PushEndpointError("Push endpoint host could not be resolved") from error
    if infos is None:
        raise PushEndpointError("Push endpoint host could not be resolved")
    if not infos:
        raise PushEndpointError("Push endpoint host could not be resolved")
    for info in infos:
        sockaddr = info[4]
        if not sockaddr:
            raise PushEndpointError("Push endpoint returned an invalid address")
        try:
            value = ipaddress.ip_address(sockaddr[0].split("%", 1)[0])
        except ValueError as exc:
            raise PushEndpointError("Push endpoint returned an invalid address") from exc
        if _is_blocked_ip(value):
            raise PushEndpointError("Push endpoint resolved to a blocked address")


def validate_push_endpoint(endpoint: str, *, resolve_dns: bool = False) -> str:
    if not endpoint or len(endpoint) > 4096:
        raise PushEndpointError("Push endpoint is missing or too long")
    try:
        parsed = urlsplit(endpoint)
        port = parsed.port
    except ValueError as exc:
        raise PushEndpointError("Push endpoint is invalid") from exc
    if parsed.scheme.lower() != "https":
        raise PushEndpointError("Push endpoint must use HTTPS")
    if parsed.username or parsed.password:
        raise PushEndpointError("Push endpoint must not include credentials")
    if parsed.fragment:
        raise PushEndpointError("Push endpoint must not include a fragment")
    if port not in (None, 443):
        raise PushEndpointError("Push endpoint must use the HTTPS port")
    host = _normalized_host(parsed.hostname or "")
    if not host:
        raise PushEndpointError("Push endpoint host is missing")
    _reject_literal_or_metadata_host(host)
    if not any(_host_matches_suffix(host, suffix) for suffix in _configured_suffixes()):
        raise PushEndpointError("Push endpoint is not a recognized Web Push provider")
    if resolve_dns:
        _reject_resolved_private_ips(host)
    return endpoint


def no_redirect_session():
    import requests

    class _NoRedirectSession(requests.Session):
        def __init__(self) -> None:
            super().__init__()
            self.trust_env = False
            self.max_redirects = 0

        def send(self, request, **kwargs):  # type: ignore[no-untyped-def]
            kwargs["allow_redirects"] = False
            kwargs.setdefault("timeout", (3.05, 10))
            validate_push_endpoint(request.url, resolve_dns=True)
            response = super().send(request, **kwargs)
            if 300 <= int(response.status_code) < 400:
                response.close()
                raise PushEndpointError("Push provider redirects are not allowed")
            return response

    return _NoRedirectSession()

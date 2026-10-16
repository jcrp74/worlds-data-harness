"""Adaptador de HTML público; no usa claves ni APIs privadas del sitio."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
import hashlib
from html.parser import HTMLParser
import http.client
import re
import socket
import time
import urllib.error
import urllib.request

from .estado_actual import Entry, Observation, aware, utc_now

SOURCE_URL = "https://lolesports.com/en-US/"
MAX_BYTES = 4 * 1024 * 1024  # Margen sobre los 2,53 MB observados; no descargas ilimitadas.
MAX_NODES = 60_000
MAX_DEPTH = 96
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
IGNORE = {"script", "style", "svg", "template", "noscript"}


class SourceError(Exception):
    """Código estable; los mensajes y cuerpos externos no se reproducen en errores."""


@dataclass(frozen=True)
class Response:
    status: int
    headers: dict[str, str]
    body: bytes


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch_html(*, timeout: float, max_bytes: int = MAX_BYTES) -> Response:
    """Una solicitud, sin redirects ni reintentos; TLS y proxies del sistema.

    Timeout de socket y presupuesto comprobado entre lecturas. Una operación de
    socket en curso puede consumir su timeout antes de devolver el control.
    """
    request = urllib.request.Request(SOURCE_URL, headers={
        "User-Agent": "WorldsDataHarness/0.1",
        "Accept": "text/html",
        "Accept-Encoding": "identity",
    })
    opener = urllib.request.build_opener(_NoRedirect())
    deadline = time.monotonic() + timeout
    try:
        try:
            stream = opener.open(request, timeout=timeout)
        except urllib.error.HTTPError as error:
            with error:
                return Response(error.code, {k.lower(): v for k, v in error.headers.items()}, b"")
        with stream:
            headers = {k.lower(): v for k, v in stream.headers.items()}
            if headers.get("content-encoding", "identity").lower() not in {"identity", ""}:
                raise SourceError("unsupported_content_encoding")
            length = headers.get("content-length")
            if length is not None:
                if not re.fullmatch(r"[0-9]{1,20}", length):
                    raise SourceError("invalid_content_length")
                if int(length) > max_bytes:
                    raise SourceError("response_too_large")
            body = bytearray()
            while True:
                if time.monotonic() >= deadline:
                    raise SourceError("timeout")
                chunk = stream.read1(min(65536, max_bytes + 1 - len(body)))
                if time.monotonic() >= deadline:
                    raise SourceError("timeout")
                if not chunk:
                    break
                body.extend(chunk)
                if len(body) > max_bytes:
                    raise SourceError("response_too_large")
            if length is not None and len(body) != int(length):
                raise SourceError("response_truncated")
            return Response(stream.status, headers, bytes(body))
    except (TimeoutError, socket.timeout):
        raise SourceError("timeout") from None
    except urllib.error.URLError as error:
        code = "timeout" if isinstance(error.reason, TimeoutError) else "network_error"
        raise SourceError(code) from None
    except (OSError, http.client.HTTPException):
        raise SourceError("network_error") from None


@dataclass(slots=True)
class _Node:
    tag: str
    attrs: dict[str, str | None]
    parent: "_Node | None" = None
    children: list = field(default_factory=list)

    def descendants(self, tag: str):
        for child in self.children:
            if isinstance(child, _Node):
                if child.tag == tag:
                    yield child
                yield from child.descendants(tag)

    def text(self) -> str:
        return " ".join(c.text() if isinstance(c, _Node) else c for c in self.children)


class _Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _Node("root", {})
        self.stack = [self.root]
        self.ignored_depth = 0
        self.nodes = 0
        self.closed_html = False

    def handle_starttag(self, tag, attrs):
        if self.ignored_depth:
            if tag not in VOID:
                self.ignored_depth += 1
            return
        if tag in IGNORE:
            self.ignored_depth = 1
            return
        self.nodes += 1
        if self.nodes > MAX_NODES or len(self.stack) > MAX_DEPTH:
            raise SourceError("html_complexity_exceeded")
        attrs = {k: v for k, v in attrs if k in {"alt", "datetime", "data-tag", "aria-label"}}
        node = _Node(tag, attrs, self.stack[-1])
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if self.ignored_depth:
            self.ignored_depth -= 1
            return
        if tag == "html":
            self.closed_html = True
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                self.stack = self.stack[:index]
                break

    def handle_data(self, data):
        if not self.ignored_depth and data.strip():
            self.stack[-1].children.append(data)


def _clean(value: str) -> str:
    value = " ".join(value.split())
    if len(value) > 160 or any(not c.isprintable() for c in value):
        raise SourceError("invalid_team_label")
    return value


def parse_schedule(body: bytes) -> tuple[tuple[Entry, ...], tuple[str, ...]]:
    if len(body) > MAX_BYTES:
        raise SourceError("response_too_large")
    try:
        text = body.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise SourceError("invalid_utf8") from None
    page = _Page()
    page.feed(text)
    page.close()
    titles = list(page.root.descendants("title"))
    if not page.closed_html or len(titles) != 1 or titles[0].text().strip() != "LoL Esports | SCHEDULE":
        raise SourceError("schema_changed")
    footers = list(page.root.descendants("footer"))
    date_sections = [s for s in page.root.descendants("section") if s.attrs.get("data-tag") == "date"]
    empty_marker = "No Matches Scheduled Today" in page.root.text()
    if not date_sections or (not footers and not empty_marker):
        raise SourceError("schema_changed")
    entries = []
    warnings = {"html_streaming_scripts_not_executed", "provider_event_ids_unavailable"}
    invalid_worlds_rows = 0
    for index, footer in enumerate(footers):
        if not any(img.attrs.get("alt") == "Worlds" for img in footer.descendants("img")):
            continue
        labels = list(footer.descendants("p"))
        if not labels or not re.match(r"^Worlds(?:\s|$)", " ".join(labels[0].text().split())):
            warnings.add("unrecognized_worlds_footer")
            continue
        card = footer.parent
        times = list(card.descendants("time"))
        if not times:
            warnings.add("worlds_rows_without_explicit_time")
            continue
        if len(times) != 1 or len(list(card.descendants("footer"))) != 1:
            invalid_worlds_rows += 1
            warnings.add("ambiguous_card_structure")
            continue
        raw_time = times[0].attrs.get("datetime") or ""
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})", raw_time):
            invalid_worlds_rows += 1
            warnings.add("invalid_event_time")
            continue
        try:
            start = aware(datetime.fromisoformat(raw_time.replace("Z", "+00:00")))
        except ValueError:
            invalid_worlds_rows += 1
            warnings.add("invalid_event_time")
            continue
        if start.year != 2026:
            warnings.add("other_tournament_year_excluded")
            continue
        footer_images = list(footer.descendants("img"))
        team_images = [img for img in card.descendants("img") if not any(img is f for f in footer_images)]
        if len(team_images) != 2:
            invalid_worlds_rows += 1
            warnings.add("team_slots_incomplete")
            continue
        try:
            names = [_clean(img.attrs.get("alt") or "") for img in team_images]
        except SourceError:
            invalid_worlds_rows += 1
            warnings.add("invalid_team_label")
            continue
        teams = tuple(None if n in {"", "TBD"} else n for n in names)
        if None in teams:
            warnings.add("team_identity_pending")
        # El año explícito del timestamp y el marcador Worlds determinan el ámbito.
        # La posición es un localizador del cuerpo con hash, nunca un ID de evento.
        entries.append(Entry(start, teams, f"html:footer[{index}]"))
    if invalid_worlds_rows and not entries:
        raise SourceError("schema_changed")
    return tuple(entries), tuple(sorted(warnings))


def _retry_at(value: str | None, received_at: datetime) -> datetime | None:
    if value is None:
        return None
    try:
        if re.fullmatch(r"\d{1,8}", value.strip()):
            return aware(received_at) + timedelta(seconds=int(value))
        return max(aware(received_at), aware(parsedate_to_datetime(value)))
    except (ValueError, TypeError, OverflowError):
        return None


def query_schedule(*, timeout: float = 15, transport=fetch_html, clock=utc_now) -> Observation:
    requested = aware(clock())
    try:
        response = transport(timeout=timeout, max_bytes=MAX_BYTES)
    except SourceError as error:
        return Observation(SOURCE_URL, requested, aware(clock()), errors=(str(error),))
    received = aware(clock())
    headers = {k.lower(): v for k, v in response.headers.items()}
    warnings = []
    age = headers.get("age")
    if age is not None and (not age.isdecimal() or len(age) > 12):
        warnings.append("invalid_http_age")
        age = None
    retry_raw = headers.get("retry-after")
    retry_at = _retry_at(retry_raw, received)
    if retry_raw is not None and retry_at is None:
        warnings.append("invalid_retry_after")
    common = dict(
        source_url=SOURCE_URL, requested_at=requested, received_at=received,
        http_status=response.status, http_date=headers.get("date"),
        http_age_seconds=int(age) if age is not None else None,
        retry_not_before=retry_at, response_bytes=len(response.body),
        evidence_sha256=hashlib.sha256(response.body).hexdigest() if response.body else None,
    )
    if response.status != 200:
        code = {403: "http_forbidden", 429: "http_rate_limited"}.get(response.status, "http_error")
        if 300 <= response.status < 400:
            code = "http_redirect_rejected"
        return Observation(**common, warnings=tuple(warnings), errors=(code,))
    if headers.get("content-type", "").split(";", 1)[0].strip().lower() != "text/html":
        return Observation(**common, warnings=tuple(warnings), errors=("unexpected_content_type",))
    try:
        entries, parse_warnings = parse_schedule(response.body)
    except SourceError as error:
        return Observation(**common, warnings=tuple(warnings), errors=(str(error),))
    return Observation(**common, entries=entries, warnings=tuple(warnings) + parse_warnings)

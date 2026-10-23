from __future__ import annotations

import html
import ipaddress
import json
import socket
from urllib.parse import urlsplit

import requests

from .store import redact


def normalized_origin(url):
    parsed = urlsplit(url)
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise ValueError("只支持不包含内嵌凭据的 HTTP/HTTPS URL")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    return parsed.scheme.lower(), parsed.hostname.lower().rstrip("."), port


def allowed(url, scope, excluded):
    target = normalized_origin(url)

    def matches(rule):
        try:
            expected = normalized_origin(rule)
        except (ValueError, TypeError):
            return False
        if target != expected:
            return False
        prefix = urlsplit(rule).path.rstrip("/")
        path = urlsplit(url).path or "/"
        return not prefix or path == prefix or path.startswith(prefix + "/")

    return any(matches(rule) for rule in scope) and not any(
        matches(rule) for rule in excluded
    )


def import_requests(kind, data):
    result = []
    if kind == "har":
        entries = data.get("log", {}).get("entries", [])
        for entry in entries[:2000]:
            req = entry.get("request", {})
            headers = {
                h["name"]: h.get("value", "")
                for h in req.get("headers", [])
                if "name" in h
            }
            # Imported credentials are deliberately removed; login state is set by the user.
            headers = {
                k: v
                for k, v in headers.items()
                if k.lower()
                not in (
                    "authorization",
                    "cookie",
                    "proxy-authorization",
                    "x-api-key",
                    "x-auth-token",
                    "x-csrf-token",
                    "x-xsrf-token",
                )
            }
            result.append(
                {
                    "method": req.get("method", "GET").upper(),
                    "url": req.get("url", ""),
                    "headers": headers,
                    "body": redact(req.get("postData", {}).get("text", "")),
                }
            )
    else:
        servers = data.get("servers", [])
        if not servers or not servers[0].get("url", "").startswith(
            ("http://", "https://")
        ):
            raise ValueError("OpenAPI 文档需要包含绝对 HTTP/HTTPS servers URL")
        base = servers[0]["url"].rstrip("/")
        for path, operations in list(data.get("paths", {}).items())[:2000]:
            for method in operations:
                if method.upper() in (
                    "GET",
                    "HEAD",
                    "POST",
                    "PUT",
                    "PATCH",
                    "DELETE",
                    "OPTIONS",
                ):
                    result.append(
                        {
                            "method": method.upper(),
                            "url": base + path,
                            "headers": {},
                            "body": "",
                        }
                    )
    valid = []
    for item in result:
        normalized_origin(item["url"])
        if item["method"] not in (
            "GET",
            "HEAD",
            "POST",
            "PUT",
            "PATCH",
            "DELETE",
            "OPTIONS",
        ):
            continue
        valid.append(item)
    return valid


def replay_request(item):
    # Prevent proxy credentials, redirects, file URLs and cloud metadata destinations.
    parsed = urlsplit(item["url"])
    normalized_origin(item["url"])
    addresses = socket.getaddrinfo(
        parsed.hostname,
        parsed.port or (443 if parsed.scheme == "https" else 80),
        type=socket.SOCK_STREAM,
    )
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if ip.is_link_local or ip.is_multicast or ip.is_unspecified:
            raise ValueError("禁止访问链路本地、元数据或组播地址")
    headers = (
        json.loads(item["headers"])
        if isinstance(item["headers"], str)
        else item["headers"]
    )
    headers = {
        k: v
        for k, v in headers.items()
        if k.lower()
        not in ("host", "content-length", "proxy-authorization", "connection")
    }
    with requests.Session() as session:
        session.trust_env = False
        with session.request(
            item["method"],
            item["url"],
            headers=headers,
            data=item["body"],
            timeout=(5, 15),
            allow_redirects=False,
            stream=True,
        ) as response:
            content = bytearray()
            for chunk in response.iter_content(16384):
                content.extend(chunk)
                if len(content) > 1024 * 1024:
                    break
            return {
                "status": response.status_code,
                "headers": json.loads(redact(dict(response.headers))),
                "body": redact(
                    bytes(content[: 1024 * 1024]).decode(
                        response.encoding or "utf-8", errors="replace"
                    )
                ),
                "truncated": len(content) > 1024 * 1024,
            }


def report(project, findings, artifacts):
    confirmed = [f for f in findings if f["status"] == "confirmed"]
    lines = [
        f"# {project['title']} — 安全研究报告",
        "",
        f"起点：{project['origin']}",
        "",
        f"目标：{project['goal']}",
        "",
        f"范围：{', '.join(json.loads(project['scope']))}",
        "",
        f"已人工确认发现：{len(confirmed)}",
        "",
    ]
    known = {a["id"]: a for a in artifacts}
    for finding in confirmed:
        lines += [
            f"## [{finding['severity'].upper()}] {finding['title']}",
            "",
            finding["description"],
            "",
            "### 复现步骤",
            "",
            finding["reproduction"],
            "",
            "### 影响",
            "",
            finding["impact"],
            "",
            "### 证据",
            "",
        ]
        for ident in json.loads(finding["evidence"]):
            artifact = known.get(ident)
            if artifact:
                lines += [
                    f"- {artifact['name']} · SHA-256 `{artifact['sha256']}` · 运行 `{artifact['run_id'] or '人工录入'}`"
                ]
        lines += [""]
    return redact("\n".join(lines))


def html_report(markdown):
    # Escaped text keeps imported descriptions and model output inert in exported HTML.
    return (
        '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>安全研究报告</title><style>body{max-width:900px;margin:48px auto;padding:24px;font:15px/1.8 "Segoe UI",sans-serif;color:#202124}pre{white-space:pre-wrap;overflow-wrap:anywhere}@media print{body{margin:0;padding:0}}</style><pre>'
        + html.escape(markdown)
        + "</pre></html>"
    )


def pdf_report(markdown):
    from io import BytesIO
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

    font = "STSong-Light"
    pdfmetrics.registerFont(UnicodeCIDFont(font))
    styles = {
        "title": ParagraphStyle(
            "title",
            fontName=font,
            fontSize=20,
            leading=29,
            textColor=colors.HexColor("#202124"),
            spaceAfter=18,
            wordWrap="CJK",
        ),
        "section": ParagraphStyle(
            "section",
            fontName=font,
            fontSize=14,
            leading=22,
            spaceBefore=16,
            spaceAfter=8,
            wordWrap="CJK",
        ),
        "label": ParagraphStyle(
            "label",
            fontName=font,
            fontSize=11,
            leading=18,
            spaceBefore=10,
            spaceAfter=5,
            textColor=colors.HexColor("#565c67"),
            wordWrap="CJK",
        ),
        "body": ParagraphStyle(
            "body",
            fontName=font,
            fontSize=10.5,
            leading=18,
            spaceAfter=5,
            wordWrap="CJK",
        ),
    }
    stream = BytesIO()
    document = SimpleDocTemplate(
        stream,
        pagesize=A4,
        rightMargin=48,
        leftMargin=48,
        topMargin=62,
        bottomMargin=50,
        title="Cairn Security Research Report",
        author="Cairn Workbench",
    )
    story = []
    for line in markdown.splitlines():
        if not line.strip():
            story.append(Spacer(1, 5))
            continue
        style = (
            "title"
            if line.startswith("# ")
            else "section"
            if line.startswith("## ")
            else "label"
            if line.startswith("### ")
            else "body"
        )
        content = line.lstrip("# ").replace("`", "")
        story.append(Paragraph(html.escape(content), styles[style]))

    def chrome(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#787f8c"))
        canvas.drawString(48, A4[1] - 32, "CAIRN WORKBENCH / RESEARCH REPORT")
        canvas.setStrokeColor(colors.HexColor("#e3e5e9"))
        canvas.line(48, 37, A4[0] - 48, 37)
        canvas.drawRightString(A4[0] - 48, 25, str(doc.page))
        canvas.restoreState()

    document.build(story, onFirstPage=chrome, onLaterPages=chrome)
    return stream.getvalue()

"""
Secure Web Bridge tests: SSRF guards, URL validation, sanitization.
No live network calls — every test uses safe/blocked targets.
"""
from app.core import secure_web
from app.core.secure_web import sanitize_html, validate_url


def test_validate_url_rejects_private_networks():
    for url in (
        "http://192.168.1.1/admin",
        "http://10.0.0.5/",
        "http://127.0.0.1:8000/health",
        "http://localhost:8000/health",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/",
        "ftp://example.com/file",
        "file:///etc/passwd",
        "javascript:alert(1)",
        "https://10.0.0.1/",
        "https://192.168.0.10/",
        "",
    ):
        assert validate_url(url, allow_http=True) is not None, url


def test_validate_url_rejects_http_by_default():
    assert validate_url("http://example.com/") is not None
    assert validate_url("https://example.com/") is None


def test_validate_url_allows_http_when_flagged():
    assert validate_url("http://example.com/", allow_http=True) is None


def test_validate_url_accepts_public_https():
    assert validate_url("https://en.wikipedia.org/wiki/Campus") is None
    assert validate_url("https://www.python.org/doc/") is None


def test_fetch_url_blocks_private_host_without_network():
    result = secure_web.fetch_url("http://169.254.169.254/latest/meta-data/", allow_http=True)
    assert result["ok"] is False
    assert "private" in result["error"].lower() or "blocked" in result["error"].lower()


def test_fetch_url_blocks_localhost():
    result = secure_web.fetch_url("https://localhost:8443/", allow_http=True)
    assert result["ok"] is False


def test_sanitize_html_strips_scripts_and_styles():
    html = "<script>alert('xss')</script><style>body{display:none}</style><p>Hello <b>world</b> &amp; more</p>"
    text = sanitize_html(html)
    assert "alert" not in text
    assert "display" not in text
    assert "Hello world & more" in text


def test_sanitize_html_respects_limit():
    long = "<p>" + "x" * 5000 + "</p>"
    assert len(sanitize_html(long, limit=100)) <= 100


def test_validate_url_rejects_missing_host():
    assert validate_url("https:///path") is not None
    assert validate_url("not a url") is not None

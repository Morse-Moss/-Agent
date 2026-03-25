"""CR-001~009: SSRF protection tests for crawl URL validation."""
import pytest
from app.api.routes.crawl import _validate_crawl_url


class TestCrawlUrlValidation:
    """Unit tests for _validate_crawl_url()."""

    # CR-001: Valid public URL
    def test_valid_1688_url(self):
        ok, _ = _validate_crawl_url("https://detail.1688.com/offer/123456.html")
        assert ok

    def test_valid_taobao_url(self):
        ok, _ = _validate_crawl_url("https://item.taobao.com/item.htm?id=123")
        assert ok

    def test_valid_tmall_url(self):
        ok, _ = _validate_crawl_url("https://detail.tmall.com/item.htm?id=123")
        assert ok

    # CR-002: Invalid URL format
    def test_invalid_url_format(self):
        ok, reason = _validate_crawl_url("ht!tp://bad")
        assert not ok

    def test_empty_url(self):
        ok, reason = _validate_crawl_url("")
        assert not ok

    def test_none_like_url(self):
        ok, reason = _validate_crawl_url("   ")
        assert not ok

    # CR-003: Protocol restriction
    def test_file_protocol_blocked(self):
        ok, reason = _validate_crawl_url("file:///etc/passwd")
        assert not ok
        assert "Scheme" in reason or "not allowed" in reason

    def test_ftp_protocol_blocked(self):
        ok, reason = _validate_crawl_url("ftp://1688.com/file")
        assert not ok

    # CR-004: Localhost blocked
    def test_localhost_blocked(self):
        ok, reason = _validate_crawl_url("http://localhost:8000/admin")
        assert not ok

    def test_127_blocked(self):
        ok, reason = _validate_crawl_url("http://127.0.0.1:8000/admin")
        assert not ok

    # CR-005: Private IP ranges blocked
    def test_10_network_blocked(self):
        ok, reason = _validate_crawl_url("http://10.1.2.3/image.jpg")
        assert not ok

    def test_172_network_blocked(self):
        ok, reason = _validate_crawl_url("http://172.16.0.1/image.jpg")
        assert not ok

    def test_192_network_blocked(self):
        ok, reason = _validate_crawl_url("http://192.168.1.1/image.jpg")
        assert not ok

    # CR-006: Cloud metadata blocked
    def test_metadata_ip_blocked(self):
        ok, reason = _validate_crawl_url("http://169.254.169.254/latest/meta-data")
        assert not ok

    # CR-009: IPv6 loopback blocked
    def test_ipv6_loopback_blocked(self):
        ok, reason = _validate_crawl_url("http://[::1]/image.jpg")
        assert not ok

    # Non-whitelisted domain blocked
    def test_non_whitelisted_domain(self):
        ok, reason = _validate_crawl_url("https://evil.com/image.jpg")
        assert not ok
        assert "not in the allowed list" in reason

    def test_subdomain_of_allowed(self):
        ok, _ = _validate_crawl_url("https://img.1688.com/image.jpg")
        assert ok

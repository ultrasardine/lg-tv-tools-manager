"""Property-based tests for HLS server URL construction.

# Feature: screen-capture-mirror, Property 4: Player and stream URL construction is well-formed

These tests verify that player_url() and stream_url() produce valid, well-formed
HTTP URLs for any valid IPv4 address (non-loopback) and port number.
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlparse

from hypothesis import given, settings
from hypothesis import strategies as st

from lgtvtools.mirror.hls_server import HLSServer

# -----------------------------------------------------------------------------
# Strategies for generating valid IPv4 addresses and ports
# -----------------------------------------------------------------------------


def valid_ipv4_non_loopback() -> st.SearchStrategy[str]:
    """Generate valid IPv4 addresses excluding loopback (127.x.x.x).

    We generate realistic LAN addresses that would be used for streaming.
    """
    # Generate each octet separately
    # First octet: 1-126 or 128-254 (excluding 127 for loopback, 0 and 255 for special)
    first_octet = st.one_of(
        st.integers(min_value=1, max_value=126),
        st.integers(min_value=128, max_value=254),
    )
    # Remaining octets: 0-255
    other_octet = st.integers(min_value=0, max_value=255)

    return st.builds(
        lambda a, b, c, d: f"{a}.{b}.{c}.{d}",
        a=first_octet,
        b=other_octet,
        c=other_octet,
        d=other_octet,
    )


# Strategy for valid port numbers (1-65535)
valid_port = st.integers(min_value=1, max_value=65535)


# Combined strategy for (ip, port) tuples
ip_port_pairs = st.tuples(valid_ipv4_non_loopback(), valid_port)


class TestProperty4URLConstruction:
    """Property 4: Player and stream URL construction is well-formed.

    *For any* valid IPv4 address (not loopback) and port number in range
    [1, 65535], the constructed player_url SHALL be
    `http://<ip>:<port>/player.html` and stream_url SHALL be
    `http://<ip>:<port>/stream.m3u8`, both parseable as valid HTTP URLs.

    **Validates: Requirements 5.2**
    """

    @given(ip_port=ip_port_pairs)
    @settings(max_examples=100, deadline=None)
    def test_player_url_format(self, ip_port: tuple[str, int]) -> None:
        """player_url SHALL return http://<ip>:<port>/player.html.

        # Feature: screen-capture-mirror, Property 4: Player and stream URL construction is well-formed

        **Validates: Requirements 5.2**
        """
        host_ip, port = ip_port

        with TemporaryDirectory() as tmpdir:
            server = HLSServer(Path(tmpdir))
            # Set the port directly (server not started, just testing URL construction)
            server._port = port

            url = server.player_url(host_ip)

            # Verify exact format
            expected = f"http://{host_ip}:{port}/player.html"
            assert url == expected, (
                f"player_url format incorrect: got '{url}', "
                f"expected '{expected}'"
            )

    @given(ip_port=ip_port_pairs)
    @settings(max_examples=100, deadline=None)
    def test_stream_url_format(self, ip_port: tuple[str, int]) -> None:
        """stream_url SHALL return http://<ip>:<port>/stream.m3u8.

        # Feature: screen-capture-mirror, Property 4: Player and stream URL construction is well-formed

        **Validates: Requirements 5.2**
        """
        host_ip, port = ip_port

        with TemporaryDirectory() as tmpdir:
            server = HLSServer(Path(tmpdir))
            # Set the port directly (server not started, just testing URL construction)
            server._port = port

            url = server.stream_url(host_ip)

            # Verify exact format
            expected = f"http://{host_ip}:{port}/stream.m3u8"
            assert url == expected, (
                f"stream_url format incorrect: got '{url}', "
                f"expected '{expected}'"
            )

    @given(ip_port=ip_port_pairs)
    @settings(max_examples=100, deadline=None)
    def test_player_url_parseable_as_http(self, ip_port: tuple[str, int]) -> None:
        """player_url SHALL be parseable as a valid HTTP URL.

        # Feature: screen-capture-mirror, Property 4: Player and stream URL construction is well-formed

        **Validates: Requirements 5.2**
        """
        host_ip, port = ip_port

        with TemporaryDirectory() as tmpdir:
            server = HLSServer(Path(tmpdir))
            server._port = port

            url = server.player_url(host_ip)
            parsed = urlparse(url)

            # Verify scheme is http
            assert parsed.scheme == "http", (
                f"player_url scheme is '{parsed.scheme}', expected 'http'"
            )

            # Verify netloc matches ip:port
            expected_netloc = f"{host_ip}:{port}"
            assert parsed.netloc == expected_netloc, (
                f"player_url netloc is '{parsed.netloc}', "
                f"expected '{expected_netloc}'"
            )

            # Verify path is /player.html
            assert parsed.path == "/player.html", (
                f"player_url path is '{parsed.path}', expected '/player.html'"
            )

    @given(ip_port=ip_port_pairs)
    @settings(max_examples=100, deadline=None)
    def test_stream_url_parseable_as_http(self, ip_port: tuple[str, int]) -> None:
        """stream_url SHALL be parseable as a valid HTTP URL.

        # Feature: screen-capture-mirror, Property 4: Player and stream URL construction is well-formed

        **Validates: Requirements 5.2**
        """
        host_ip, port = ip_port

        with TemporaryDirectory() as tmpdir:
            server = HLSServer(Path(tmpdir))
            server._port = port

            url = server.stream_url(host_ip)
            parsed = urlparse(url)

            # Verify scheme is http
            assert parsed.scheme == "http", (
                f"stream_url scheme is '{parsed.scheme}', expected 'http'"
            )

            # Verify netloc matches ip:port
            expected_netloc = f"{host_ip}:{port}"
            assert parsed.netloc == expected_netloc, (
                f"stream_url netloc is '{parsed.netloc}', "
                f"expected '{expected_netloc}'"
            )

            # Verify path is /stream.m3u8
            assert parsed.path == "/stream.m3u8", (
                f"stream_url path is '{parsed.path}', expected '/stream.m3u8'"
            )

    @given(ip_port=ip_port_pairs)
    @settings(max_examples=100, deadline=None)
    def test_urls_do_not_contain_loopback(self, ip_port: tuple[str, int]) -> None:
        """Generated IPs SHALL not be loopback addresses.

        # Feature: screen-capture-mirror, Property 4: Player and stream URL construction is well-formed

        **Validates: Requirements 5.2**
        """
        host_ip, _port = ip_port

        # Verify the IP is not in the loopback range (127.0.0.0/8)
        octets = host_ip.split(".")
        first_octet = int(octets[0])
        assert first_octet != 127, (
            f"Generated IP '{host_ip}' is in loopback range (127.x.x.x)"
        )


class TestURLConstructionEdgeCases:
    """Edge case tests for URL construction.

    These tests cover specific edge cases that complement the property-based tests.
    """

    def test_minimum_port_number(self) -> None:
        """URL construction with port 1 should work."""
        with TemporaryDirectory() as tmpdir:
            server = HLSServer(Path(tmpdir))
            server._port = 1

            player_url = server.player_url("192.168.1.1")
            stream_url = server.stream_url("192.168.1.1")

            assert player_url == "http://192.168.1.1:1/player.html"
            assert stream_url == "http://192.168.1.1:1/stream.m3u8"

    def test_maximum_port_number(self) -> None:
        """URL construction with port 65535 should work."""
        with TemporaryDirectory() as tmpdir:
            server = HLSServer(Path(tmpdir))
            server._port = 65535

            player_url = server.player_url("10.0.0.1")
            stream_url = server.stream_url("10.0.0.1")

            assert player_url == "http://10.0.0.1:65535/player.html"
            assert stream_url == "http://10.0.0.1:65535/stream.m3u8"

    def test_typical_lan_addresses(self) -> None:
        """Common LAN IP ranges should produce valid URLs."""
        test_cases = [
            ("192.168.1.100", 8080),  # Class C private
            ("10.0.0.50", 3000),  # Class A private
            ("172.16.0.1", 9090),  # Class B private
            ("192.168.0.1", 80),  # Common router address
        ]

        for host_ip, port in test_cases:
            with TemporaryDirectory() as tmpdir:
                server = HLSServer(Path(tmpdir))
                server._port = port

                player_url = server.player_url(host_ip)
                stream_url = server.stream_url(host_ip)

                # Parse and verify
                player_parsed = urlparse(player_url)
                stream_parsed = urlparse(stream_url)

                assert player_parsed.scheme == "http"
                assert player_parsed.netloc == f"{host_ip}:{port}"
                assert player_parsed.path == "/player.html"

                assert stream_parsed.scheme == "http"
                assert stream_parsed.netloc == f"{host_ip}:{port}"
                assert stream_parsed.path == "/stream.m3u8"

    def test_url_construction_with_zero_in_octets(self) -> None:
        """IP addresses with zero octets should be handled correctly."""
        with TemporaryDirectory() as tmpdir:
            server = HLSServer(Path(tmpdir))
            server._port = 8080

            # IP with zeros in middle octets
            player_url = server.player_url("192.0.0.1")
            assert player_url == "http://192.0.0.1:8080/player.html"

            # IP with zero in last octet (network address)
            stream_url = server.stream_url("10.0.0.0")
            assert stream_url == "http://10.0.0.0:8080/stream.m3u8"

    def test_url_construction_with_max_octets(self) -> None:
        """IP addresses with maximum octet values (255) should work."""
        with TemporaryDirectory() as tmpdir:
            server = HLSServer(Path(tmpdir))
            server._port = 8080

            # Note: 255.255.255.255 is broadcast, but URL construction should still work
            player_url = server.player_url("192.168.255.255")
            assert player_url == "http://192.168.255.255:8080/player.html"

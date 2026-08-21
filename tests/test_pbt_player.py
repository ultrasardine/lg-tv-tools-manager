"""Property-based tests for the player HTML template module.

# Feature: screen-capture-mirror, Property 8: Player HTML template contains required elements

These tests verify that generate_player_html() produces valid HTML with all required
elements for any valid stream URL input.
"""

from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from lgtvtools.mirror.player import generate_player_html


# Strategy for generating valid HTTP stream URLs
# We generate various valid URLs that could be passed to generate_player_html
def valid_stream_url_strategy() -> st.SearchStrategy[str]:
    """Generate valid HTTP stream URL strings.

    URLs have the form: http://<host>:<port>/<path>
    where path ends with .m3u8 for HLS streams.
    """
    # Generate valid IPv4 addresses (avoiding localhost/loopback for realistic URLs)
    ip_octets = st.tuples(
        st.integers(min_value=1, max_value=254),  # Avoid 0 and 255
        st.integers(min_value=0, max_value=255),
        st.integers(min_value=0, max_value=255),
        st.integers(min_value=1, max_value=254),
    )
    ip_address = ip_octets.map(lambda o: f"{o[0]}.{o[1]}.{o[2]}.{o[3]}")

    # Generate valid port numbers (1-65535)
    port = st.integers(min_value=1, max_value=65535)

    # Generate optional path segments
    path_segment = st.text(
        alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz0123456789-_"),
        min_size=1,
        max_size=20,
    )

    # Build the full URL
    return st.builds(
        lambda ip, p, path: f"http://{ip}:{p}/{path}.m3u8",
        ip=ip_address,
        p=port,
        path=path_segment,
    )


# Also test with simple URLs to ensure edge cases work
simple_stream_urls = st.sampled_from(
    [
        "http://192.168.1.100:8080/stream.m3u8",
        "http://10.0.0.1:3000/video.m3u8",
        "http://172.16.0.50:9090/live.m3u8",
        "http://192.168.0.1:1/s.m3u8",
        "http://255.255.255.254:65535/test.m3u8",
    ]
)


class TestPlayerHtmlPropertyBased:
    """Property-based tests for generate_player_html().

    **Validates: Requirements 5.4**

    These tests verify that the generated HTML contains all required elements:
    - A <video> element for playback
    - A reference to hls.js (script tag)
    - The stream URL embedded in the JavaScript initialization code
    """

    @given(stream_url=valid_stream_url_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_html_contains_video_element(self, stream_url: str) -> None:
        """For any valid stream URL, HTML SHALL contain a <video> element.

        **Validates: Requirements 5.4**
        """
        html = generate_player_html(stream_url)

        assert "<video" in html, f"HTML missing <video> element for URL: {stream_url}"
        assert (
            "</video>" in html
        ), f"HTML missing closing </video> tag for URL: {stream_url}"

    @given(stream_url=valid_stream_url_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_html_contains_hlsjs_script_tag(self, stream_url: str) -> None:
        """For any valid stream URL, HTML SHALL reference hls.js via script tag.

        **Validates: Requirements 5.4**
        """
        html = generate_player_html(stream_url)

        # The HTML should contain a script tag referencing hls.js
        assert (
            "<script" in html
        ), f"HTML missing <script> tag for URL: {stream_url}"
        assert (
            "hls.js" in html.lower()
        ), f"HTML missing hls.js reference for URL: {stream_url}"

    @given(stream_url=valid_stream_url_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_html_contains_stream_url_in_javascript(self, stream_url: str) -> None:
        """For any valid stream URL, the URL SHALL be embedded in JavaScript code.

        **Validates: Requirements 5.4**
        """
        html = generate_player_html(stream_url)

        # The stream URL should appear in the HTML (embedded in JS)
        assert (
            stream_url in html
        ), f"HTML missing stream URL {stream_url} in JavaScript code"

    @given(stream_url=valid_stream_url_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_html_is_valid_document(self, stream_url: str) -> None:
        """For any valid stream URL, HTML SHALL be a complete document.

        **Validates: Requirements 5.4**
        """
        html = generate_player_html(stream_url)

        # Basic HTML document structure
        assert "<!DOCTYPE html>" in html, "HTML missing DOCTYPE declaration"
        assert "<html" in html, "HTML missing <html> tag"
        assert "</html>" in html, "HTML missing closing </html> tag"
        assert "<head>" in html, "HTML missing <head> tag"
        assert "</head>" in html, "HTML missing closing </head> tag"
        assert "<body>" in html, "HTML missing <body> tag"
        assert "</body>" in html, "HTML missing closing </body> tag"

    @given(stream_url=valid_stream_url_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_video_element_has_autoplay_attributes(self, stream_url: str) -> None:
        """For any valid stream URL, video element SHALL have autoplay configuration.

        **Validates: Requirements 5.4**
        """
        html = generate_player_html(stream_url)

        # The video element should have autoplay and muted attributes
        # (required for browser autoplay policies)
        assert "autoplay" in html, "HTML video element missing autoplay attribute"
        assert "muted" in html, "HTML video element missing muted attribute"

    @given(stream_url=valid_stream_url_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_html_contains_error_handling(self, stream_url: str) -> None:
        """For any valid stream URL, HTML SHALL include error overlay.

        **Validates: Requirements 5.4**
        """
        html = generate_player_html(stream_url)

        # The HTML should contain error handling elements
        assert (
            "error" in html.lower()
        ), "HTML missing error handling elements"

    @given(stream_url=simple_stream_urls)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_all_required_elements_combined(self, stream_url: str) -> None:
        """Verify all Property 8 requirements are met in a single test.

        **Validates: Requirements 5.4**

        Property 8: Player HTML template contains required elements
        *For any* valid stream URL string, `generate_player_html(stream_url)` SHALL
        produce an HTML document containing: a `<video>` element, a reference to
        hls.js (script tag), and the stream URL embedded in the JavaScript
        initialization code.
        """
        html = generate_player_html(stream_url)

        # 1. HTML contains <video> element
        assert "<video" in html and "</video>" in html, (
            "Property 8 violation: HTML missing <video> element"
        )

        # 2. HTML contains hls.js script tag reference
        assert "<script" in html and "hls.js" in html.lower(), (
            "Property 8 violation: HTML missing hls.js script reference"
        )

        # 3. Stream URL is embedded in JavaScript initialization code
        assert stream_url in html, (
            f"Property 8 violation: Stream URL {stream_url} not embedded in JS code"
        )


class TestPlayerHtmlEdgeCases:
    """Edge case tests for generate_player_html().

    These tests cover specific edge cases that complement the property-based tests.
    """

    def test_url_with_special_characters_in_path(self) -> None:
        """URLs with special path characters should be embedded correctly."""
        stream_url = "http://192.168.1.1:8080/my-stream_v2.m3u8"
        html = generate_player_html(stream_url)

        assert stream_url in html
        assert "<video" in html
        assert "hls.js" in html.lower()

    def test_url_with_minimum_port(self) -> None:
        """URL with port 1 should work."""
        stream_url = "http://10.0.0.1:1/stream.m3u8"
        html = generate_player_html(stream_url)

        assert stream_url in html
        assert "<video" in html

    def test_url_with_maximum_port(self) -> None:
        """URL with port 65535 should work."""
        stream_url = "http://10.0.0.1:65535/stream.m3u8"
        html = generate_player_html(stream_url)

        assert stream_url in html
        assert "<video" in html

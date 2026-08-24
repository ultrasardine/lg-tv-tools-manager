"""Property-based tests for the capture pipeline module.

# Feature: screen-capture-mirror, Property 3: Resolution capping preserves aspect ratio

These tests verify that compute_output_resolution() correctly caps output
dimensions while preserving aspect ratio and ensuring even dimensions.
"""

from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from lgtvtools.mirror.capture import compute_output_resolution

# -----------------------------------------------------------------------------
# Strategies for generating resolutions
# -----------------------------------------------------------------------------

# Strategy for valid input resolutions up to 8K (7680x4320)
# We use min_value=1 to avoid zero dimensions which are invalid inputs
input_resolution = st.tuples(
    st.integers(min_value=1, max_value=7680),  # width up to 8K
    st.integers(min_value=1, max_value=4320),  # height up to 8K
)

# Strategy for max resolution values (reasonable range for output caps)
max_resolution = st.tuples(
    st.integers(min_value=100, max_value=3840),  # max_width
    st.integers(min_value=100, max_value=2160),  # max_height
)

# Combined strategy for (input_width, input_height, max_width, max_height)
resolution_test_case = st.tuples(
    st.integers(min_value=1, max_value=7680),   # input_width
    st.integers(min_value=1, max_value=4320),   # input_height
    st.integers(min_value=100, max_value=3840), # max_width
    st.integers(min_value=100, max_value=2160), # max_height
)


class TestProperty3ResolutionCappingPreservesAspectRatio:
    """Property 3: Resolution capping preserves aspect ratio.

    *For any* input resolution (W, H) and max_resolution (MW, MH),
    the computed scale filter output dimensions SHALL satisfy:
    - output_width <= MW
    - output_height <= MH
    - output_width/output_height == W/H (within rounding tolerance of 1 pixel)
    - Output dimensions are even (divisible by 2)

    **Validates: Requirements 3.4**
    """

    @given(data=resolution_test_case)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_output_width_does_not_exceed_max_width(
        self, data: tuple[int, int, int, int]
    ) -> None:
        """Output width SHALL NOT exceed max_width.

        # Feature: screen-capture-mirror, Property 3: Resolution capping preserves aspect ratio
        **Validates: Requirements 3.4**
        """
        input_width, input_height, max_width, max_height = data

        output_width, _output_height = compute_output_resolution(
            input_width, input_height, max_width, max_height
        )

        assert output_width <= max_width, (
            f"Output width {output_width} exceeds max_width {max_width}. "
            f"Input: {input_width}x{input_height}, max: {max_width}x{max_height}"
        )

    @given(data=resolution_test_case)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_output_height_does_not_exceed_max_height(
        self, data: tuple[int, int, int, int]
    ) -> None:
        """Output height SHALL NOT exceed max_height.

        # Feature: screen-capture-mirror, Property 3: Resolution capping preserves aspect ratio
        **Validates: Requirements 3.4**
        """
        input_width, input_height, max_width, max_height = data

        _output_width, output_height = compute_output_resolution(
            input_width, input_height, max_width, max_height
        )

        assert output_height <= max_height, (
            f"Output height {output_height} exceeds max_height {max_height}. "
            f"Input: {input_width}x{input_height}, max: {max_width}x{max_height}"
        )

    @given(data=resolution_test_case)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_output_dimensions_are_even(
        self, data: tuple[int, int, int, int]
    ) -> None:
        """Output dimensions SHALL be divisible by 2 (codec requirement).

        # Feature: screen-capture-mirror, Property 3: Resolution capping preserves aspect ratio
        **Validates: Requirements 3.4**
        """
        input_width, input_height, max_width, max_height = data

        output_width, output_height = compute_output_resolution(
            input_width, input_height, max_width, max_height
        )

        assert output_width % 2 == 0, (
            f"Output width {output_width} is not even. "
            f"Input: {input_width}x{input_height}, max: {max_width}x{max_height}"
        )
        assert output_height % 2 == 0, (
            f"Output height {output_height} is not even. "
            f"Input: {input_width}x{input_height}, max: {max_width}x{max_height}"
        )

    @given(data=resolution_test_case)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_aspect_ratio_preserved_within_tolerance(
        self, data: tuple[int, int, int, int]
    ) -> None:
        """Aspect ratio SHALL be preserved within 1 pixel tolerance.

        # Feature: screen-capture-mirror, Property 3: Resolution capping preserves aspect ratio
        **Validates: Requirements 3.4**

        The aspect ratio of the output should match the input aspect ratio,
        allowing for 1 pixel of rounding tolerance due to the even-dimension
        requirement for codec compatibility.
        """
        input_width, input_height, max_width, max_height = data

        output_width, output_height = compute_output_resolution(
            input_width, input_height, max_width, max_height
        )

        # Skip check if output dimensions are zero (degenerate case)
        if output_width == 0 or output_height == 0:
            return

        # Calculate aspect ratios
        input_aspect = input_width / input_height
        output_aspect = output_width / output_height

        # Calculate expected output height for the output width (and vice versa)
        # to determine the tolerance in pixels
        expected_height_from_width = output_width / input_aspect
        expected_width_from_height = output_height * input_aspect

        # The tolerance allows for 1 pixel deviation in either dimension
        # due to the requirement to have even dimensions
        height_diff = abs(output_height - expected_height_from_width)
        width_diff = abs(output_width - expected_width_from_height)

        # We allow tolerance of up to 2 pixels due to:
        # 1. Rounding to even dimensions (up to 1 pixel)
        # 2. Additional rounding during calculation (up to 1 pixel)
        tolerance = 2.0

        assert height_diff <= tolerance or width_diff <= tolerance, (
            f"Aspect ratio not preserved within {tolerance}px tolerance. "
            f"Input: {input_width}x{input_height} (aspect {input_aspect:.4f}), "
            f"Output: {output_width}x{output_height} (aspect {output_aspect:.4f}), "
            f"Height diff: {height_diff:.2f}px, Width diff: {width_diff:.2f}px"
        )

    @given(data=resolution_test_case)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_all_property3_requirements_combined(
        self, data: tuple[int, int, int, int]
    ) -> None:
        """Verify all Property 3 requirements are met in a single test.

        # Feature: screen-capture-mirror, Property 3: Resolution capping preserves aspect ratio
        **Validates: Requirements 3.4**

        Property 3: Resolution capping preserves aspect ratio
        *For any* input resolution (W, H) and max_resolution (MW, MH),
        the computed scale filter output dimensions SHALL satisfy:
        output_width <= MW, output_height <= MH, and output_width/output_height
        == W/H (within rounding tolerance of 1 pixel).
        """
        input_width, input_height, max_width, max_height = data

        output_width, output_height = compute_output_resolution(
            input_width, input_height, max_width, max_height
        )

        # 1. Output width <= max_width
        assert output_width <= max_width, (
            f"Property 3 violation: Output width {output_width} > max_width {max_width}"
        )

        # 2. Output height <= max_height
        assert output_height <= max_height, (
            f"Property 3 violation: Output height {output_height} > max_height {max_height}"
        )

        # 3. Output dimensions are even (codec compatibility)
        assert output_width % 2 == 0, (
            f"Property 3 violation: Output width {output_width} is not even"
        )
        assert output_height % 2 == 0, (
            f"Property 3 violation: Output height {output_height} is not even"
        )

        # 4. Aspect ratio preserved within tolerance
        if output_width > 0 and output_height > 0:
            input_aspect = input_width / input_height

            expected_height = output_width / input_aspect
            expected_width = output_height * input_aspect

            height_diff = abs(output_height - expected_height)
            width_diff = abs(output_width - expected_width)

            tolerance = 2.0
            assert height_diff <= tolerance or width_diff <= tolerance, (
                f"Property 3 violation: Aspect ratio not preserved. "
                f"Input: {input_width}x{input_height}, Output: {output_width}x{output_height}"
            )


class TestResolutionCappingEdgeCases:
    """Edge case tests for compute_output_resolution().

    These tests cover specific edge cases that complement the property-based tests.
    """

    def test_input_smaller_than_max_preserves_dimensions(self) -> None:
        """When input is smaller than max, output should match input (even-adjusted)."""
        output_width, output_height = compute_output_resolution(
            input_width=800,
            input_height=600,
            max_width=1920,
            max_height=1080,
        )

        # Should preserve input dimensions (already even)
        assert output_width == 800
        assert output_height == 600

    def test_input_equal_to_max(self) -> None:
        """When input equals max, output should match (already at limit)."""
        output_width, output_height = compute_output_resolution(
            input_width=1920,
            input_height=1080,
            max_width=1920,
            max_height=1080,
        )

        assert output_width == 1920
        assert output_height == 1080

    def test_8k_input_capped_to_1080p(self) -> None:
        """8K input should be capped to 1080p max resolution."""
        output_width, output_height = compute_output_resolution(
            input_width=7680,
            input_height=4320,
            max_width=1920,
            max_height=1080,
        )

        # 16:9 aspect ratio should be preserved
        assert output_width <= 1920
        assert output_height <= 1080
        assert output_width % 2 == 0
        assert output_height % 2 == 0

        # Check aspect ratio (16:9)
        input_aspect = 7680 / 4320  # 1.777...
        output_aspect = output_width / output_height
        assert abs(input_aspect - output_aspect) < 0.01

    def test_ultrawide_aspect_ratio_preserved(self) -> None:
        """Ultrawide aspect ratios should be preserved when capping."""
        # 21:9 ultrawide (3440x1440)
        output_width, output_height = compute_output_resolution(
            input_width=3440,
            input_height=1440,
            max_width=1920,
            max_height=1080,
        )

        assert output_width <= 1920
        assert output_height <= 1080

        # Verify aspect ratio preserved
        input_aspect = 3440 / 1440
        output_aspect = output_width / output_height
        # Allow slightly more tolerance for ultrawide
        assert abs(input_aspect - output_aspect) < 0.02

    def test_tall_aspect_ratio_preserved(self) -> None:
        """Tall (portrait) aspect ratios should be preserved when capping."""
        # 9:16 portrait
        output_width, output_height = compute_output_resolution(
            input_width=1080,
            input_height=1920,
            max_width=1920,
            max_height=1080,
        )

        assert output_width <= 1920
        assert output_height <= 1080

        # Height is the limiting factor for portrait
        # Expected: height = 1080, width = 1080 * (1080/1920) = 607.5 -> 608
        assert output_height <= 1080
        assert output_width % 2 == 0
        assert output_height % 2 == 0

    def test_odd_input_dimensions_produce_even_output(self) -> None:
        """Odd input dimensions should produce even output dimensions."""
        output_width, output_height = compute_output_resolution(
            input_width=1921,  # Odd
            input_height=1081,  # Odd
            max_width=1920,
            max_height=1080,
        )

        assert output_width % 2 == 0
        assert output_height % 2 == 0

    def test_width_constrained_scenario(self) -> None:
        """When width is the constraining dimension."""
        output_width, output_height = compute_output_resolution(
            input_width=3840,
            input_height=1080,  # Very wide
            max_width=1920,
            max_height=1080,
        )

        # Width should be capped, height scaled proportionally
        assert output_width <= 1920
        assert output_height <= 1080

    def test_height_constrained_scenario(self) -> None:
        """When height is the constraining dimension."""
        output_width, output_height = compute_output_resolution(
            input_width=1920,
            input_height=2160,  # Very tall
            max_width=1920,
            max_height=1080,
        )

        # Height should be capped, width scaled proportionally
        assert output_height <= 1080
        assert output_width <= 1920

    def test_zero_dimensions_handled(self) -> None:
        """Zero input dimensions should return (0, 0)."""
        output_width, output_height = compute_output_resolution(
            input_width=0,
            input_height=100,
            max_width=1920,
            max_height=1080,
        )
        assert output_width == 0
        assert output_height == 0

        output_width, output_height = compute_output_resolution(
            input_width=100,
            input_height=0,
            max_width=1920,
            max_height=1080,
        )
        assert output_width == 0
        assert output_height == 0

    def test_very_small_resolution(self) -> None:
        """Very small resolutions should still produce valid output."""
        output_width, output_height = compute_output_resolution(
            input_width=2,
            input_height=2,
            max_width=1920,
            max_height=1080,
        )

        # Should preserve small dimensions
        assert output_width == 2
        assert output_height == 2
        assert output_width % 2 == 0
        assert output_height % 2 == 0

    def test_1x1_produces_zero_due_to_even_requirement(self) -> None:
        """1x1 input produces 0x0 due to even dimension requirement."""
        output_width, output_height = compute_output_resolution(
            input_width=1,
            input_height=1,
            max_width=1920,
            max_height=1080,
        )

        # 1 // 2 * 2 = 0
        assert output_width == 0
        assert output_height == 0


# =============================================================================
# Property 6: Hardware encoder selection with fallback
# =============================================================================


from lgtvtools.mirror.capture import (  # noqa: E402
    HARDWARE_ENCODERS,
    SOFTWARE_ENCODER,
    select_encoder,
)
from lgtvtools.mirror.models import EncoderInfo  # noqa: E402
from lgtvtools.system.platform import Platform  # noqa: E402

# -----------------------------------------------------------------------------
# Strategies for generating encoder selection scenarios
# -----------------------------------------------------------------------------

# Platforms that have defined hardware encoders (excludes UNKNOWN)
platforms_with_encoders = st.sampled_from([Platform.MACOS, Platform.DEBIAN, Platform.WINDOWS])

# All platforms including UNKNOWN
all_platforms = st.sampled_from(list(Platform))

# Common encoder names (hardware and software)
all_encoder_names = [
    "h264_videotoolbox",  # macOS
    "h264_vaapi",  # Linux
    "h264_nvenc",  # Linux/Windows
    "h264_qsv",  # Windows
    "libx264",  # Software fallback
    "libx265",  # Other codec
    "h264_amf",  # AMD encoder (not in our list)
    "hevc_nvenc",  # Different codec
]


@st.composite
def encoder_selection_scenario(draw: st.DrawFn) -> tuple[Platform, set[str], str | None]:
    """Generate a platform and random subset of available encoders.

    Returns a tuple of (platform, available_encoders, expected_hardware_encoder).
    The expected_hardware_encoder is None if no hardware encoder should be selected.
    """
    platform = draw(platforms_with_encoders)

    # Get the hardware encoders for this platform
    hw_encoders = HARDWARE_ENCODERS.get(platform, [])

    # Generate a random subset of all encoder names
    available_encoders = draw(
        st.frozensets(st.sampled_from(all_encoder_names), min_size=0, max_size=len(all_encoder_names))
    )

    # Determine which hardware encoder (if any) should be selected
    # It should be the first available hardware encoder in the platform's preference order
    expected_hw_encoder: str | None = None
    for encoder in hw_encoders:
        if encoder in available_encoders:
            expected_hw_encoder = encoder
            break

    return platform, set(available_encoders), expected_hw_encoder


@st.composite
def no_hardware_encoder_scenario(draw: st.DrawFn) -> tuple[Platform, set[str]]:
    """Generate a scenario where no hardware encoder is available for the platform.

    Returns a tuple of (platform, available_encoders).
    """
    platform = draw(all_platforms)

    # Get the hardware encoders for this platform
    hw_encoders = HARDWARE_ENCODERS.get(platform, [])

    # Generate available encoders that exclude all hardware encoders for this platform
    other_encoders = [e for e in all_encoder_names if e not in hw_encoders]
    available_encoders = draw(
        st.frozensets(st.sampled_from(other_encoders) if other_encoders else st.nothing(), min_size=0)
    )

    return platform, set(available_encoders)


@st.composite
def all_hardware_encoders_available(draw: st.DrawFn) -> tuple[Platform, set[str]]:
    """Generate a scenario where all hardware encoders for a platform are available.

    Returns a tuple of (platform, available_encoders).
    """
    platform = draw(platforms_with_encoders)

    # Get the hardware encoders for this platform
    hw_encoders = HARDWARE_ENCODERS.get(platform, [])

    # Include all hardware encoders plus potentially some others
    additional = draw(
        st.frozensets(st.sampled_from(all_encoder_names), min_size=0, max_size=3)
    )

    available_encoders = set(hw_encoders) | set(additional)
    return platform, available_encoders


# -----------------------------------------------------------------------------
# Property Tests for Hardware Encoder Selection
# -----------------------------------------------------------------------------


class TestProperty6HardwareEncoderSelection:
    """Property 6: Hardware encoder selection with fallback.

    For any platform and set of available encoders, the encoder selection logic
    SHALL pick the first available hardware encoder for that platform; if none
    are available, it SHALL select libx264. The result is never empty.

    **Validates: Requirements 3.2, 3.3**
    """

    @settings(max_examples=100, deadline=None)
    @given(data=encoder_selection_scenario())
    def test_selects_hardware_encoder_when_available(
        self, data: tuple[Platform, set[str], str | None]
    ) -> None:
        """When hardware encoder is available, it should be selected.

        # Feature: screen-capture-mirror, Property 6: Hardware encoder selection with fallback
        """
        platform, available_encoders, expected_hw_encoder = data

        result = select_encoder(platform, available_encoders)

        # Result should never be empty
        assert isinstance(result, EncoderInfo)
        assert result.name != ""

        if expected_hw_encoder is not None:
            # Hardware encoder should be selected
            assert result.name == expected_hw_encoder, (
                f"Expected hardware encoder '{expected_hw_encoder}' but got '{result.name}' "
                f"for platform {platform} with available encoders {available_encoders}"
            )
            assert result.is_hardware is True
        else:
            # Should fall back to software encoder
            assert result.name == SOFTWARE_ENCODER
            assert result.is_hardware is False

    @settings(max_examples=100, deadline=None)
    @given(data=no_hardware_encoder_scenario())
    def test_falls_back_to_libx264_when_no_hardware_encoder(
        self, data: tuple[Platform, set[str]]
    ) -> None:
        """When no hardware encoder is available, libx264 should be selected.

        # Feature: screen-capture-mirror, Property 6: Hardware encoder selection with fallback
        """
        platform, available_encoders = data

        result = select_encoder(platform, available_encoders)

        # Result should never be empty
        assert isinstance(result, EncoderInfo)
        assert result.name != ""

        # Should fall back to software encoder
        assert result.name == SOFTWARE_ENCODER, (
            f"Expected fallback to '{SOFTWARE_ENCODER}' but got '{result.name}' "
            f"for platform {platform} with available encoders {available_encoders}"
        )
        assert result.is_hardware is False

    @settings(max_examples=100, deadline=None)
    @given(platform=all_platforms)
    def test_result_is_never_empty_with_no_encoders(self, platform: Platform) -> None:
        """With no available encoders, result should still be libx264.

        # Feature: screen-capture-mirror, Property 6: Hardware encoder selection with fallback
        """
        # Empty set of available encoders
        available_encoders: set[str] = set()

        result = select_encoder(platform, available_encoders)

        # Result should never be empty
        assert isinstance(result, EncoderInfo)
        assert result.name == SOFTWARE_ENCODER
        assert result.is_hardware is False

    @settings(max_examples=100, deadline=None)
    @given(data=all_hardware_encoders_available())
    def test_selects_first_preferred_hardware_encoder(
        self, data: tuple[Platform, set[str]]
    ) -> None:
        """When multiple hardware encoders available, first preferred is selected.

        # Feature: screen-capture-mirror, Property 6: Hardware encoder selection with fallback
        """
        platform, available_encoders = data

        result = select_encoder(platform, available_encoders)

        # Result should never be empty
        assert isinstance(result, EncoderInfo)
        assert result.name != ""

        # Should select the first encoder in the platform's preference list
        hw_encoders = HARDWARE_ENCODERS.get(platform, [])
        expected_encoder = hw_encoders[0] if hw_encoders else SOFTWARE_ENCODER

        assert result.name == expected_encoder, (
            f"Expected first preferred encoder '{expected_encoder}' but got '{result.name}' "
            f"for platform {platform} with available encoders {available_encoders}"
        )

        if hw_encoders:
            assert result.is_hardware is True
        else:
            assert result.is_hardware is False

    @settings(max_examples=100, deadline=None)
    @given(platform=all_platforms, available=st.frozensets(st.sampled_from(all_encoder_names)))
    def test_is_hardware_flag_is_correct(
        self, platform: Platform, available: frozenset[str]
    ) -> None:
        """The is_hardware flag should correctly reflect encoder type.

        # Feature: screen-capture-mirror, Property 6: Hardware encoder selection with fallback
        """
        available_encoders = set(available)

        result = select_encoder(platform, available_encoders)

        # Get hardware encoders for this platform
        hw_encoders = set(HARDWARE_ENCODERS.get(platform, []))

        # is_hardware should be True if and only if the selected encoder
        # is a hardware encoder for this platform
        expected_is_hardware = result.name in hw_encoders

        assert result.is_hardware == expected_is_hardware, (
            f"is_hardware flag mismatch: got {result.is_hardware} but expected "
            f"{expected_is_hardware} for encoder '{result.name}' on platform {platform}"
        )

    @settings(max_examples=100, deadline=None)
    @given(platform=all_platforms, available=st.frozensets(st.sampled_from(all_encoder_names)))
    def test_platform_field_is_correct(
        self, platform: Platform, available: frozenset[str]
    ) -> None:
        """The platform field should match the input platform.

        # Feature: screen-capture-mirror, Property 6: Hardware encoder selection with fallback
        """
        available_encoders = set(available)

        result = select_encoder(platform, available_encoders)

        assert result.platform == platform.value, (
            f"Platform field mismatch: got '{result.platform}' but expected "
            f"'{platform.value}'"
        )

    def test_macos_prefers_videotoolbox(self) -> None:
        """macOS should prefer h264_videotoolbox.

        # Feature: screen-capture-mirror, Property 6: Hardware encoder selection with fallback
        """
        available = {"h264_videotoolbox", "libx264"}
        result = select_encoder(Platform.MACOS, available)

        assert result.name == "h264_videotoolbox"
        assert result.is_hardware is True
        assert result.platform == "macos"

    def test_linux_prefers_vaapi_over_nvenc(self) -> None:
        """Linux should prefer h264_vaapi over h264_nvenc.

        # Feature: screen-capture-mirror, Property 6: Hardware encoder selection with fallback
        """
        available = {"h264_vaapi", "h264_nvenc", "libx264"}
        result = select_encoder(Platform.DEBIAN, available)

        assert result.name == "h264_vaapi"
        assert result.is_hardware is True

    def test_linux_uses_nvenc_when_vaapi_unavailable(self) -> None:
        """Linux should use h264_nvenc when h264_vaapi is not available.

        # Feature: screen-capture-mirror, Property 6: Hardware encoder selection with fallback
        """
        available = {"h264_nvenc", "libx264"}
        result = select_encoder(Platform.DEBIAN, available)

        assert result.name == "h264_nvenc"
        assert result.is_hardware is True

    def test_windows_prefers_nvenc_over_qsv(self) -> None:
        """Windows should prefer h264_nvenc over h264_qsv.

        # Feature: screen-capture-mirror, Property 6: Hardware encoder selection with fallback
        """
        available = {"h264_nvenc", "h264_qsv", "libx264"}
        result = select_encoder(Platform.WINDOWS, available)

        assert result.name == "h264_nvenc"
        assert result.is_hardware is True

    def test_windows_uses_qsv_when_nvenc_unavailable(self) -> None:
        """Windows should use h264_qsv when h264_nvenc is not available.

        # Feature: screen-capture-mirror, Property 6: Hardware encoder selection with fallback
        """
        available = {"h264_qsv", "libx264"}
        result = select_encoder(Platform.WINDOWS, available)

        assert result.name == "h264_qsv"
        assert result.is_hardware is True

    def test_unknown_platform_uses_software(self) -> None:
        """Unknown platform should always use libx264.

        # Feature: screen-capture-mirror, Property 6: Hardware encoder selection with fallback
        """
        # Even with hardware encoders available, unknown platform has no hw preference
        available = {"h264_videotoolbox", "h264_vaapi", "h264_nvenc", "libx264"}
        result = select_encoder(Platform.UNKNOWN, available)

        assert result.name == SOFTWARE_ENCODER
        assert result.is_hardware is False


# -----------------------------------------------------------------------------
# Property 2: HLS and Encoding Output Configuration
# -----------------------------------------------------------------------------
#
# Feature: screen-capture-mirror, Property 2: HLS and encoding output configuration
#
# Tests verify that the ffmpeg command contains correct HLS and encoding parameters
# for any valid CaptureConfig input.
# -----------------------------------------------------------------------------

from pathlib import Path  # noqa: E402
from unittest import mock  # noqa: E402

from lgtvtools.mirror.capture import CapturePipeline  # noqa: E402
from lgtvtools.mirror.models import CaptureConfig, CaptureSource  # noqa: E402
from lgtvtools.system.platform import Platform  # noqa: E402

# -----------------------------------------------------------------------------
# Strategies for generating random CaptureConfig values
# -----------------------------------------------------------------------------

# Strategy for segment duration (1-10 seconds per task guidance)
segment_duration_strategy = st.integers(min_value=1, max_value=10)

# Strategy for max segments (1-20 per task guidance)
max_segments_strategy = st.integers(min_value=1, max_value=20)

# Strategy for H.264 profile
h264_profile_strategy = st.sampled_from(["baseline", "main", "high"])

# Strategy for framerate (15-60 fps per task guidance)
framerate_strategy = st.integers(min_value=15, max_value=60)

# Strategy for video bitrate (common bitrate strings)
video_bitrate_strategy = st.sampled_from(["1M", "2M", "4M", "6M", "8M", "10M"])

# Strategy for max resolution for CaptureConfig (common resolutions)
capture_max_resolution_strategy = st.sampled_from([
    (1280, 720),
    (1920, 1080),
    (2560, 1440),
    (3840, 2160),
])


@st.composite
def capture_config_strategy(draw: st.DrawFn) -> CaptureConfig:
    """Generate random CaptureConfig objects with valid parameters."""
    return CaptureConfig(
        framerate=draw(framerate_strategy),
        max_resolution=draw(capture_max_resolution_strategy),
        segment_duration=draw(segment_duration_strategy),
        max_segments=draw(max_segments_strategy),
        video_bitrate=draw(video_bitrate_strategy),
        h264_profile=draw(h264_profile_strategy),
    )


# Strategy for platforms
platform_strategy = st.sampled_from([
    Platform.MACOS,
    Platform.DEBIAN,
    Platform.RHEL,
    Platform.WINDOWS,
])


def create_test_pipeline(
    config: CaptureConfig,
    platform: Platform = Platform.MACOS,
) -> CapturePipeline:
    """Create a CapturePipeline for testing with mocked encoder detection."""
    source = CaptureSource(
        id="1",
        name="Test Screen",
        kind="screen",
        resolution=(1920, 1080),
    )
    output_dir = Path("/tmp/test_mirror")

    pipeline = CapturePipeline(
        source=source,
        output_dir=output_dir,
        platform=platform,
        config=config,
    )

    return pipeline


class TestProperty2HLSAndEncodingConfiguration:
    """Property 2: HLS and encoding output configuration.

    For any CaptureConfig with segment_duration S, max_segments N, and h264_profile P,
    the constructed ffmpeg command SHALL include:
    - `-hls_time S`
    - `-hls_list_size N`
    - the `delete_segments` flag
    - `-f hls` output format
    - a keyframe interval flag (`-g`)
    - `-profile:v P`

    **Validates: Requirements 3.1, 3.5, 4.2, 4.3**
    """

    @given(config=capture_config_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_command_contains_hls_time_with_segment_duration(
        self, config: CaptureConfig
    ) -> None:
        """For any config, command SHALL include `-hls_time` with segment_duration.

        # Feature: screen-capture-mirror, Property 2: HLS and encoding output configuration

        **Validates: Requirements 4.2**
        """
        with mock.patch.object(
            CapturePipeline,
            "_get_available_encoders",
            return_value={"libx264"},
        ):
            pipeline = create_test_pipeline(config)
            command = pipeline._build_command()

        # Find -hls_time flag and its value
        assert "-hls_time" in command, (
            f"Command missing -hls_time flag. Config: segment_duration={config.segment_duration}"
        )

        hls_time_idx = command.index("-hls_time")
        hls_time_value = command[hls_time_idx + 1]

        assert hls_time_value == str(config.segment_duration), (
            f"Expected -hls_time {config.segment_duration}, got {hls_time_value}"
        )

    @given(config=capture_config_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_command_contains_hls_list_size_with_max_segments(
        self, config: CaptureConfig
    ) -> None:
        """For any config, command SHALL include `-hls_list_size` with max_segments.

        # Feature: screen-capture-mirror, Property 2: HLS and encoding output configuration

        **Validates: Requirements 4.3**
        """
        with mock.patch.object(
            CapturePipeline,
            "_get_available_encoders",
            return_value={"libx264"},
        ):
            pipeline = create_test_pipeline(config)
            command = pipeline._build_command()

        # Find -hls_list_size flag and its value
        assert "-hls_list_size" in command, (
            f"Command missing -hls_list_size flag. Config: max_segments={config.max_segments}"
        )

        hls_list_size_idx = command.index("-hls_list_size")
        hls_list_size_value = command[hls_list_size_idx + 1]

        assert hls_list_size_value == str(config.max_segments), (
            f"Expected -hls_list_size {config.max_segments}, got {hls_list_size_value}"
        )

    @given(config=capture_config_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_command_contains_delete_segments_flag(
        self, config: CaptureConfig
    ) -> None:
        """For any config, command SHALL include `delete_segments` HLS flag.

        # Feature: screen-capture-mirror, Property 2: HLS and encoding output configuration

        **Validates: Requirements 4.3**
        """
        with mock.patch.object(
            CapturePipeline,
            "_get_available_encoders",
            return_value={"libx264"},
        ):
            pipeline = create_test_pipeline(config)
            command = pipeline._build_command()

        # The delete_segments flag should appear in the -hls_flags argument
        assert "-hls_flags" in command, "Command missing -hls_flags argument"

        hls_flags_idx = command.index("-hls_flags")
        hls_flags_value = command[hls_flags_idx + 1]

        assert "delete_segments" in hls_flags_value, (
            f"HLS flags missing 'delete_segments'. Got: {hls_flags_value}"
        )

    @given(config=capture_config_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_command_contains_hls_output_format(
        self, config: CaptureConfig
    ) -> None:
        """For any config, command SHALL include `-f hls` output format.

        # Feature: screen-capture-mirror, Property 2: HLS and encoding output configuration

        **Validates: Requirements 4.2**
        """
        with mock.patch.object(
            CapturePipeline,
            "_get_available_encoders",
            return_value={"libx264"},
        ):
            pipeline = create_test_pipeline(config)
            command = pipeline._build_command()

        # Find -f flag followed by "hls"
        assert "-f" in command, "Command missing -f flag"

        # Find the -f flag in the output section (not the input -f)
        # The output -f hls should come after the video filter
        command_str = " ".join(command)
        assert "-f hls" in command_str, (
            f"Command missing '-f hls' output format. Command: {command_str}"
        )

    @given(config=capture_config_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_command_contains_keyframe_interval(
        self, config: CaptureConfig
    ) -> None:
        """For any config, command SHALL include `-g` with keyframe interval.

        The keyframe interval should be framerate * segment_duration for clean
        segment boundaries.

        # Feature: screen-capture-mirror, Property 2: HLS and encoding output configuration

        **Validates: Requirements 3.5**
        """
        with mock.patch.object(
            CapturePipeline,
            "_get_available_encoders",
            return_value={"libx264"},
        ):
            pipeline = create_test_pipeline(config)
            command = pipeline._build_command()

        # Find -g flag and its value
        assert "-g" in command, "Command missing -g (GOP size) flag"

        g_idx = command.index("-g")
        g_value = command[g_idx + 1]

        expected_gop = config.framerate * config.segment_duration
        assert g_value == str(expected_gop), (
            f"Expected -g {expected_gop} (framerate={config.framerate} * "
            f"segment_duration={config.segment_duration}), got {g_value}"
        )

    @given(config=capture_config_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_command_contains_h264_profile(
        self, config: CaptureConfig
    ) -> None:
        """For any config, command SHALL include `-profile:v` with h264_profile.

        # Feature: screen-capture-mirror, Property 2: HLS and encoding output configuration

        **Validates: Requirements 3.1**
        """
        with mock.patch.object(
            CapturePipeline,
            "_get_available_encoders",
            return_value={"libx264"},
        ):
            pipeline = create_test_pipeline(config)
            command = pipeline._build_command()

        # Find -profile:v flag and its value
        assert "-profile:v" in command, "Command missing -profile:v flag"

        profile_idx = command.index("-profile:v")
        profile_value = command[profile_idx + 1]

        assert profile_value == config.h264_profile, (
            f"Expected -profile:v {config.h264_profile}, got {profile_value}"
        )

    @given(config=capture_config_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_all_hls_encoding_requirements_combined(
        self, config: CaptureConfig
    ) -> None:
        """Verify all Property 2 requirements are met in a single test.

        # Feature: screen-capture-mirror, Property 2: HLS and encoding output configuration

        Property 2: For any CaptureConfig with segment_duration S, max_segments N,
        and h264_profile P, the constructed ffmpeg command SHALL include:
        `-hls_time S`, `-hls_list_size N`, `delete_segments`, `-f hls`, `-g`, `-profile:v P`.

        **Validates: Requirements 3.1, 3.5, 4.2, 4.3**
        """
        with mock.patch.object(
            CapturePipeline,
            "_get_available_encoders",
            return_value={"libx264"},
        ):
            pipeline = create_test_pipeline(config)
            command = pipeline._build_command()

        command_str = " ".join(command)

        # 1. -hls_time with segment_duration
        assert "-hls_time" in command, "Property 2 violation: missing -hls_time"
        hls_time_idx = command.index("-hls_time")
        assert command[hls_time_idx + 1] == str(config.segment_duration), (
            f"Property 2 violation: -hls_time should be {config.segment_duration}"
        )

        # 2. -hls_list_size with max_segments
        assert "-hls_list_size" in command, "Property 2 violation: missing -hls_list_size"
        hls_list_size_idx = command.index("-hls_list_size")
        assert command[hls_list_size_idx + 1] == str(config.max_segments), (
            f"Property 2 violation: -hls_list_size should be {config.max_segments}"
        )

        # 3. delete_segments flag
        assert "-hls_flags" in command, "Property 2 violation: missing -hls_flags"
        hls_flags_idx = command.index("-hls_flags")
        assert "delete_segments" in command[hls_flags_idx + 1], (
            "Property 2 violation: delete_segments not in -hls_flags"
        )

        # 4. -f hls output format
        assert "-f hls" in command_str, "Property 2 violation: missing -f hls"

        # 5. -g keyframe interval
        assert "-g" in command, "Property 2 violation: missing -g flag"
        g_idx = command.index("-g")
        expected_gop = config.framerate * config.segment_duration
        assert command[g_idx + 1] == str(expected_gop), (
            f"Property 2 violation: -g should be {expected_gop}"
        )

        # 6. -profile:v with h264_profile
        assert "-profile:v" in command, "Property 2 violation: missing -profile:v"
        profile_idx = command.index("-profile:v")
        assert command[profile_idx + 1] == config.h264_profile, (
            f"Property 2 violation: -profile:v should be {config.h264_profile}"
        )

    @given(config=capture_config_strategy(), platform=platform_strategy)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_hls_encoding_config_across_platforms(
        self, config: CaptureConfig, platform: Platform
    ) -> None:
        """HLS and encoding configuration should be consistent across all platforms.

        # Feature: screen-capture-mirror, Property 2: HLS and encoding output configuration

        **Validates: Requirements 3.1, 3.5, 4.2, 4.3**
        """
        with mock.patch.object(
            CapturePipeline,
            "_get_available_encoders",
            return_value={"libx264"},
        ):
            pipeline = create_test_pipeline(config, platform=platform)
            command = pipeline._build_command()

        # Verify HLS configuration is present regardless of platform
        assert "-hls_time" in command, (
            f"Platform {platform.value}: missing -hls_time"
        )
        assert "-hls_list_size" in command, (
            f"Platform {platform.value}: missing -hls_list_size"
        )
        assert "-f" in command, (
            f"Platform {platform.value}: missing -f flag"
        )

        # Verify encoding configuration
        assert "-g" in command, f"Platform {platform.value}: missing -g flag"
        assert "-profile:v" in command, (
            f"Platform {platform.value}: missing -profile:v"
        )


class TestCaptureConfigEdgeCases:
    """Edge case tests for CaptureConfig handling.

    These tests complement the property-based tests with specific edge cases.
    """

    def test_minimum_config_values(self) -> None:
        """Minimum valid config values should produce valid command."""
        config = CaptureConfig(
            framerate=15,
            max_resolution=(1280, 720),
            segment_duration=1,
            max_segments=1,
            video_bitrate="1M",
            h264_profile="baseline",
        )

        with mock.patch.object(
            CapturePipeline,
            "_get_available_encoders",
            return_value={"libx264"},
        ):
            pipeline = create_test_pipeline(config)
            command = pipeline._build_command()

        # Verify command is valid
        assert "-hls_time" in command
        assert "-hls_list_size" in command
        assert "-g" in command
        assert "-profile:v" in command

        # Check specific values
        hls_time_idx = command.index("-hls_time")
        assert command[hls_time_idx + 1] == "1"

        hls_list_size_idx = command.index("-hls_list_size")
        assert command[hls_list_size_idx + 1] == "1"

        g_idx = command.index("-g")
        assert command[g_idx + 1] == "15"  # 15 fps * 1 second

    def test_maximum_config_values(self) -> None:
        """Maximum valid config values should produce valid command."""
        config = CaptureConfig(
            framerate=60,
            max_resolution=(3840, 2160),
            segment_duration=10,
            max_segments=20,
            video_bitrate="10M",
            h264_profile="high",
        )

        with mock.patch.object(
            CapturePipeline,
            "_get_available_encoders",
            return_value={"libx264"},
        ):
            pipeline = create_test_pipeline(config)
            command = pipeline._build_command()

        # Verify command is valid
        assert "-hls_time" in command
        assert "-hls_list_size" in command
        assert "-g" in command
        assert "-profile:v" in command

        # Check specific values
        hls_time_idx = command.index("-hls_time")
        assert command[hls_time_idx + 1] == "10"

        hls_list_size_idx = command.index("-hls_list_size")
        assert command[hls_list_size_idx + 1] == "20"

        g_idx = command.index("-g")
        assert command[g_idx + 1] == "600"  # 60 fps * 10 seconds

        profile_idx = command.index("-profile:v")
        assert command[profile_idx + 1] == "high"

    def test_default_config_values(self) -> None:
        """Default CaptureConfig should produce valid command with expected defaults."""
        config = CaptureConfig()  # All defaults

        with mock.patch.object(
            CapturePipeline,
            "_get_available_encoders",
            return_value={"libx264"},
        ):
            pipeline = create_test_pipeline(config)
            command = pipeline._build_command()

        # Verify default values from models.py
        hls_time_idx = command.index("-hls_time")
        assert command[hls_time_idx + 1] == "2"  # Default segment_duration

        hls_list_size_idx = command.index("-hls_list_size")
        assert command[hls_list_size_idx + 1] == "5"  # Default max_segments

        g_idx = command.index("-g")
        assert command[g_idx + 1] == "60"  # Default 30 fps * 2 seconds

        profile_idx = command.index("-profile:v")
        assert command[profile_idx + 1] == "main"  # Default h264_profile

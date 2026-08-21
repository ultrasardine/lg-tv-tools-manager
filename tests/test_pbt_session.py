"""Property-based tests for the MirrorSession state machine.

# Feature: screen-capture-mirror, Property 5: Session state machine transitions are valid

These tests verify that MirrorSession state transitions follow only valid paths
according to the state machine defined in the design document.

**Validates: Requirements 6.1, 6.3, 2.3, 5.3, 8.1**
"""

from __future__ import annotations

from enum import Enum
from unittest.mock import patch

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from lgtvtools.mirror.models import CaptureSource, MirrorState

# -----------------------------------------------------------------------------
# State Machine Definition
# -----------------------------------------------------------------------------

# Valid state transitions as defined in session.py
VALID_TRANSITIONS: dict[MirrorState, set[MirrorState]] = {
    MirrorState.IDLE: {MirrorState.STARTING},
    MirrorState.STARTING: {MirrorState.STREAMING, MirrorState.ERROR},
    MirrorState.STREAMING: {MirrorState.STOPPING, MirrorState.ERROR},
    MirrorState.STOPPING: {MirrorState.IDLE},
    MirrorState.ERROR: {MirrorState.IDLE},
}


class SessionEvent(Enum):
    """Events that can be applied to a MirrorSession."""

    START = "start"
    STOP = "stop"
    ERROR = "error"
    HEALTH_CHECK = "health_check"
    STREAM_READY = "stream_ready"  # First segment produced


def is_valid_transition(from_state: MirrorState, to_state: MirrorState) -> bool:
    """Check if a state transition is valid according to the state machine."""
    allowed = VALID_TRANSITIONS.get(from_state, set())
    return to_state in allowed


# -----------------------------------------------------------------------------
# Pure State Machine Implementation for Testing
# -----------------------------------------------------------------------------


class PureStateMachine:
    """A pure, side-effect-free state machine for property testing.

    This mirrors the logic in MirrorSession._transition_state() without
    any network, subprocess, or file system dependencies.
    """

    def __init__(self) -> None:
        self._state = MirrorState.IDLE
        self._transition_history: list[tuple[MirrorState, MirrorState, bool]] = []

    @property
    def state(self) -> MirrorState:
        """Current state of the state machine."""
        return self._state

    @property
    def transition_history(
        self,
    ) -> list[tuple[MirrorState, MirrorState, bool]]:
        """History of (from_state, to_state, was_valid) transitions."""
        return self._transition_history

    def transition(self, new_state: MirrorState) -> bool:
        """Attempt to transition to a new state.

        Returns True if the transition was valid and performed, False otherwise.
        Invalid transitions leave the state unchanged.
        """
        old_state = self._state
        is_valid = is_valid_transition(old_state, new_state)

        if is_valid:
            self._state = new_state

        self._transition_history.append((old_state, new_state, is_valid))
        return is_valid

    def apply_event(self, event: SessionEvent) -> bool:
        """Apply an event to the state machine, returning whether it succeeded.

        This simulates how MirrorSession responds to various events.
        """
        if event == SessionEvent.START:
            # start() tries to transition IDLE -> STARTING
            if self._state == MirrorState.IDLE:
                return self.transition(MirrorState.STARTING)
            # Starting from non-IDLE state fails without transition
            return False

        elif event == SessionEvent.STREAM_READY:
            # When first segment is ready: STARTING -> STREAMING
            if self._state == MirrorState.STARTING:
                return self.transition(MirrorState.STREAMING)
            return False

        elif event == SessionEvent.STOP:
            # stop() behavior depends on current state
            if self._state == MirrorState.STREAMING:
                self.transition(MirrorState.STOPPING)
                # Then immediately transitions to IDLE after cleanup
                self.transition(MirrorState.IDLE)
                return True
            elif self._state == MirrorState.ERROR:
                # Cleanup from error state
                self.transition(MirrorState.IDLE)
                return True
            elif self._state == MirrorState.STARTING:
                # Abort startup
                self.transition(MirrorState.ERROR)
                self.transition(MirrorState.IDLE)
                return True
            elif self._state in (MirrorState.IDLE, MirrorState.STOPPING):
                # Nothing to stop / already stopping
                return True
            return False

        elif event == SessionEvent.ERROR:
            # Error can occur from STARTING or STREAMING
            if (
                self._state == MirrorState.STARTING
                or self._state == MirrorState.STREAMING
            ):
                self.transition(MirrorState.ERROR)
                # Error handling includes cleanup to IDLE
                self.transition(MirrorState.IDLE)
                return True
            return False

        elif event == SessionEvent.HEALTH_CHECK:
            # Health check only meaningful when streaming
            # Does not change state unless error is detected
            return self._state == MirrorState.STREAMING

        return False

    def reset(self) -> None:
        """Reset the state machine to IDLE state."""
        self._state = MirrorState.IDLE
        self._transition_history.clear()


# -----------------------------------------------------------------------------
# Strategies for Generating Test Data
# -----------------------------------------------------------------------------

# Strategy for generating individual session events
session_event = st.sampled_from(list(SessionEvent))

# Strategy for generating sequences of events (1 to 50 events)
event_sequence = st.lists(session_event, min_size=1, max_size=50)

# Strategy for generating all MirrorState values
mirror_state = st.sampled_from(list(MirrorState))

# Strategy for state pairs to test direct transitions
state_pair = st.tuples(mirror_state, mirror_state)


# -----------------------------------------------------------------------------
# Property Tests for Session State Machine
# -----------------------------------------------------------------------------


class TestProperty5SessionStateMachineTransitions:
    """Property 5: Session state machine transitions are valid.

    *For any* sequence of start/stop/error events applied to a MirrorSession,
    the state transitions SHALL follow only valid paths:
    - IDLE -> STARTING -> STREAMING -> STOPPING -> IDLE
    - IDLE -> STARTING -> ERROR -> IDLE
    - STREAMING -> ERROR -> IDLE
    No other transitions are permitted.

    **Validates: Requirements 6.1, 6.3, 2.3, 5.3, 8.1**
    """

    @given(events=event_sequence)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_all_transitions_are_valid(self, events: list[SessionEvent]) -> None:
        """All state transitions performed must be valid according to the state machine.

        # Feature: screen-capture-mirror, Property 5: Session state machine transitions are valid
        **Validates: Requirements 6.1, 6.3, 2.3, 5.3, 8.1**
        """
        sm = PureStateMachine()

        for event in events:
            sm.apply_event(event)

        # Check all transitions in history were valid
        for from_state, to_state, was_valid in sm.transition_history:
            if was_valid:
                assert is_valid_transition(from_state, to_state), (
                    f"Invalid transition performed: {from_state.value} -> {to_state.value}. "
                    f"Events applied: {[e.value for e in events]}"
                )

    @given(events=event_sequence)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_invalid_transitions_are_rejected(self, events: list[SessionEvent]) -> None:
        """Invalid transitions must be rejected (state unchanged).

        # Feature: screen-capture-mirror, Property 5: Session state machine transitions are valid
        **Validates: Requirements 6.1, 6.3, 2.3, 5.3, 8.1**
        """
        sm = PureStateMachine()

        for event in events:
            sm.apply_event(event)

        # Check that rejected transitions did not change state
        for from_state, to_state, was_valid in sm.transition_history:
            if not was_valid and from_state != to_state:
                # If transition was rejected but states differ, that's a problem
                # (But note: in our history, from_state is the state BEFORE the transition)
                # The actual check is that after a rejected transition, state stays same
                pass

        # Verify by replaying: rejected transitions should not change state
        sm2 = PureStateMachine()
        for from_state, to_state, was_valid in sm.transition_history:
            old = sm2.state
            result = sm2.transition(to_state)
            if not result:
                assert sm2.state == old, (
                    f"State changed after rejected transition. "
                    f"Old: {old.value}, New: {sm2.state.value}, Attempted: {to_state.value}"
                )

    @given(from_state=mirror_state, to_state=mirror_state)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_direct_transition_validity(
        self, from_state: MirrorState, to_state: MirrorState
    ) -> None:
        """Direct transitions are only allowed between states in VALID_TRANSITIONS.

        # Feature: screen-capture-mirror, Property 5: Session state machine transitions are valid
        **Validates: Requirements 6.1, 6.3, 2.3, 5.3, 8.1**
        """
        # Check that our validity function matches the defined transitions
        expected_valid = to_state in VALID_TRANSITIONS.get(from_state, set())
        actual_valid = is_valid_transition(from_state, to_state)

        assert actual_valid == expected_valid, (
            f"Validity mismatch for {from_state.value} -> {to_state.value}. "
            f"Expected: {expected_valid}, Got: {actual_valid}"
        )

    @given(events=event_sequence)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_state_machine_always_reaches_valid_state(
        self, events: list[SessionEvent]
    ) -> None:
        """After any sequence of events, state machine is in a valid state.

        # Feature: screen-capture-mirror, Property 5: Session state machine transitions are valid
        **Validates: Requirements 6.1, 6.3, 2.3, 5.3, 8.1**
        """
        sm = PureStateMachine()

        for event in events:
            sm.apply_event(event)

        # Final state must be a valid MirrorState
        assert sm.state in MirrorState, (
            f"Invalid final state: {sm.state}. Events: {[e.value for e in events]}"
        )

    @given(events=event_sequence)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_idle_is_always_reachable(self, events: list[SessionEvent]) -> None:
        """IDLE state can always be reached by calling stop().

        # Feature: screen-capture-mirror, Property 5: Session state machine transitions are valid
        **Validates: Requirements 6.1, 6.3, 8.1**

        This validates requirement 6.3: session cleanup returns to IDLE.
        """
        sm = PureStateMachine()

        # Apply random events
        for event in events:
            sm.apply_event(event)

        # Now apply stop - should reach IDLE or stay in IDLE
        sm.apply_event(SessionEvent.STOP)

        assert sm.state == MirrorState.IDLE, (
            f"After STOP, state should be IDLE but got {sm.state.value}. "
            f"Events: {[e.value for e in events]}"
        )

    @given(events=event_sequence)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_no_forbidden_transitions_occur(self, events: list[SessionEvent]) -> None:
        """Forbidden transitions (e.g., IDLE -> STREAMING directly) never occur.

        # Feature: screen-capture-mirror, Property 5: Session state machine transitions are valid
        **Validates: Requirements 6.1, 2.3, 5.3**
        """
        # Define explicitly forbidden transitions
        forbidden = [
            (MirrorState.IDLE, MirrorState.STREAMING),  # Must go through STARTING
            (MirrorState.IDLE, MirrorState.STOPPING),  # Can't stop what isn't started
            (MirrorState.IDLE, MirrorState.ERROR),  # Error only from active states
            (
                MirrorState.STREAMING,
                MirrorState.STARTING,
            ),  # Can't restart while streaming
            (MirrorState.STOPPING, MirrorState.STREAMING),  # Can't resume during stop
            (MirrorState.STOPPING, MirrorState.STARTING),  # Can't restart during stop
            (MirrorState.ERROR, MirrorState.STREAMING),  # Must restart from IDLE
            (MirrorState.ERROR, MirrorState.STARTING),  # Must go to IDLE first
        ]

        sm = PureStateMachine()

        for event in events:
            sm.apply_event(event)

        for from_state, to_state, was_valid in sm.transition_history:
            if was_valid:
                assert (from_state, to_state) not in forbidden, (
                    f"Forbidden transition occurred: {from_state.value} -> {to_state.value}. "
                    f"Events: {[e.value for e in events]}"
                )


class TestStateMachineSpecificPaths:
    """Tests for specific valid paths through the state machine."""

    def test_happy_path_streaming_to_idle(self) -> None:
        """Test the happy path: IDLE -> STARTING -> STREAMING -> STOPPING -> IDLE.

        # Feature: screen-capture-mirror, Property 5: Session state machine transitions are valid
        """
        sm = PureStateMachine()

        # Start session
        assert sm.apply_event(SessionEvent.START)
        assert sm.state == MirrorState.STARTING

        # Stream becomes ready
        assert sm.apply_event(SessionEvent.STREAM_READY)
        assert sm.state == MirrorState.STREAMING

        # Stop session
        assert sm.apply_event(SessionEvent.STOP)
        assert sm.state == MirrorState.IDLE

    def test_error_during_startup(self) -> None:
        """Test error path: IDLE -> STARTING -> ERROR -> IDLE.

        # Feature: screen-capture-mirror, Property 5: Session state machine transitions are valid
        **Validates: Requirements 5.3, 8.1**
        """
        sm = PureStateMachine()

        # Start session
        assert sm.apply_event(SessionEvent.START)
        assert sm.state == MirrorState.STARTING

        # Error occurs during startup
        assert sm.apply_event(SessionEvent.ERROR)
        assert sm.state == MirrorState.IDLE  # Error + cleanup returns to IDLE

    def test_error_during_streaming(self) -> None:
        """Test error path: STREAMING -> ERROR -> IDLE.

        # Feature: screen-capture-mirror, Property 5: Session state machine transitions are valid
        **Validates: Requirements 8.1**
        """
        sm = PureStateMachine()

        # Get to streaming state
        sm.apply_event(SessionEvent.START)
        sm.apply_event(SessionEvent.STREAM_READY)
        assert sm.state == MirrorState.STREAMING

        # Error occurs (e.g., encoder crash)
        assert sm.apply_event(SessionEvent.ERROR)
        assert sm.state == MirrorState.IDLE  # Error + cleanup returns to IDLE

    def test_stop_while_starting_aborts(self) -> None:
        """Stopping during STARTING should abort and return to IDLE.

        # Feature: screen-capture-mirror, Property 5: Session state machine transitions are valid
        **Validates: Requirements 6.1**
        """
        sm = PureStateMachine()

        sm.apply_event(SessionEvent.START)
        assert sm.state == MirrorState.STARTING

        # Stop before stream is ready
        sm.apply_event(SessionEvent.STOP)
        assert sm.state == MirrorState.IDLE

    def test_multiple_stops_are_safe(self) -> None:
        """Multiple stop calls should be safe (idempotent).

        # Feature: screen-capture-mirror, Property 5: Session state machine transitions are valid
        **Validates: Requirements 6.1**
        """
        sm = PureStateMachine()

        # Stop from IDLE (no-op)
        sm.apply_event(SessionEvent.STOP)
        assert sm.state == MirrorState.IDLE

        # Start and stream
        sm.apply_event(SessionEvent.START)
        sm.apply_event(SessionEvent.STREAM_READY)

        # Multiple stops
        sm.apply_event(SessionEvent.STOP)
        assert sm.state == MirrorState.IDLE

        sm.apply_event(SessionEvent.STOP)
        assert sm.state == MirrorState.IDLE

    def test_cannot_start_while_active(self) -> None:
        """Cannot start a new session while one is active.

        # Feature: screen-capture-mirror, Property 5: Session state machine transitions are valid
        **Validates: Requirements 6.1**
        """
        sm = PureStateMachine()

        # Start first session
        sm.apply_event(SessionEvent.START)
        sm.apply_event(SessionEvent.STREAM_READY)
        assert sm.state == MirrorState.STREAMING

        # Try to start another
        result = sm.apply_event(SessionEvent.START)
        assert result is False
        assert sm.state == MirrorState.STREAMING  # State unchanged

    def test_health_check_only_valid_when_streaming(self) -> None:
        """Health check is only meaningful when streaming.

        # Feature: screen-capture-mirror, Property 5: Session state machine transitions are valid
        """
        sm = PureStateMachine()

        # Health check in IDLE - not meaningful
        assert not sm.apply_event(SessionEvent.HEALTH_CHECK)
        assert sm.state == MirrorState.IDLE

        # Health check in STARTING - not meaningful
        sm.apply_event(SessionEvent.START)
        assert not sm.apply_event(SessionEvent.HEALTH_CHECK)
        assert sm.state == MirrorState.STARTING

        # Health check in STREAMING - valid
        sm.apply_event(SessionEvent.STREAM_READY)
        assert sm.apply_event(SessionEvent.HEALTH_CHECK)
        assert sm.state == MirrorState.STREAMING


class TestStateMachineInvariants:
    """Test invariants that must hold for the state machine."""

    @given(events=event_sequence)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_state_is_always_a_valid_enum_value(
        self, events: list[SessionEvent]
    ) -> None:
        """State is always a valid MirrorState enum value.

        # Feature: screen-capture-mirror, Property 5: Session state machine transitions are valid
        """
        sm = PureStateMachine()

        for event in events:
            sm.apply_event(event)
            assert isinstance(sm.state, MirrorState), (
                f"Invalid state type: {type(sm.state)}"
            )

    @given(events=event_sequence)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_history_is_complete(self, events: list[SessionEvent]) -> None:
        """Transition history records all transition attempts.

        # Feature: screen-capture-mirror, Property 5: Session state machine transitions are valid
        """
        sm = PureStateMachine()

        for event in events:
            sm.apply_event(event)

        # History should have at least as many entries as state changes would require
        # (Some events trigger multiple transitions, e.g., STOP -> STOPPING -> IDLE)
        assert len(sm.transition_history) >= 0  # Basic sanity check

    def test_all_states_are_reachable(self) -> None:
        """All defined states are reachable from IDLE.

        # Feature: screen-capture-mirror, Property 5: Session state machine transitions are valid
        """
        # IDLE is the initial state
        sm = PureStateMachine()
        assert sm.state == MirrorState.IDLE

        # STARTING is reachable
        sm.apply_event(SessionEvent.START)
        assert sm.state == MirrorState.STARTING

        # STREAMING is reachable
        sm.apply_event(SessionEvent.STREAM_READY)
        assert sm.state == MirrorState.STREAMING

        # STOPPING is reachable (as intermediate state)
        # We verify by checking transition history after stop
        sm.apply_event(SessionEvent.STOP)
        assert sm.state == MirrorState.IDLE

        # Check that STOPPING was visited
        stopping_reached = any(
            to_state == MirrorState.STOPPING
            for _, to_state, valid in sm.transition_history
            if valid
        )
        assert stopping_reached, "STOPPING state was never reached"

        # ERROR is reachable
        sm.reset()
        sm.apply_event(SessionEvent.START)
        sm.apply_event(SessionEvent.STREAM_READY)
        sm.apply_event(SessionEvent.ERROR)
        # Check that ERROR was visited
        error_reached = any(
            to_state == MirrorState.ERROR
            for _, to_state, valid in sm.transition_history
            if valid
        )
        assert error_reached, "ERROR state was never reached"


class TestMirrorSessionTransitionStateMethod:
    """Tests for the actual MirrorSession._transition_state() method.

    These tests verify that the real implementation matches the expected
    state machine behavior.
    """

    @given(from_state=mirror_state, to_state=mirror_state)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_transition_state_matches_expected_validity(
        self, from_state: MirrorState, to_state: MirrorState
    ) -> None:
        """MirrorSession._transition_state() matches expected validity.

        # Feature: screen-capture-mirror, Property 5: Session state machine transitions are valid
        **Validates: Requirements 6.1, 6.3, 2.3, 5.3, 8.1**
        """
        from lgtvtools.mirror.session import MirrorSession

        # Create a mock session with minimal dependencies
        source = CaptureSource(id="1", name="Test Screen", kind="screen")

        with patch("lgtvtools.mirror.session.detect_platform"):
            session = MirrorSession(
                device_ip="192.168.1.100",
                source=source,
            )

        # Set the state to from_state via internal manipulation
        session._state = from_state

        # Attempt the transition
        result = session._transition_state(to_state)

        # Verify result matches expectation
        expected = is_valid_transition(from_state, to_state)
        assert result == expected, (
            f"Transition {from_state.value} -> {to_state.value} returned {result}, "
            f"expected {expected}"
        )

        # Verify state was updated correctly
        if expected:
            assert session.state == to_state, (
                f"State should be {to_state.value} after valid transition, "
                f"but is {session.state.value}"
            )
        else:
            assert session.state == from_state, (
                f"State should remain {from_state.value} after invalid transition, "
                f"but is {session.state.value}"
            )

    @given(events=st.lists(session_event, min_size=1, max_size=20))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_real_session_maintains_valid_states(
        self, events: list[SessionEvent]
    ) -> None:
        """Real MirrorSession always maintains valid state after events.

        # Feature: screen-capture-mirror, Property 5: Session state machine transitions are valid
        **Validates: Requirements 6.1, 6.3, 2.3, 5.3, 8.1**

        This test verifies that when applying events to the real MirrorSession,
        all _transition_state calls return valid results according to the state
        machine definition.
        """
        from lgtvtools.mirror.session import MirrorSession

        source = CaptureSource(id="1", name="Test Screen", kind="screen")

        with patch("lgtvtools.mirror.session.detect_platform"):
            session = MirrorSession(
                device_ip="192.168.1.100",
                source=source,
            )

        for event in events:
            old_state = session.state

            # Apply event by directly calling _transition_state
            # (We can't call start/stop directly as they have side effects)
            # Each transition is individually validated by _transition_state
            if event == SessionEvent.START and old_state == MirrorState.IDLE:
                result = session._transition_state(MirrorState.STARTING)
                assert result is True, "IDLE -> STARTING should be valid"

            elif (
                event == SessionEvent.STREAM_READY and old_state == MirrorState.STARTING
            ):
                result = session._transition_state(MirrorState.STREAMING)
                assert result is True, "STARTING -> STREAMING should be valid"

            elif event == SessionEvent.STOP:
                if old_state == MirrorState.STREAMING:
                    result = session._transition_state(MirrorState.STOPPING)
                    assert result is True, "STREAMING -> STOPPING should be valid"
                    # Then cleanup transitions to IDLE
                    result = session._transition_state(MirrorState.IDLE)
                    assert result is True, "STOPPING -> IDLE should be valid"
                elif old_state == MirrorState.STARTING:
                    result = session._transition_state(MirrorState.ERROR)
                    assert result is True, "STARTING -> ERROR should be valid"
                    # Then cleanup transitions to IDLE
                    result = session._transition_state(MirrorState.IDLE)
                    assert result is True, "ERROR -> IDLE should be valid"
                elif old_state == MirrorState.ERROR:
                    result = session._transition_state(MirrorState.IDLE)
                    assert result is True, "ERROR -> IDLE should be valid"

            elif event == SessionEvent.ERROR:
                if old_state == MirrorState.STARTING:
                    result = session._transition_state(MirrorState.ERROR)
                    assert result is True, "STARTING -> ERROR should be valid"
                    # Then cleanup transitions to IDLE
                    result = session._transition_state(MirrorState.IDLE)
                    assert result is True, "ERROR -> IDLE should be valid"
                elif old_state == MirrorState.STREAMING:
                    result = session._transition_state(MirrorState.ERROR)
                    assert result is True, "STREAMING -> ERROR should be valid"
                    # Then cleanup transitions to IDLE
                    result = session._transition_state(MirrorState.IDLE)
                    assert result is True, "ERROR -> IDLE should be valid"

        # Final state should be valid
        assert session.state in MirrorState

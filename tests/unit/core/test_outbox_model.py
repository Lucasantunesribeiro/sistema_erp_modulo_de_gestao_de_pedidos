"""Unit tests for the OutboxEvent model.

Covers:
- Event creation with all required fields.
- Default status is PENDING.
- JSON payload persistence and retrieval.
- mark_as_published() transition (PENDING -> PUBLISHED).
- mark_as_failed(error) transition with retry counter.
- __str__ representation.
"""

from __future__ import annotations

import uuid

import pytest

from modules.core.models import EventStatus, OutboxEvent

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_event(**overrides) -> OutboxEvent:
    """Create and persist an OutboxEvent with sensible defaults."""
    defaults = {
        "event_type": "ORDER_CREATED",
        "payload": {"order_id": "abc-123", "total": "99.90"},
        "aggregate_id": "abc-123",
        "topic": "orders",
    }
    defaults.update(overrides)
    return OutboxEvent.objects.create(**defaults)


# ---------------------------------------------------------------------------
# Creation
# ---------------------------------------------------------------------------


class TestOutboxEventCreation:
    """Happy-path event creation."""

    def test_create_event_with_defaults(self):
        event = _make_event()
        event.refresh_from_db()
        assert event.event_type == "ORDER_CREATED"
        assert event.aggregate_id == "abc-123"
        assert event.topic == "orders"
        assert event.status == EventStatus.PENDING
        assert event.processed_at is None
        assert event.error_message is None
        assert event.retry_count == 0

    def test_id_is_uuid7(self):
        event = _make_event()
        assert isinstance(event.id, uuid.UUID)
        assert event.id.version == 7

    def test_timestamps_set_on_create(self):
        event = _make_event()
        assert event.created_at is not None
        assert event.updated_at is not None

    def test_default_status_is_pending(self):
        event = _make_event()
        assert event.status == EventStatus.PENDING


# ---------------------------------------------------------------------------
# JSON Payload
# ---------------------------------------------------------------------------


class TestOutboxEventPayload:
    """JSON payload persistence and retrieval."""

    def test_payload_persisted_and_retrieved(self):
        payload = {"order_id": "xyz-789", "items": [1, 2, 3], "nested": {"key": "val"}}
        event = _make_event(payload=payload)
        event.refresh_from_db()
        assert event.payload == payload

    def test_payload_with_empty_dict(self):
        event = _make_event(payload={})
        event.refresh_from_db()
        assert event.payload == {}

    def test_payload_with_list(self):
        event = _make_event(payload=[{"id": 1}, {"id": 2}])
        event.refresh_from_db()
        assert event.payload == [{"id": 1}, {"id": 2}]


# ---------------------------------------------------------------------------
# Status Transitions
# ---------------------------------------------------------------------------


class TestOutboxEventMarkAsPublished:
    """mark_as_published() sets status and processed_at."""

    def test_mark_as_published(self):
        event = _make_event()
        assert event.status == EventStatus.PENDING
        assert event.processed_at is None

        event.mark_as_published()
        event.refresh_from_db()

        assert event.status == EventStatus.PUBLISHED
        assert event.processed_at is not None

    def test_mark_as_published_updates_updated_at(self):
        event = _make_event()
        original_updated_at = event.updated_at

        event.mark_as_published()
        event.refresh_from_db()

        assert event.updated_at > original_updated_at


class TestOutboxEventMarkAsFailed:
    """mark_as_failed(error) sets status, error, and increments retry."""

    def test_mark_as_failed(self):
        event = _make_event()
        event.mark_as_failed("Connection timeout")
        event.refresh_from_db()

        assert event.status == EventStatus.FAILED
        assert event.error_message == "Connection timeout"
        assert event.retry_count == 1

    def test_mark_as_failed_increments_retry(self):
        event = _make_event()
        event.mark_as_failed("Error 1")
        event.mark_as_failed("Error 2")
        event.refresh_from_db()

        assert event.retry_count == 2
        assert event.error_message == "Error 2"

    def test_mark_as_failed_updates_updated_at(self):
        event = _make_event()
        original_updated_at = event.updated_at

        event.mark_as_failed("Something broke")
        event.refresh_from_db()

        assert event.updated_at > original_updated_at


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------


class TestOutboxEventDisplay:
    """__str__ shows event_type, status, and aggregate_id."""

    def test_str_representation(self):
        event = _make_event(
            event_type="STOCK_RESERVED",
            aggregate_id="order-456",
        )
        result = str(event)
        assert "STOCK_RESERVED" in result
        assert "PENDING" in result
        assert "order-456" in result

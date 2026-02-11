"""Unit tests for BaseModel and SoftDeleteModel.

Uses concrete test models created via Django's SchemaEditor so we can
exercise the abstract classes against a real database.
"""

from __future__ import annotations

import uuid

import pytest
from freezegun import freeze_time

from django.db import connection, models
from django.utils import timezone

from modules.core.models import BaseModel, SoftDeleteManager, SoftDeleteModel

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Concrete models for testing (abstract models can't be instantiated)
# ---------------------------------------------------------------------------


class ConcreteBaseModel(BaseModel):
    name = models.CharField(max_length=100)

    class Meta(BaseModel.Meta):
        app_label = "core"
        db_table = "test_concrete_base"


class ConcreteSoftDeleteModel(SoftDeleteModel):
    title = models.CharField(max_length=100)

    class Meta(SoftDeleteModel.Meta):
        app_label = "core"
        db_table = "test_concrete_soft_delete"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def _test_tables(django_db_setup, django_db_blocker):
    """Create DB tables for concrete test models (idempotent for --reuse-db)."""
    with django_db_blocker.unblock():
        with connection.schema_editor() as editor:
            existing = connection.introspection.table_names()
            if ConcreteBaseModel._meta.db_table not in existing:
                editor.create_model(ConcreteBaseModel)
            if ConcreteSoftDeleteModel._meta.db_table not in existing:
                editor.create_model(ConcreteSoftDeleteModel)


@pytest.fixture(autouse=True)
def _use_test_tables(_test_tables):
    """Ensure test tables exist for every test in this module."""


# ---------------------------------------------------------------------------
# BaseModel tests
# ---------------------------------------------------------------------------


class TestBaseModel:
    """Tests for UUIDv7 PK and timestamp behaviour."""

    def test_id_is_uuid(self):
        obj = ConcreteBaseModel.objects.create(name="test")
        assert isinstance(obj.id, uuid.UUID)

    def test_id_is_uuid_version_7(self):
        obj = ConcreteBaseModel.objects.create(name="test")
        # UUIDv7 has version bits set to 7
        assert obj.id.version == 7

    def test_ids_are_unique(self):
        a = ConcreteBaseModel.objects.create(name="a")
        b = ConcreteBaseModel.objects.create(name="b")
        assert a.id != b.id

    def test_ids_are_time_ordered(self):
        """UUIDv7 encodes timestamp, so sequential creates yield ordered IDs."""
        a = ConcreteBaseModel.objects.create(name="first")
        b = ConcreteBaseModel.objects.create(name="second")
        assert str(a.id) < str(b.id)

    def test_created_at_set_on_create(self):
        obj = ConcreteBaseModel.objects.create(name="test")
        assert obj.created_at is not None

    def test_updated_at_set_on_create(self):
        obj = ConcreteBaseModel.objects.create(name="test")
        assert obj.updated_at is not None

    def test_updated_at_changes_on_save(self):
        obj = ConcreteBaseModel.objects.create(name="original")
        original_updated = obj.updated_at
        obj.name = "modified"
        obj.save()
        obj.refresh_from_db()
        assert obj.updated_at > original_updated

    def test_created_at_does_not_change_on_save(self):
        obj = ConcreteBaseModel.objects.create(name="original")
        original_created = obj.created_at
        obj.name = "modified"
        obj.save()
        obj.refresh_from_db()
        assert obj.created_at == original_created

    def test_save_with_update_fields_includes_updated_at(self):
        """The save() guard must inject updated_at into update_fields."""
        obj = ConcreteBaseModel.objects.create(name="original")
        original_updated = obj.updated_at
        obj.name = "modified"
        obj.save(update_fields=["name"])
        obj.refresh_from_db()
        assert obj.updated_at > original_updated

    def test_id_is_not_editable(self):
        field = ConcreteBaseModel._meta.get_field("id")
        assert field.editable is False


# ---------------------------------------------------------------------------
# SoftDeleteModel tests
# ---------------------------------------------------------------------------


class TestSoftDeleteModel:
    """Tests for soft-delete, restore, and manager behaviour."""

    def test_new_instance_is_not_deleted(self):
        obj = ConcreteSoftDeleteModel.objects.create(title="alive")
        assert obj.is_deleted is False
        assert obj.deleted_at is None

    def test_delete_sets_deleted_at(self):
        obj = ConcreteSoftDeleteModel.objects.create(title="to-delete")
        result = obj.delete()
        obj.refresh_from_db()
        assert obj.deleted_at is not None
        assert obj.is_deleted is True
        assert result == (1, {"core.ConcreteSoftDeleteModel": 1})

    def test_delete_is_noop_if_already_deleted(self):
        obj = ConcreteSoftDeleteModel.objects.create(title="double-delete")
        obj.delete()
        result = obj.delete()
        assert result == (0, {})

    def test_soft_deleted_still_in_objects_all(self):
        """objects.all() returns ALL records, including soft-deleted."""
        obj = ConcreteSoftDeleteModel.objects.create(title="visible")
        obj.delete()
        assert ConcreteSoftDeleteModel.objects.filter(pk=obj.pk).exists()

    def test_soft_deleted_excluded_from_alive(self):
        obj = ConcreteSoftDeleteModel.objects.create(title="hidden")
        obj.delete()
        assert not ConcreteSoftDeleteModel.objects.alive().filter(pk=obj.pk).exists()

    def test_alive_returns_only_non_deleted(self):
        alive = ConcreteSoftDeleteModel.objects.create(title="alive")
        dead = ConcreteSoftDeleteModel.objects.create(title="dead")
        dead.delete()
        alive_qs = ConcreteSoftDeleteModel.objects.alive()
        assert alive_qs.filter(pk=alive.pk).exists()
        assert not alive_qs.filter(pk=dead.pk).exists()

    def test_dead_returns_only_deleted(self):
        alive = ConcreteSoftDeleteModel.objects.create(title="alive")
        dead = ConcreteSoftDeleteModel.objects.create(title="dead")
        dead.delete()
        dead_qs = ConcreteSoftDeleteModel.objects.dead()
        assert dead_qs.filter(pk=dead.pk).exists()
        assert not dead_qs.filter(pk=alive.pk).exists()

    def test_restore_clears_deleted_at(self):
        obj = ConcreteSoftDeleteModel.objects.create(title="restore-me")
        obj.delete()
        assert obj.is_deleted is True
        obj.restore()
        obj.refresh_from_db()
        assert obj.deleted_at is None
        assert obj.is_deleted is False

    def test_restore_is_noop_if_alive(self):
        obj = ConcreteSoftDeleteModel.objects.create(title="already-alive")
        obj.restore()
        obj.refresh_from_db()
        assert obj.deleted_at is None

    def test_hard_delete_removes_from_db(self):
        obj = ConcreteSoftDeleteModel.objects.create(title="permanent")
        pk = obj.pk
        obj.hard_delete()
        assert not ConcreteSoftDeleteModel.objects.filter(pk=pk).exists()

    def test_delete_updates_updated_at(self):
        obj = ConcreteSoftDeleteModel.objects.create(title="timestamp-check")
        original_updated = obj.updated_at
        obj.delete()
        obj.refresh_from_db()
        assert obj.updated_at > original_updated

    def test_restore_updates_updated_at(self):
        obj = ConcreteSoftDeleteModel.objects.create(title="timestamp-restore")
        obj.delete()
        obj.refresh_from_db()
        after_delete_updated = obj.updated_at
        obj.restore()
        obj.refresh_from_db()
        assert obj.updated_at > after_delete_updated

    @freeze_time("2025-06-15 12:00:00")
    def test_delete_records_exact_timestamp(self):
        obj = ConcreteSoftDeleteModel.objects.create(title="exact-time")
        obj.delete()
        obj.refresh_from_db()
        expected = timezone.now()
        assert obj.deleted_at == expected


class TestSoftDeleteQuerySet:
    """Tests for bulk operations on the SoftDeleteQuerySet."""

    def test_queryset_bulk_delete(self):
        a = ConcreteSoftDeleteModel.objects.create(title="bulk-a")
        b = ConcreteSoftDeleteModel.objects.create(title="bulk-b")
        qs = ConcreteSoftDeleteModel.objects.filter(pk__in=[a.pk, b.pk])
        count, details = qs.delete()
        assert count == 2
        a.refresh_from_db()
        b.refresh_from_db()
        assert a.is_deleted is True
        assert b.is_deleted is True

    def test_queryset_bulk_delete_skips_already_deleted(self):
        a = ConcreteSoftDeleteModel.objects.create(title="skip-a")
        b = ConcreteSoftDeleteModel.objects.create(title="skip-b")
        a.delete()
        qs = ConcreteSoftDeleteModel.objects.filter(pk__in=[a.pk, b.pk])
        count, _ = qs.delete()
        assert count == 1  # Only b was alive

    def test_queryset_hard_delete_removes_from_db(self):
        a = ConcreteSoftDeleteModel.objects.create(title="hard-a")
        b = ConcreteSoftDeleteModel.objects.create(title="hard-b")
        qs = ConcreteSoftDeleteModel.objects.filter(pk__in=[a.pk, b.pk])
        qs.hard_delete()
        assert not ConcreteSoftDeleteModel.objects.filter(pk__in=[a.pk, b.pk]).exists()

    def test_queryset_bulk_delete_updates_updated_at(self):
        obj = ConcreteSoftDeleteModel.objects.create(title="bulk-ts")
        original_updated = obj.updated_at
        ConcreteSoftDeleteModel.objects.filter(pk=obj.pk).delete()
        obj.refresh_from_db()
        assert obj.updated_at > original_updated


class TestSoftDeleteManagerType:
    """Verify manager and queryset types."""

    def test_objects_is_soft_delete_manager(self):
        assert isinstance(ConcreteSoftDeleteModel.objects, SoftDeleteManager)

    def test_queryset_type(self):
        from modules.core.models import SoftDeleteQuerySet

        qs = ConcreteSoftDeleteModel.objects.all()
        assert isinstance(qs, SoftDeleteQuerySet)

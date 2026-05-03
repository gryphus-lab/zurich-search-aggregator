from datetime import date

import pytest
from pydantic import ValidationError

from src.aggregator.models import ApartmentListing


def _minimal(**overrides) -> dict:
    """
    Build a minimal mapping of keyword arguments suitable for constructing an ApartmentListing.
    
    Parameters:
        **overrides: Any keyword arguments to override the default fields.
    
    Returns:
        A dict containing the default ApartmentListing fields (`id`, `title`, `price_chf`, `neighborhood`, `link`, `source`) with any provided `overrides` applied.
    """
    base = {
        "id": "abc123",
        "title": "Cosy 2-room flat",
        "price_chf": 2000.0,
        "neighborhood": "Oerlikon",
        "link": "https://example.com/flat/abc123",
        "source": "test",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Construction & defaults
# ---------------------------------------------------------------------------


def test_apartment_listing_minimal_construction():
    listing = ApartmentListing(**_minimal())

    assert listing.id == "abc123"
    assert listing.title == "Cosy 2-room flat"
    assert listing.price_chf == 2000.0
    assert listing.neighborhood == "Oerlikon"
    assert listing.link == "https://example.com/flat/abc123"
    assert listing.source == "test"


def test_apartment_listing_default_furnished_is_true():
    listing = ApartmentListing(**_minimal())
    assert listing.furnished is True


def test_apartment_listing_default_raw_data_is_empty_dict():
    listing = ApartmentListing(**_minimal())
    assert listing.raw_data == {}


def test_apartment_listing_default_optional_fields_are_none():
    listing = ApartmentListing(**_minimal())
    assert listing.address is None
    assert listing.available_from is None
    assert listing.size_m2 is None
    assert listing.rooms is None
    assert listing.description_snippet is None


def test_apartment_listing_accepts_all_optional_fields():
    listing = ApartmentListing(
        **_minimal(
            address="Hauptstrasse 1",
            available_from=date(2026, 6, 1),
            size_m2=55.5,
            rooms=2.5,
            description_snippet="Lovely flat with balcony",
            raw_data={"source_id": "99"},
            furnished=False,
        )
    )

    assert listing.address == "Hauptstrasse 1"
    assert listing.available_from == date(2026, 6, 1)
    assert listing.size_m2 == 55.5
    assert listing.rooms == 2.5
    assert listing.description_snippet == "Lovely flat with balcony"
    assert listing.raw_data == {"source_id": "99"}
    assert listing.furnished is False


def test_apartment_listing_raw_data_is_independent_per_instance():
    """
    Ensure each ApartmentListing instance receives a distinct default `raw_data` dictionary.
    
    Verifies that modifying one instance's `raw_data` does not affect another instance's `raw_data`.
    """
    a = ApartmentListing(**_minimal())
    b = ApartmentListing(**_minimal(id="other"))
    a.raw_data["key"] = "value"
    assert "key" not in b.raw_data


# ---------------------------------------------------------------------------
# Price field
# ---------------------------------------------------------------------------


def test_apartment_listing_integer_price_coerced_to_float():
    listing = ApartmentListing(**_minimal(price_chf=2500))
    assert isinstance(listing.price_chf, float)
    assert listing.price_chf == 2500.0


def test_apartment_listing_price_boundary_values():
    low = ApartmentListing(**_minimal(price_chf=0.0))
    assert low.price_chf == 0.0

    high = ApartmentListing(**_minimal(price_chf=99999.99))
    assert high.price_chf == 99999.99


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------


def test_apartment_listing_model_dump_contains_expected_keys():
    listing = ApartmentListing(**_minimal(available_from=date(2026, 5, 1)))
    data = listing.model_dump(mode="json")

    expected_keys = {
        "id", "title", "price_chf", "neighborhood", "link", "source",
        "address", "available_from", "size_m2", "rooms",
        "description_snippet", "raw_data", "furnished",
    }
    assert expected_keys == set(data.keys())


def test_apartment_listing_model_dump_serialises_date_as_string():
    listing = ApartmentListing(**_minimal(available_from=date(2026, 5, 1)))
    data = listing.model_dump(mode="json")
    assert data["available_from"] == "2026-05-01"


def test_apartment_listing_model_dump_none_date_stays_none():
    listing = ApartmentListing(**_minimal())
    data = listing.model_dump(mode="json")
    assert data["available_from"] is None


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------


def test_apartment_listing_missing_required_field_raises():
    kwargs = _minimal()
    del kwargs["price_chf"]
    with pytest.raises(ValidationError):
        ApartmentListing(**kwargs)


def test_apartment_listing_missing_link_raises():
    kwargs = _minimal()
    del kwargs["link"]
    with pytest.raises(ValidationError):
        ApartmentListing(**kwargs)
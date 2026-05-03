from datetime import date

from src.aggregator.filters import (
    apply_filters,
    generate_unique_id,
    is_month_to_month_friendly,
    normalize_neighborhood,
)
from src.aggregator.models import ApartmentListing


def make_listing(
    *,
    link: str,
    price_chf: float,
    neighborhood: str,
    description_snippet: str | None = None,
    available_from: date | None = None,
) -> ApartmentListing:
    return ApartmentListing(
        id=link.rsplit("/", 1)[-1] or "id",
        title="Test listing",
        price_chf=price_chf,
        neighborhood=neighborhood,
        address=None,
        link=link,
        available_from=available_from,
        size_m2=None,
        rooms=None,
        source="test",
        furnished=True,
        description_snippet=description_snippet,
        raw_data={},
    )


def test_normalize_neighborhood_basic_mappings():
    assert normalize_neighborhood("oerlikon") == "Oerlikon"
    assert normalize_neighborhood("Seebach") == "Seebach"
    assert normalize_neighborhood("quartier oerlikon") == "Oerlikon"


def test_is_month_to_month_friendly_keywords():
    flexible = make_listing(
        link="https://example.com/a",
        price_chf=2000,
        neighborhood="Oerlikon",
        description_snippet="Serviced apartment, month to month, furnished",
    )
    standard = make_listing(
        link="https://example.com/b",
        price_chf=2000,
        neighborhood="Oerlikon",
        description_snippet="Long-term apartment (annual lease)",
    )

    assert is_month_to_month_friendly(flexible) is True
    assert is_month_to_month_friendly(standard) is False


def test_apply_filters_price_neighborhood_and_move_in_date():
    listings = [
        make_listing(
            link="https://example.com/1",
            price_chf=2000,
            neighborhood="Oerlikon",
            available_from=date(2026, 5, 1),
            description_snippet="month to month furnished",
        ),
        # Price out of range
        make_listing(
            link="https://example.com/2",
            price_chf=3500,
            neighborhood="Oerlikon",
            available_from=date(2026, 5, 1),
            description_snippet="month to month furnished",
        ),
        # Move-in date too early
        make_listing(
            link="https://example.com/3",
            price_chf=2000,
            neighborhood="Oerlikon",
            available_from=date(2026, 4, 1),
            description_snippet="month to month furnished",
        ),
        # Neighborhood mismatch
        make_listing(
            link="https://example.com/4",
            price_chf=2000,
            neighborhood="Altstetten",
            available_from=date(2026, 5, 1),
            description_snippet="month to month furnished",
        ),
    ]

    filtered = apply_filters(
        listings=listings,
        price_min=1700,
        price_max=3000,
        move_in_from=date(2026, 5, 1),
        neighborhoods=["Oerlikon"],
        only_month_to_month=False,
    )

    assert len(filtered) == 1
    assert filtered[0].link == "https://example.com/1"


def test_apply_filters_deduplicates_on_link_and_price():
    # Same link + same effective price -> should dedupe
    flexible_first = make_listing(
        link="https://example.com/dup",
        price_chf=2000.0,
        neighborhood="Oerlikon",
        available_from=date(2026, 5, 1),
        description_snippet="month to month furnished",
    )
    standard_second = make_listing(
        link="https://example.com/dup",
        price_chf=2000.49,  # .0f formatting in generate_unique_id => same uid
        neighborhood="Oerlikon",
        available_from=date(2026, 5, 1),
        description_snippet="Long-term annual lease",
    )

    filtered = apply_filters(
        listings=[flexible_first, standard_second],
        price_min=1700,
        price_max=3000,
        move_in_from=None,
        neighborhoods=["Oerlikon"],
        only_month_to_month=False,
    )

    assert len(filtered) == 1
    assert filtered[0].link == "https://example.com/dup"
    assert filtered[0].description_snippet is not None
    assert filtered[0].description_snippet.startswith("[FLEXIBLE]")


def test_generate_unique_id_is_stable_and_short():
    listing = make_listing(
        link="https://example.com/id",
        price_chf=1999.0,
        neighborhood="Oerlikon",
    )
    uid1 = generate_unique_id(listing)
    uid2 = generate_unique_id(listing)
    assert uid1 == uid2
    assert len(uid1) == 16


def test_only_month_to_month_filters_non_flexible_listings():
    flexible = make_listing(
        link="https://example.com/flex",
        price_chf=2000,
        neighborhood="Oerlikon",
        available_from=date(2026, 5, 1),
        description_snippet="month to month furnished",
    )
    standard = make_listing(
        link="https://example.com/std",
        price_chf=2100,
        neighborhood="Oerlikon",
        available_from=date(2026, 5, 1),
        description_snippet="Long-term annual lease",
    )

    filtered = apply_filters(
        listings=[flexible, standard],
        price_min=1700,
        price_max=3000,
        move_in_from=None,
        neighborhoods=["Oerlikon"],
        only_month_to_month=True,
    )

    # Intended behavior: only flexible/month-to-month listings remain.
    assert [x.link for x in filtered] == ["https://example.com/flex"]

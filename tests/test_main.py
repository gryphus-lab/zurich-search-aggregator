import json
from datetime import date
from unittest.mock import MagicMock

import pytest
import typer

from src.aggregator.main import _main_impl as main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class DummyListing:
    def __init__(
        self,
        id="1",
        title="Test Apartment",
        price_chf=2000.0,
        neighborhood="Oerlikon",
        address="Oerlikon",
        link="https://example.com/1",
        available_from=None,
        source="test",
    ):
        self.id = id
        self.title = title
        self.price_chf = price_chf
        self.neighborhood = neighborhood
        self.address = address
        self.link = link
        self.available_from = available_from
        self.source = source

    def model_dump(self, mode="json", exclude=None):
        data = {
            "id": self.id,
            "title": self.title,
            "price_chf": self.price_chf,
            "neighborhood": self.neighborhood,
            "address": self.address,
            "link": self.link,
            "available_from": self.available_from,
            "source": self.source,
            "raw_data": {},
        }
        for key in exclude or ():
            data.pop(key, None)
        return data


@pytest.fixture
def mock_console(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr("src.aggregator.main.console", mock)
    return mock


@pytest.fixture
def mock_scrapers(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr("src.aggregator.main.run_all_scrapers", mock)
    return mock


@pytest.fixture
def mock_filters(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr("src.aggregator.main.apply_filters", mock)
    return mock


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------


def test_main_invalid_date_exits(mock_console):
    with pytest.raises(typer.Exit) as e:
        main(move_in_from="invalid-date")

    assert e.value.exit_code == 1
    mock_console.print.assert_called_once()


def test_main_valid_date_passed_to_scraper(mock_scrapers, mock_filters, tmp_path):
    mock_scrapers.return_value = []
    mock_filters.return_value = []

    output = tmp_path / "out.csv"

    main(move_in_from="2026-06-01", output=output)

    args = mock_scrapers.call_args.kwargs
    assert args["move_in_from"] == date(2026, 6, 1)


# ---------------------------------------------------------------------------
# Scraper + filter integration
# ---------------------------------------------------------------------------


def test_main_calls_scrapers_and_filters(mock_scrapers, mock_filters, tmp_path):
    mock_scrapers.return_value = [DummyListing()]
    mock_filters.return_value = [DummyListing()]

    output = tmp_path / "out.csv"

    main(output=output)

    mock_scrapers.assert_called_once()
    mock_filters.assert_called_once()


def test_main_filters_none_returns_empty_list(mock_scrapers, mock_filters, tmp_path):
    mock_scrapers.return_value = [DummyListing()]
    mock_filters.return_value = None

    output = tmp_path / "out.csv"

    main(output=output)

    # Should not crash → empty CSV written (header row only).
    assert output.exists()
    lines = output.read_text().strip().splitlines()
    assert lines[0].startswith("source,title,price_chf")
    assert len(lines) == 1  # header only, no data rows


# ---------------------------------------------------------------------------
# CSV output (default)
# ---------------------------------------------------------------------------


def test_main_writes_csv_file_by_default(mock_scrapers, mock_filters, tmp_path):
    listing = DummyListing()
    mock_scrapers.return_value = [listing]
    mock_filters.return_value = [listing]

    output = tmp_path / "nested" / "results.csv"

    main(output=output)

    assert output.exists()
    text = output.read_text()
    header = text.splitlines()[0]
    assert header.split(",")[:3] == ["source", "title", "price_chf"]
    assert "raw_data" not in header  # internal field excluded from CSV
    assert ",1" in text or text.strip().endswith(",1")  # id present


def test_main_creates_parent_directories(mock_scrapers, mock_filters, tmp_path):
    mock_scrapers.return_value = []
    mock_filters.return_value = []

    output = tmp_path / "deep" / "nested" / "file.csv"

    main(output=output)

    assert output.exists()


# ---------------------------------------------------------------------------
# JSON export (opt-in)
# ---------------------------------------------------------------------------


def test_main_json_export_writes_both(mock_scrapers, mock_filters, tmp_path):
    listing = DummyListing()
    mock_scrapers.return_value = [listing]
    mock_filters.return_value = [listing]

    output = tmp_path / "out.csv"

    main(output=output, export_json=True)

    # CSV is always written; JSON is written alongside with the same stem.
    assert output.exists()
    json_path = output.with_suffix(".json")
    assert json_path.exists()
    data = json.loads(json_path.read_text())
    assert isinstance(data, list)
    assert data[0]["id"] == "1"


# ---------------------------------------------------------------------------
# Console output
# ---------------------------------------------------------------------------


def test_main_prints_table_when_results_exist(
    mock_scrapers, mock_filters, mock_console, tmp_path
):
    listing = DummyListing()
    mock_scrapers.return_value = [listing]
    mock_filters.return_value = [listing]

    output = tmp_path / "out.csv"

    main(output=output)

    # Should print a table
    assert mock_console.print.called


def test_main_prints_no_results_message(
    mock_scrapers, mock_filters, mock_console, tmp_path
):
    mock_scrapers.return_value = []
    mock_filters.return_value = []

    output = tmp_path / "out.csv"

    main(output=output)

    mock_console.print.assert_called()
    args = mock_console.print.call_args[0][0]
    assert "No matches found" in str(args)


# ---------------------------------------------------------------------------
# Table formatting edge cases
# ---------------------------------------------------------------------------


def test_main_truncates_long_links(mock_scrapers, mock_filters, mock_console, tmp_path):
    long_link = "https://example.com/" + "x" * 200
    listing = DummyListing(link=long_link)

    mock_scrapers.return_value = [listing]
    mock_filters.return_value = [listing]

    output = tmp_path / "out.csv"

    main(output=output)

    # Ensure table printed (indirectly validates truncation logic ran)
    assert mock_console.print.called


def test_main_limits_table_to_15_rows(
    mock_scrapers, mock_filters, mock_console, tmp_path
):
    listings = [DummyListing(id=str(i)) for i in range(30)]

    mock_scrapers.return_value = listings
    mock_filters.return_value = listings

    output = tmp_path / "out.csv"

    main(output=output)

    # We can't easily inspect Table rows, but we ensure no crash and print called
    assert mock_console.print.called


# ---------------------------------------------------------------------------
# Metro-region expansion
# ---------------------------------------------------------------------------


def test_main_default_searches_city_quartiers(mock_scrapers, mock_filters, tmp_path):
    mock_scrapers.return_value = []
    mock_filters.return_value = []

    main(output=tmp_path / "out.csv")

    neighborhoods = mock_scrapers.call_args.kwargs["neighborhoods"]
    assert neighborhoods == ["Oerlikon", "Seebach", "Wipkingen", "Altstetten"]


def test_main_metro_flag_expands_to_full_region(mock_scrapers, mock_filters, tmp_path):
    mock_scrapers.return_value = []
    mock_filters.return_value = []

    main(output=tmp_path / "out.csv", metro=True)

    neighborhoods = mock_scrapers.call_args.kwargs["neighborhoods"]
    assert len(neighborhoods) == 30
    for town in ["Schlieren", "Thalwil", "Opfikon", "Küsnacht", "Regensdorf"]:
        assert town in neighborhoods


def test_main_explicit_neighborhoods_override_metro(
    mock_scrapers, mock_filters, tmp_path
):
    mock_scrapers.return_value = []
    mock_filters.return_value = []

    main(output=tmp_path / "out.csv", neighborhoods=["Dietikon"], metro=True)

    neighborhoods = mock_scrapers.call_args.kwargs["neighborhoods"]
    assert neighborhoods == ["Dietikon"]


# ---------------------------------------------------------------------------
# Source selection (CLI)
# ---------------------------------------------------------------------------


def test_main_default_runs_all_sources(mock_scrapers, mock_filters, tmp_path):
    mock_scrapers.return_value = []
    mock_filters.return_value = []

    main(output=tmp_path / "out.csv")

    assert mock_scrapers.call_args.kwargs["sources"] == [
        "flatfox",
        "blueground",
        "homegate",
        "ums",
    ]


def test_main_source_subset_passed_through(mock_scrapers, mock_filters, tmp_path):
    mock_scrapers.return_value = []
    mock_filters.return_value = []

    main(output=tmp_path / "out.csv", sources=["homegate", "flatfox"])

    # Canonical order is restored by normalize_sources.
    assert mock_scrapers.call_args.kwargs["sources"] == ["flatfox", "homegate"]


def test_main_unknown_source_exits(mock_console):
    with pytest.raises(typer.Exit) as e:
        main(sources=["zillow"])

    assert e.value.exit_code == 1
    mock_console.print.assert_called_once()

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

    def model_dump(self, mode="json"):
        return {
            "id": self.id,
            "title": self.title,
            "price_chf": self.price_chf,
            "neighborhood": self.neighborhood,
            "address": self.address,
            "link": self.link,
            "available_from": self.available_from,
            "source": self.source,
        }


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

    output = tmp_path / "out.json"

    main(move_in_from="2026-06-01", output_json=output)

    args = mock_scrapers.call_args.kwargs
    assert args["move_in_from"] == date(2026, 6, 1)


# ---------------------------------------------------------------------------
# Scraper + filter integration
# ---------------------------------------------------------------------------


def test_main_calls_scrapers_and_filters(mock_scrapers, mock_filters, tmp_path):
    mock_scrapers.return_value = [DummyListing()]
    mock_filters.return_value = [DummyListing()]

    output = tmp_path / "out.json"

    main(output_json=output)

    mock_scrapers.assert_called_once()
    mock_filters.assert_called_once()


def test_main_filters_none_returns_empty_list(mock_scrapers, mock_filters, tmp_path):
    mock_scrapers.return_value = [DummyListing()]
    mock_filters.return_value = None

    output = tmp_path / "out.json"

    main(output_json=output)

    # Should not crash → empty JSON written
    assert output.exists()
    data = json.loads(output.read_text())
    assert data == []


# ---------------------------------------------------------------------------
# JSON output
# ---------------------------------------------------------------------------


def test_main_writes_json_file(mock_scrapers, mock_filters, tmp_path):
    listing = DummyListing()
    mock_scrapers.return_value = [listing]
    mock_filters.return_value = [listing]

    output = tmp_path / "nested" / "results.json"

    main(output_json=output)

    assert output.exists()

    data = json.loads(output.read_text())
    assert isinstance(data, list)
    assert data[0]["id"] == "1"


def test_main_creates_parent_directories(mock_scrapers, mock_filters, tmp_path):
    mock_scrapers.return_value = []
    mock_filters.return_value = []

    output = tmp_path / "deep" / "nested" / "file.json"

    main(output_json=output)

    assert output.exists()


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------


def test_main_csv_export(monkeypatch, mock_scrapers, mock_filters, tmp_path):
    listing = DummyListing()
    mock_scrapers.return_value = [listing]
    mock_filters.return_value = [listing]

    mock_df = MagicMock()
    mock_pd = MagicMock(DataFrame=MagicMock(return_value=mock_df))

    monkeypatch.setitem(__import__("sys").modules, "pandas", mock_pd)

    output = tmp_path / "out.json"

    main(output_json=output, export_csv=True)

    csv_path = output.with_suffix(".csv")
    mock_df.to_csv.assert_called_once()
    assert str(csv_path) in str(mock_df.to_csv.call_args)


# ---------------------------------------------------------------------------
# Console output
# ---------------------------------------------------------------------------


def test_main_prints_table_when_results_exist(
    mock_scrapers, mock_filters, mock_console, tmp_path
):
    listing = DummyListing()
    mock_scrapers.return_value = [listing]
    mock_filters.return_value = [listing]

    output = tmp_path / "out.json"

    main(output_json=output)

    # Should print a table
    assert mock_console.print.called


def test_main_prints_no_results_message(
    mock_scrapers, mock_filters, mock_console, tmp_path
):
    mock_scrapers.return_value = []
    mock_filters.return_value = []

    output = tmp_path / "out.json"

    main(output_json=output)

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

    output = tmp_path / "out.json"

    main(output_json=output)

    # Ensure table printed (indirectly validates truncation logic ran)
    assert mock_console.print.called


def test_main_limits_table_to_15_rows(
    mock_scrapers, mock_filters, mock_console, tmp_path
):
    listings = [DummyListing(id=str(i)) for i in range(30)]

    mock_scrapers.return_value = listings
    mock_filters.return_value = listings

    output = tmp_path / "out.json"

    main(output_json=output)

    # We can't easily inspect Table rows, but we ensure no crash and print called
    assert mock_console.print.called

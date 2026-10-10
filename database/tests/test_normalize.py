"""Cleaning rules for imported data (database/imports/normalize.py). No database needed."""

import pytest

from database.imports.normalize import (
    classify, clean_station_name, connector_from_title, connectors_from_osm_tags, names_other_state,
    normalize_operator, parse_power_kw, parse_price_per_kwh,
)


@pytest.mark.parametrize("raw, expected", [
    ("tata", "Tata Power"), ("TATA", "Tata Power"), ("Tata power", "Tata Power"),
    ("Tata Power EZ Charge", "Tata Power"), ("JIO BP Pulse (India)", "Jio-bp"), ("Jio-bp", "Jio-bp"),
    ("Chargezone (India)", "ChargeZone"), ("eDrive BPCL (IN)", "Bharat Petroleum (BPCL)"),
    ("Statiq (IN)", "Statiq"), ("Fortum", "GLIDA (Fortum)"),
])
def test_operator_spellings_are_merged(raw, expected):
    assert normalize_operator(raw) == expected


def test_unknown_operator_values_are_ignored():
    assert normalize_operator("(Unknown Operator)", "", None) is None


def test_unrecognised_real_operator_is_kept_tidy():
    assert normalize_operator("Nikol  EV (IN)") == "Nikol EV"


def test_station_name_only_recognises_known_operators():
    assert normalize_operator(None, station_name="MobiLane AMC Kankariya") == "MobiLane"
    assert normalize_operator(None, station_name="Capital EV Charging Station") is None


def test_operator_matching_uses_whole_words():
    assert normalize_operator("Olavanna Motors") == "Olavanna Motors"   # not "Ola Hypercharger"


@pytest.mark.parametrize("title, current, expected", [
    ("CCS (Type 2)", "DC", "CCS2"), ("CHAdeMO", "DC", "CHADEMO"),
    ("Type 2 (Socket Only)", "AC (Three-Phase)", "TYPE2"), ("Type 2 (Tethered Connector) ", None, "TYPE2"),
    ("IEC 60309 3-pin", None, "BHARAT_AC001"), ("GB-T DC - GB/T 20234.3", "DC", "BHARAT_DC001"),
    ("Type 1 (J1772)", None, "TYPE1"), ("CCS (Type 1)", "DC", "OTHER"),
    ("Unknown", None, None), ("Type M", None, None),
])
def test_connector_titles(title, current, expected):
    assert connector_from_title(title, current) == expected


def test_osm_socket_tags():
    tags = {"socket:type2_combo": "2", "socket:type2_combo:output": "60 kW", "socket:type2": "1",
            "socket:type2:output": "7400 W", "socket:chademo": "no", "socket:unknown_thing": "3"}
    result = sorted(connectors_from_osm_tags(tags), key=lambda c: c["connector_type"])
    assert result == [
        {"connector_type": "CCS2", "count": 2, "power_kw": 60.0},
        {"connector_type": "TYPE2", "count": 1, "power_kw": 7.4},
    ]


@pytest.mark.parametrize("text, expected", [("60 kW", 60.0), ("7400 W", 7.4), ("22", 22.0), ("3300", 3.3), ("", None), ("fast", None)])
def test_power_parsing(text, expected):
    assert parse_power_kw(text) == expected


@pytest.mark.parametrize("text, expected", [
    ("21/kWh", 21.0), ("21.0/kWh", 21.0), ("Rs 14", 14.0), ("21rs", 21.0), ("21++", 21.0),
    ("£0.79/kWh; other tariffs available", None), ("Free", None), (None, None), ("250 per session", None),
])
def test_price_parsing_accepts_only_believable_prices(text, expected):
    assert parse_price_per_kwh(text) == expected


@pytest.mark.parametrize("name, operator, plugs, tags, expected", [
    ("Honda e:swap", None, None, None, "EXCLUDE"),
    ("Battery Smart station", None, None, None, "EXCLUDE"),
    ("Yulu Zone", None, None, None, "EXCLUDE"),
    ("Cycle Kiosk / E-Vehicle Recharge", None, None, None, "EXCLUDE"),
    ("Ather Grid Charging Station", "Ather Grid", None, None, "TWO_WHEELER"),
    ("Some Hub", None, ["Type M"], None, "TWO_WHEELER"),
    ("Some Hub", None, ["Type M", "CCS (Type 2)"], None, "FOUR_WHEELER"),
    ("Scooter point", None, None, {"amenity": "charging_station", "motorcar": "no", "scooter": "yes"}, "TWO_WHEELER"),
    ("Tata Power – Gota", "Tata Power", ["CCS (Type 2)"], None, "FOUR_WHEELER"),
])
def test_classify(name, operator, plugs, tags, expected):
    assert classify(name, operator, plugs, tags) == expected


def test_junk_names_are_replaced():
    assert clean_station_name("Unknown Charging Station", "Tata Power", "Bopal") == "Tata Power – Bopal"
    assert clean_station_name("EV Charging Station", None, None) == "EV Charging Station"
    assert clean_station_name("Agora Mall Charging Station", "Jio-bp", "Gandhinagar") == "Agora Mall Charging Station"


def test_address_naming_another_state_is_detected():
    assert names_other_state("Gujarat", "Karnataka", "Whitefield, Bengaluru") == "karnataka"
    assert names_other_state("Gujarat", "Gujarat", "SG Highway, Ahmedabad") is None
    assert names_other_state("Gujarat", None, None) is None

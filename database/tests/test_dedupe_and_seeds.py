"""Duplicate detection, the region boundary test and seed generation. No database needed."""

from database.imports.dedupe import Candidate, find_duplicates
from database.imports.regions import point_in_boundary
from database.seeds.profiles import estimate_price, generate_chargers


def station(sid, name, lat, lng, source="ocm", operator=None, chargers=1):
    return Candidate(sid, name, lat, lng, operator, source, chargers)


# 0.0001 degrees of latitude is about 11 m.
def test_nearby_stations_with_similar_names_are_merged():
    a = station("a", "Riya Autolink Bopal", 23.02558, 72.47991, "manual")
    b = station("b", "Riya Auto Link - Bopal", 23.02570, 72.47991, "osm")
    assert find_duplicates([a, b]) == [(a, [b])]


def test_manual_beats_imported_sources():
    osm = station("1", "Gota HP pump", 23.10381, 72.53993, "osm", chargers=4)
    manual = station("2", "Gota HP pump", 23.10382, 72.53993, "manual", chargers=1)
    ocm = station("3", "Gota HP pump", 23.10383, 72.53993, "ocm", chargers=2)
    [(survivor, others)] = find_duplicates([osm, manual, ocm])
    assert survivor is manual
    assert {o.station_id for o in others} == {"1", "3"}


def test_generic_name_merges_with_a_real_one_nearby():
    a = station("a", "EV Charging Station", 23.0300, 72.5100)
    b = station("b", "Swarnim Heights", 23.0301, 72.5100)
    assert len(find_duplicates([a, b])) == 1


def test_different_places_are_not_merged():
    far = [station("a", "Agora Mall", 23.0300, 72.5100), station("b", "Agora Mall", 23.0310, 72.5100)]  # ~110 m apart
    different = [station("c", "Agora Mall", 23.0300, 72.5100, operator="Jio-bp"),
                 station("d", "Capital EV Kalupur", 23.0301, 72.5100)]
    assert find_duplicates(far) == []
    assert find_duplicates(different) == []


def test_point_in_boundary_with_a_square():
    # A 1x1 degree square drawn as four separate edges (lng1, lat1, lng2, lat2).
    square = [(0, 0, 1, 0), (1, 0, 1, 1), (1, 1, 0, 1), (0, 1, 0, 0)]
    assert point_in_boundary(0.5, 0.5, square)
    assert not point_in_boundary(1.5, 0.5, square)
    assert not point_in_boundary(0.5, -0.2, square)


def test_synthetic_chargers_are_repeatable_and_realistic():
    sid = "6b0a4d2e-1c3f-4b5a-9d8e-7f6a5b4c3d2e"
    first, second = generate_chargers(sid, "Tata Power"), generate_chargers(sid, "Tata Power")
    assert first == second                                   # same station -> same chargers
    assert first[0]["connector_type"] == "CCS2"              # Tata Power always has a CCS2 fast charger
    assert all(10 <= c["price_per_kwh"] <= 25 for c in first)
    assert len(generate_chargers(sid, None, count=5)) == 5


def test_estimated_prices_follow_power_bands():
    sid = "6b0a4d2e-1c3f-4b5a-9d8e-7f6a5b4c3d2e"
    assert 10 <= estimate_price(sid, "TYPE2-1", 7.4) <= 16      # slow AC
    assert 16 <= estimate_price(sid, "CCS2-1", 50) <= 22        # DC fast
    assert 21 <= estimate_price(sid, "CCS2-2", 120) <= 25       # DC rapid

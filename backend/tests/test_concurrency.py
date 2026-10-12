"""Two people book the same slot at the same instant: exactly one wins (needs the test database).

Unlike the other tests, nothing here is wrapped in a rolled-back transaction: each thread has
its OWN database connection and really commits, because that is what makes the race real. The
test cleans up its rows afterwards.
"""

import threading
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.features.bookings import service
from app.features.recommendations import service as recommendations
from app.features.recommendations.osrm import Travel
from tests import factories
from tests.conftest import needs_db

pytestmark = needs_db

NOW = datetime(2026, 10, 12, 10, 0, tzinfo=timezone.utc)
ROUNDS = 12


class FakeRoutes:
    def estimate(self, origin, destinations):
        return [Travel(5.0, 2.0, True) for _ in destinations]


@pytest.fixture
def committed_world(test_engine, monkeypatch):
    """A station, a charger and several drivers, really committed; removed when the test ends."""
    monkeypatch.setattr(recommendations, "travel_times", FakeRoutes())
    with Session(test_engine) as setup:
        station = factories.make_station(setup, "Race hub", 23.03, 72.55)
        charger = factories.make_charger(setup, station, "CCS2", 60, 20, label="Only one")
        spare = factories.make_charger(setup, station, "CCS2", 60, 20, label="Spare")
        users = [factories.make_user(setup) for _ in range(4)]
        setup.commit()
    yield {"station": station, "charger": charger, "spare": spare, "users": users}
    with Session(test_engine) as cleanup:
        ids = {"s": station, "u": users}
        cleanup.execute(text("DELETE FROM bookings WHERE user_id = ANY(:u)"), ids)  # booking_events go with them
        cleanup.execute(text("DELETE FROM chargers WHERE station_id = :s"), ids)
        cleanup.execute(text("DELETE FROM stations WHERE station_id = :s"), ids)
        cleanup.execute(text("DELETE FROM users WHERE user_id = ANY(:u)"), ids)
        cleanup.commit()


def book_at_the_same_moment(engine, charger, users, start, blocks=2):
    """Each user books from their own connection; a barrier lets them all go together."""
    barrier = threading.Barrier(len(users))
    outcomes = [None] * len(users)

    def worker(index):
        with Session(engine) as session:  # a separate connection and transaction per person
            barrier.wait()
            try:
                outcomes[index] = ("booked", service.create_hold(session, users[index], charger, start, blocks, None, NOW))
            except AppError as error:
                outcomes[index] = ("refused", error)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(len(users))]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    assert all(o is not None for o in outcomes), "a booking attempt hung"
    return outcomes


def test_two_people_booking_the_same_slot_at_the_same_moment_exactly_one_wins(test_engine, committed_world):
    world = committed_world
    for round_number in range(ROUNDS):  # many rounds: the interesting orderings (and deadlocks) are timing-dependent
        start = NOW + timedelta(hours=2 + round_number)
        winners = []
        refused = []
        outcomes = book_at_the_same_moment(test_engine, world["charger"], world["users"][:2], start)
        for kind, value in outcomes:
            (winners if kind == "booked" else refused).append(value)

        assert len(winners) == 1, f"round {round_number}: {[(k, getattr(v, 'code', None)) for k, v in outcomes]}"
        [loser] = refused
        assert loser.status_code == 409 and loser.code == "SLOT_TAKEN"
        assert loser.details["alternatives"]["charger_id"] == str(world["charger"])
        assert [o["label"] for o in loser.details["alternatives"]["other_chargers"]] == ["Spare"]

        with Session(test_engine) as check:
            live = check.execute(
                text("SELECT count(*) FROM bookings WHERE charger_id = :c AND lower(time_range) = :s AND status = 'HELD'"),
                {"c": world["charger"], "s": start},
            ).scalar_one()
            assert live == 1  # the database holds exactly one booking for that slot
            # Release it so the next round starts clean (and the one-hold-per-user rule doesn't interfere).
            check.execute(text("DELETE FROM bookings WHERE charger_id = :c AND lower(time_range) = :s"), {"c": world["charger"], "s": start})
            check.commit()


def test_four_people_overlapping_but_not_identical_slots_still_allow_only_one(test_engine, committed_world):
    """Overlapping (not just identical) ranges conflict: 12:00-13:00 vs 12:30-13:30 and so on."""
    world = committed_world
    starts = [NOW + timedelta(hours=2), NOW + timedelta(hours=2, minutes=30), NOW + timedelta(hours=3), NOW + timedelta(hours=2, minutes=30)]
    barrier = threading.Barrier(4)
    results = [None] * 4

    def worker(i):
        with Session(test_engine) as session:
            barrier.wait()
            try:
                service.create_hold(session, world["users"][i], world["charger"], starts[i], 2, None, NOW)
                results[i] = "booked"
            except AppError as error:
                results[i] = error.code

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    # 12:00-13:00 conflicts with 12:30-13:30 and 13:00-14:00 does not overlap 12:00-13:00 but does overlap 12:30-13:30.
    assert results.count("booked") in (1, 2)
    assert set(results) <= {"booked", "SLOT_TAKEN"}
    with Session(test_engine) as check:
        ranges = check.execute(
            text("SELECT lower(time_range), upper(time_range) FROM bookings WHERE charger_id = :c AND status = 'HELD' ORDER BY 1"),
            {"c": world["charger"]},
        ).all()
    for (_, first_end), (second_start, _) in zip(ranges, ranges[1:]):
        assert first_end <= second_start  # whatever was accepted, nothing overlaps


def test_the_same_person_double_clicking_gets_one_hold(test_engine, committed_world):
    world = committed_world
    user = world["users"][0]
    barrier = threading.Barrier(2)
    results = [None, None]

    def worker(i):
        with Session(test_engine) as session:
            barrier.wait()
            try:
                service.create_hold(session, user, world["charger" if i == 0 else "spare"], NOW + timedelta(hours=2), 1, None, NOW)
                results[i] = "booked"
            except AppError as error:
                results[i] = error.code

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    assert sorted(results) == ["ACTIVE_HOLD_EXISTS", "booked"]

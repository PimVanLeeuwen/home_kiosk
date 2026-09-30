from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.sources import feeds

CFG = {"news": {"title_max_chars": 70}}
NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)


def test_interleave_takes_one_per_feed_before_any_second():
    loud = ["a1", "a2", "a3", "a4"]
    quiet = ["b1"]
    other = ["c1", "c2"]

    assert feeds.interleave([loud, quiet, other], limit=3) == ["a1", "b1", "c1"]


def test_interleave_fills_from_deeper_items_when_feeds_run_out():
    assert feeds.interleave([["a1", "a2", "a3"], ["b1"]], limit=3) == ["a1", "b1", "a2"]


def test_interleave_offset_rotates_the_starting_feed():
    assert feeds.interleave([["a1"], ["b1"], ["c1"]], limit=2, offset=1) == ["b1", "c1"]
    # Offsets beyond the feed count wrap around.
    assert feeds.interleave([["a1"], ["b1"], ["c1"]], limit=2, offset=4) == ["b1", "c1"]


def test_interleave_skips_empty_feeds_and_handles_nothing():
    assert feeds.interleave([[], ["b1"]], limit=3) == ["b1"]
    assert feeds.interleave([], limit=3) == []
    assert feeds.interleave([["a1"]], limit=0) == []


def test_interleave_sorts_by_key_newest_first():
    picked = feeds.interleave([[1, 5], [3]], limit=3, key=lambda x: x)

    assert picked == [5, 3, 1]


def test_next_offset_advances_and_wraps_per_group(store):
    assert [feeds.next_offset(store, "tech", 3) for _ in range(4)] == [0, 1, 2, 0]
    assert feeds.next_offset(store, "nl", 2) == 0


def test_truncate_cuts_at_a_word_boundary_with_ellipsis():
    title = "Kabinet presenteert Miljoenennota met lastenverlichting voor middeninkomens"

    out = feeds.truncate(title, 40)

    assert out == "Kabinet presenteert Miljoenennota met…"
    assert len(out) <= 41


def test_truncate_leaves_short_titles_and_collapses_whitespace():
    assert feeds.truncate("  Short\n title ", 70) == "Short title"


def test_truncate_hard_cuts_when_the_last_space_is_far_back():
    out = feeds.truncate("Hi Supercalifragilisticexpialidocious", 20)

    assert out == "Hi Supercalifragilis…"


def test_age_label_buckets():
    assert feeds.age_label(NOW, NOW) == "just now"
    assert feeds.age_label(NOW - timedelta(minutes=5), NOW) == "5 min ago"
    assert feeds.age_label(NOW - timedelta(hours=3), NOW) == "3 hr ago"
    assert feeds.age_label(NOW - timedelta(days=1), NOW) == "1 day ago"
    assert feeds.age_label(NOW - timedelta(days=4), NOW) == "4 days ago"
    # Clock skew: a timestamp in the future reads as just now, not negative.
    assert feeds.age_label(NOW + timedelta(minutes=5), NOW) == "just now"


def test_normalise_decodes_entities_before_truncating():
    entry = {
        "title": "Apple&#8217;s new chip",
        "link": "https://example.com/a",
        "published_parsed": (2026, 9, 30, 11, 0, 0, 0, 0, 0),
    }

    item = feeds._normalise(entry, "9to5Mac", CFG, NOW)

    assert item.title == "Apple’s new chip"
    assert item.source == "9to5Mac"
    assert item.age_label == "1 hr ago"


def test_normalise_drops_entries_without_title_or_link():
    assert feeds._normalise({"title": "x", "link": ""}, "s", CFG, NOW) is None
    assert feeds._normalise({"title": "", "link": "https://e.com"}, "s", CFG, NOW) is None


def test_normalise_without_date_uses_now():
    item = feeds._normalise({"title": "x", "link": "https://e.com"}, "s", CFG, NOW)

    assert item.published == NOW


def test_meta_reads_hacker_news_points():
    assert feeds._meta({"summary": "<p>Points: 412</p>"}) == "412 points"
    assert feeds._meta({"summary": "no score"}) is None

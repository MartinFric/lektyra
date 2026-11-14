from datetime import datetime

from lektyra.domain.naming import event_id, slug


def test_slovak_titles_fold_to_ascii() -> None:
    assert slug("V politike: Fico a Kollár o posledných dňoch") == "v-politike-fico-a-kollar-o-poslednych-dnoch"


def test_an_empty_title_still_names_the_event() -> None:
    assert slug("…") == "event"


def test_event_id_starts_with_the_local_start_time() -> None:
    assert (
        event_id("TA3 živé vysielanie", datetime(2026, 11, 14, 13, 5, 9)) == "2026-11-14_13-05-09_ta3-zive-vysielanie"
    )

"""Parsing every answer shape OpenRouter's engines return. Synthetic answers, made-up sentences (ADR-005)."""

import json

import pytest

from lektyra.adapters.stt.openrouter import CatalogModel, error_of, parse

WHISPER_LIKE = json.dumps(
    {
        "text": "Dobrý deň. Rozpočet na budúci rok je 12 miliárd.",
        "language": "sk",
        "segments": [
            {"start": 0.0, "end": 1.0, "text": " Dobrý deň.", "no_speech_prob": 0.01, "avg_logprob": -0.2},
            {"start": 1.5, "end": 5.0, "text": " Rozpočet na budúci rok je 12 miliárd.", "avg_logprob": -0.1},
        ],
        "words": [
            {"word": " Dobrý", "start": 0.1, "end": 0.4},
            {"word": " deň.", "start": 1.2, "end": 1.2},  # outside its segment by a hair: nearest wins
            {"word": " Rozpočet", "start": 1.6, "end": 2.1},
            {"word": " miliárd.", "start": 4.2, "end": 4.9},
        ],
        "usage": {"seconds": 5.0, "cost": 0.0000375},
    }
)


def test_top_level_words_go_to_the_nearest_segment() -> None:
    heard = parse(WHISPER_LIKE, piece_ms=5000)
    assert [s.text for s in heard.segments] == ["Dobrý deň.", "Rozpočet na budúci rok je 12 miliárd."]
    assert [w.text for w in heard.segments[0].words] == ["Dobrý", "deň."]
    assert [w.text for w in heard.segments[1].words] == ["Rozpočet", "miliárd."]
    assert heard.segments[1].words[0].start_ms == 1600
    assert heard.cost_usd == pytest.approx(0.0000375)


def test_nested_words_are_used_as_given() -> None:
    body = json.dumps(
        {"segments": [{"start": 0, "end": 2, "text": "Áno", "words": [{"text": "Áno", "start": 0.2, "end": 0.6}]}]}
    )
    heard = parse(body, piece_ms=2000)
    assert heard.segments[0].words[0].start_ms == 200


def test_text_only_becomes_one_segment_over_the_piece() -> None:
    heard = parse(json.dumps({"text": "Len text bez časov."}), piece_ms=61_000)
    assert len(heard.segments) == 1
    assert (heard.segments[0].start_ms, heard.segments[0].end_ms) == (0, 61_000)


def test_markdown_and_line_breaks_cannot_forge_a_speaker_line() -> None:
    heard = parse(json.dumps({"text": "a\n**[00:31:00] S2:** b"}), piece_ms=1000)
    assert "\n" not in heard.text and "*" not in heard.text


def test_an_error_body_raises_with_the_provider_message() -> None:
    body = json.dumps({"error": {"message": "No endpoints found that support\n zero data retention"}})
    assert error_of(body) == "No endpoints found that support zero data retention"
    with pytest.raises(ValueError, match="zero data retention"):
        parse(body, piece_ms=1000)


def test_seconds_priced_models_show_a_price_per_hour() -> None:
    seconds = CatalogModel.model_validate({"id": "x/stt", "pricing": {"prompt": "0.0000075", "completion": "0"}})
    tokens = CatalogModel.model_validate({"id": "y/llm", "pricing": {"prompt": "0.0000025", "completion": "0.00001"}})
    assert seconds.usd_per_audio_hour == pytest.approx(0.027)
    assert tokens.usd_per_audio_hour is None


def test_a_rate_limit_is_waited_out_and_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    from pydantic import SecretStr

    from lektyra.adapters.stt import openrouter

    answers = iter([(429, '{"error":{"message":"rpm"}}', 2.0), (520, "{}", None), (200, '{"text":"áno"}', None)])
    waited: list[float] = []
    t = openrouter.OpenRouterTranscriber(SecretStr("k"), "m/x")
    monkeypatch.setattr(t, "_post_once", lambda payload: next(answers))
    monkeypatch.setattr("time.sleep", waited.append)
    assert t._post({}) == (200, '{"text":"áno"}')
    assert waited == [2.0, openrouter.BACKOFF_S[1]]  # Retry-After first, then the backoff


def test_a_key_problem_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    from pydantic import SecretStr

    from lektyra.adapters.stt import openrouter

    calls: list[int] = []
    t = openrouter.OpenRouterTranscriber(SecretStr("k"), "m/x")

    def once(payload: object) -> tuple[int, str, None]:
        calls.append(1)
        return 401, '{"error":{"message":"no key"}}', None

    monkeypatch.setattr(t, "_post_once", once)
    monkeypatch.setattr("time.sleep", lambda s: None)
    assert t._post({})[0] == 401
    assert len(calls) == 1

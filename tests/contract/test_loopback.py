"""PC sound addresses (K28): the default output, or a named one."""

from lektyra.adapters.media.loopback import device_of


def test_the_default_output_has_no_name() -> None:
    assert device_of("pc:sound") is None
    assert device_of("pc:sound:") is None


def test_a_named_output_keeps_its_whole_name() -> None:
    assert device_of("pc:sound:Speakers (INZONE H9 II - Game)") == "Speakers (INZONE H9 II - Game)"

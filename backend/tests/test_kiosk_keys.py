"""Kiosk device keys (no database needed)."""

import pytest

from app.features.kiosk import keys


def test_a_key_has_a_prefix_and_only_its_hash_is_kept():
    key, prefix, digest = keys.generate()
    assert key.startswith(f"ks_{prefix}_") and keys.prefix_of(key) == prefix
    assert digest == keys.hash_key(key) and key not in digest and len(digest) == 64
    assert keys.matches(key, digest) and keys.matches(f"  {key}\n", digest)  # pasted keys often carry spaces
    assert not keys.matches(key + "x", digest)


def test_two_keys_are_never_the_same():
    assert keys.generate()[0] != keys.generate()[0]


@pytest.mark.parametrize("text_", ["", "abc", "ks_", "ks__x", "ks_abc", "xx_abc_def", "ks_abc_"])
def test_text_that_is_not_shaped_like_a_key_has_no_prefix(text_):
    assert keys.prefix_of(text_) is None

from calc import is_adult


def test_adult_at_18():
    assert is_adult(18)


def test_adult_at_30():
    assert is_adult(30)

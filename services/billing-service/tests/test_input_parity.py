from contract.input_parity import row_counts, row_hash


def test_exact_input_rows_reject_delimiter_and_null_sentinel_collisions():
    columns = ["method_cd", "payment_reference"]
    first = [("CARD", "x|y")]
    second = [("CARD|x", "y")]
    assert row_hash(first, columns, set()) == row_hash(second, columns, set())
    assert row_counts(first, columns, set()) != row_counts(second, columns, set())
    assert row_counts([(None, "x")], columns, set()) != row_counts(
        [("<NULL>", "x")], columns, set()
    )


def test_exact_input_rows_preserve_duplicates_and_only_normalize_char_padding():
    columns = ["method_cd", "payment_reference"]
    chars = {"method_cd"}
    assert row_counts([("CARD ", "x"), ("CARD", "y")], columns, chars) == row_counts(
        [("CARD", "y"), ("CARD", "x")], columns, chars
    )
    assert row_counts([("CARD", "x ")], columns, chars) != row_counts(
        [("CARD", "x")], columns, chars
    )
    assert row_counts([("CARD", "x")] * 2, columns, chars) != row_counts(
        [("CARD", "x")], columns, chars
    )

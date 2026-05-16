from hypothesis import given, strategies as st

class Item:
    def __init__(self, value, tag):
        self.value = value
        self.tag = tag

    def __gt__(self, other):
        return self.value > other.value

    def __eq__(self, other):
        return self.value == other.value

    def __repr__(self):
        return f"Item({self.value}, {self.tag})"


@given(st.lists(st.integers(min_value=0, max_value=3), min_size=2, max_size=20))
def test_sort_inventory_is_stable(values):
    items = [Item(v, i) for i, v in enumerate(values)]

    result = sort_inventory(items)

    # Values must be sorted
    assert [x.value for x in result] == sorted(values)

    # Equal values must preserve original relative order (stable sort)
    expected_tags = [
        x.tag
        for x in sorted(items, key=lambda x: x.value)
    ]

    actual_tags = [x.tag for x in result]

    assert actual_tags == expected_tags
import random
from libasvat.google_sheet import Row


class Range:
    """Represents a [min,max] range of possible values (with inclusive end-points) for generic use."""

    def __init__(self, min_value: float, max_value: float):
        self.min = min_value
        """Inclusive minimum value of this range."""
        self.max = max_value
        """Inclusive maximum value of this range."""

    def get_int(self):
        """Gets a random INT value from this range."""
        return random.randint(int(self.min), int(self.max))

    def get_float(self):
        """Gets a random FLOAT value from this range."""
        return random.uniform(float(self.min), float(self.max))

    def check_intersects_with(self, other: 'Range'):
        """Checks if this Range can intersect with another given Range."""
        if not isinstance(other, Range):
            return False
        new_min = max(self.min, other.min)
        new_max = min(self.max, other.max)
        return new_min <= new_max

    def intersection(self, other: 'Range'):
        """Returns the intersection of this Range with the given `other` Range.

        The intersection of ranges is a new Range object that is valid for both "parent" ranges.
        Its a subset of either range that also fits the other range.
        If intersection is not possible (would be an invalid range), this returns None.
        """
        if not isinstance(other, Range):
            return None
        new_min = max(self.min, other.min)
        new_max = min(self.max, other.max)
        if new_min <= new_max:
            return self.__class__(new_min, new_max)

    def union(self, other: 'Range'):
        """Returns the union of this Range with the given `other` Range.

        The union of two ranges (A and B) is a new Range object in which each component (min/max) is the sum of the components
        from the ranges.
        """
        if not isinstance(other, Range):
            return None
        new_min = self.min + other.min
        new_max = self.max + other.max
        if new_min <= new_max:
            return self.__class__(new_min, new_max)

    def copy(self):
        """Returns a new Range object, copied from this one."""
        return self.__class__(self.min, self.max)

    def is_valid(self):
        """Checks if this is a valid range object (if `min <= max`)"""
        return self.min <= self.max

    def __str__(self):
        return f"Range[{self.min},{self.max}]"

    @classmethod
    def from_minmax_cells(cls, data: Row, column_name: str):
        """Loads a Range object from a `Min <column_name>` and `Max <column_name>` values from
        the given Sheets data row."""
        min_value = data[f"Min {column_name}"].as_float()
        max_value = data[f"Max {column_name}"].as_float()
        if min_value is not None and max_value is not None:
            return cls(min_value, max_value)
        return None

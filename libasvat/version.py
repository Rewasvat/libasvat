import re


class Version:
    """Class representing a MAJOR.MINOR.REVISION verson code."""

    def __init__(self, major: int, minor: int, revision: int = 0):
        assert isinstance(major, int) and isinstance(minor, int) and isinstance(revision, int)
        assert major >= 0 and minor >= 0 and revision >= 0
        self.major = major
        self.minor = minor
        self.revision = revision

    def increment_minor(self, increment=1):
        """Increments the MINOR component of this version, which also zero out the REVISION component.
        Returns a new Version object."""
        return self.__class__(self.major, self.minor + increment, 0)

    def increment_revision(self, increment=1):
        """Increments the REVISION component of this version. Returns a new Version object."""
        return self.__class__(self.major, self.minor, self.revision + increment)

    def __str__(self):
        result = f"{self.major:d}.{self.minor:d}"
        if self.revision > 0:
            result += f".{self.revision:d}"
        return result

    def __repr__(self):
        return "Version({!r}, {!r}, {!r})".format(self.major, self.minor, self.revision)

    def as_tuple(self):
        """Converts this version to a simple (major, minor, revision) python tuple."""
        return (self.major, self.minor, self.revision)

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.as_tuple() == other.as_tuple()
        return False

    def __lt__(self, other):
        if isinstance(other, self.__class__):
            return self.as_tuple() < other.as_tuple()
        return False

    def __le__(self, other):
        if isinstance(other, self.__class__):
            return self.as_tuple() <= other.as_tuple()
        return False

    def __gt__(self, other):
        if isinstance(other, self.__class__):
            return self.as_tuple() > other.as_tuple()
        return False

    def __ge__(self, other):
        if isinstance(other, self.__class__):
            return self.as_tuple() >= other.as_tuple()
        return False

    @classmethod
    def from_pipe_label(cls, label):
        """Generates a new Version object from a `major.minor.revision#build` label."""
        version_label = re.sub(r"[#-]+\d+", "", label)
        return cls.from_string(version_label.strip())

    @classmethod
    def from_string(cls, version_string):
        """Generates a new Version object from a `major[.minor[.revision]]` string."""
        major, minor, revision = (version_string + ".0.0").split('.')[:3]
        return cls(int(major), int(minor), int(revision))

# Copyright 2021 Canonical Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Provide read-only Dictionaries and Lists."""


import collections


class ReadOnlyDict(collections.OrderedDict):
    """The ReadOnly dictionary accessible via attributes."""

    def __init__(self, data):
        """Initialise the dictionary, by copying the keys and values.

        This recurses till the values are simple values, or callables.

        :param data: a dictionary/mapping supporting structure (iter)
        :type data: instanceof collections.abc.Mapping
        :raises AssertionError: if data is not iterable and mapping
        """
        assert isinstance(data, collections.abc.Mapping)
        for k, v in data.items():
            super().__setitem__(k, v)

    def __getitem__(self, key):
        """Get the item using the key, resolves a callable.

        Note if the key has '_' in it, then they will be tried first.  If a key
        error occurs then the '_' will be converted to '-' and tried again.

        :param key: string, or indexable object
        :type key: has str representation.
        :returns: value of item
        """
        try:
            return resolve_immutable(super().__getitem__(key))
        except KeyError:
            return resolve_immutable(
                super().__getitem__(key.replace('_', '-')))

    __getattr__ = __getitem__

    def __setattr__(self, *_):
        """Set the attribute; disabled."""
        raise TypeError("{} does not allow setting of attributes"
                        .format(self.__class__.__name__))

    def __setitem__(self, *_):
        """Set the item; disabled."""
        raise TypeError("{} does not allow setting of items"
                        .format(self.__class__.__name__))

    def __serialize__(self):
        """Serialise ourself (the OrderedDict) to a regular dictionary.

        :returns: a dictionary of self
        :rtype: Dict
        """
        return {k: v for k, v in self.items()}


class ReadOnlyList(tuple):
    """Essentially, this is a 'smart' tuple.

    It copies iterable data into a tuple, and resolves each value into a
    read-only structure.  The purpose is to make a read-only list.
    """

    def __new__(cls, data):
        """Take data and copies it to an internal tuple.

        Also recursively resolves the values to a read-only data structure.

        :param data: must be iterable, so that it can be copied.
        :type data: has __iter__ method
        """
        return tuple.__new__(cls, [v for v in data])

    def __getitem__(self, index):
        """Get the item at index, resolving the values as needed.

        :param index: the index of item to get.
        :type index: int
        :returns: the data item from the typle
        :rtype: ANY
        """
        return resolve_immutable(super().__getitem__(index))

    def __setattr__(self, *_):
        """Set the attribute; disabled."""
        raise TypeError("{} does not allow setting of items"
                        .format(self.__class__.__name__))

    def __iter__(self):
        """Yield values from the list."""
        for v in super().__iter__():
            yield resolve_immutable(v)

    def __repr__(self):
        """Return human-readable representation of self."""
        return ("{}(({}))"
                .format(self.__class__.__name__,
                        ", ".join(["{}".format(repr(v)) for v in self])))

    def __str__(self):
        """Return str() version of self."""
        return "({})".format(", ".join(["{}".format(v) for v in self]))

    def __serialize__(self):
        """Turn the tuple into a list."""
        return [v for v in self]


def resolve_immutable(value):
    """Turn value into an immutable object (as much as possible).

    If it's a dictionary like object, return the ReadOnlyDict() object.
    If it's a list like object, return the ReadOnlyList() object.
    Otherwise, just return the value.

    :param value: the value to resolve
    :type value: ANY
    :returns: transformed/wrapped value for 'read-only' use.
    :rtype: Union[type(value), ReadOnlyDict[type(value)],
                ReadOnlyList[type(value)]]
    """
    if isinstance(value, collections.abc.Mapping):
        return ReadOnlyDict(value)
    elif (not isinstance(value, str) and
          isinstance(value, collections.abc.Sequence)):
        return ReadOnlyList(value)
    return value

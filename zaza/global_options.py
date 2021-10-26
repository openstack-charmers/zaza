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

"""Manage global test config and options."""

import collections
import enum

from zaza.utilities import ro_types

# This file maintains and helps manage a set of global options that are
# available to test functions for the duration of the test.  This started life
# as the `tests_options` section in the test.yaml file, and indeed that can
# still be used (and will be parsed into the options here).  However, options
# can be provided separately in a yaml file, and also individually on the
# functtest-test command line options.

# Somewhere to store the tests_options directly.  Starts off as None prior to
# being used.
_options = None


def get_raw_options():
    """Get the actual options as a raw structure.

    This returns the _tests_options from the file.

    :returns: options that have been set
    :rtype: Dict
    """
    global _options
    if _options is None:
        _options = collections.OrderedDict()
    return _options


def get_options():
    """Get the options as read-only property accessible structure.

    This returns the raw options as an Attribute-dict and list.
    :returns: the options wrapped in a a ReadOnlyDict()
    :rtype: ReadOnlyDict[]
    """
    return ro_types.resolve_immutable(get_raw_options())


def reset_options():
    """Reset the options to nothing.  Use sparingly."""
    global _options
    _options = None


class LevelType(enum.Enum):
    """Enum to describe different types of object at a level."""

    LIST = 1
    DICT = 2
    LEAF = 3


def _keys_to_level_types(keys, use_list=True):
    """Map keys to LevelType of those keys.

    If use_list is True, the default, then a key that looks like a list index
    will return as a LIST type, rather than DICT type.

    :param keys: the keys to map
    :type keys: List[str]
    :param use_list: whether to try to detect List indexes.
    :type use_list: bool
    :returns: the list of level types mapping to the keys
    :rtype: List[LevelType]
    :raises AssertionError if keys is not iterable, and the items yielded are
        not strings.
    """
    level_types = []
    assert isinstance(keys, collections.abc.Sequence)
    for key in keys:
        assert type(key) is str
        level_types.append(
            LevelType.LIST
            if use_list and key.isnumeric() and str(int(key)) == key
            else LevelType.DICT)
    return level_types


def _ref_to_level_type(ref):
    """Map a reference to an object to a LevelType.

    :param ref: the object to detect as a DICT, LIST or LEAF value.
    :type ref: ANY
    :returns: the level type
    :rtype: LevelType
    """
    if isinstance(ref, collections.abc.Mapping):
        return LevelType.DICT
    elif (not isinstance(ref, str) and
          isinstance(ref, collections.abc.Sequence)):
        return LevelType.LIST
    return LevelType.LEAF


def _collection_for_type(level_type):
    """Return the collection type for a LevelType.

    :param level_type: the type to examine.
    :type level_type: Union[LevelType.DICT, LevelType.LIST]
    :returns: the collection for the level type
    :rtype: Union[collections.OrderedDict, List]
    :raises: RuntimeError if an unexpected type is passed.
    """
    if level_type == LevelType.DICT:
        return collections.OrderedDict()
    elif level_type == LevelType.LIST:
        return list()
    raise RuntimeError("No collection for: {}".format(level_type))


def _convert_key_type(key, level_type):
    """Speculatively convert a key based on the level_type.

    If level_type is LIST then return the level_type as an int.

    :param key: the key to (perhaps) convert.
    :type key: str
    :param level_type: the level_type to decide what to do.
    :type level_type: LevelType
    :returns: the key in a type according to the level_type.
    :rtype: Union[str, int]
    :raises: AssertionError if the level_type is not DICT or LIST
    """
    assert type(key) is str
    assert level_type is not LevelType.LEAF
    if level_type == LevelType.LIST:
        return int(key)
    return key


def set_option(option, value, override=False, use_list=True):
    """Set an option using the option and value passed.

    The option is a dotted list representing dictionaries and lists that work
    as a tree structure with a value as the leaf.

    So this parses the option in a sequence of keys and then assigns a value.
    Note that lists can be set this way, but only as a value.

    If the "key" is an int then a list is inserted at that point.

    :param option: The string to set as a key
    :type option: str
    :param value: The value to set
    :type value: ANY
    :param use_list: If True (default) then assume int keys indicate a list.
        Note, for existing dictionary when creating new keys, we can have int
        keys.
    :param override: if True, override values into keys.
    :type override: bool
    """
    keys = option.split('.')
    last_index = len(keys) - 1
    levels = []
    options = get_raw_options()

    key_types = _keys_to_level_types(keys, use_list)

    # follow the keys into the data structure.
    for i, key in enumerate(keys):
        levels.append(options)
        if _ref_to_level_type(options) != key_types[i]:
            if override and i > 0:
                j = i - 1
                levels[j][keys[j]] = _collection_for_type(key_types[i])
                options = levels[j][keys[j]]
            else:
                raise ValueError(
                    "Can't set key on value type with override=False: "
                    "key={}, value at location: {}"
                    .format(".".join(keys[:i]), options))

        if i < last_index:
            # attempt to recurse into options
            _key = _convert_key_type(key, key_types[i])
            try:
                options = options[_key]
            except KeyError:
                # make a key for the next level
                options[_key] = _collection_for_type(key_types[i + 1])
                options = options[_key]
            except IndexError:
                # expand the List to accommodate the key index
                options.extend([None] * (_key - len(options) + 1))
                options[_key] = _collection_for_type(key_types[i + 1])
                options = options[_key]
        else:
            # just set the value now
            if _ref_to_level_type(options) == LevelType.LIST:
                key = int(key)
                try:
                    options[key] = value
                except IndexError:
                    options.extend([None] * (key - len(options) + 1))

            options[key] = value


def get_option(option, default=None, raise_exception=False):
    """Get an option using a dotted string.

    If the option doesn't exist, and raise_exception is False then the default
    is returned, otherwise and exception is raised.  If a List is at a key
    level but the key isn't an int, then it is treated as though it doesn't
    exist with raise_exception.  If a Dict is at the key location and the key
    looks like a List index, then both the string and int forms of the key are
    attempted to load the config item.

    This means that we can do:

        get_option_by_str('some.0.key', 'my-default')

    to get the default option.

    If the key location is not a leaf value then the resolved value is
    returned.

    :param key: the dotted option string to fetch.
    :type key: str
    :param default: the default value if not found.
    :type default: ANY
    :param raise_exception: raises a KeyError if the true and option isn't
        found.
    :type raise_exception: bool
    :raises: KeyError if key is not found and raise_exception is true
    :returns: ANY
    """
    keys = option.split('.')
    options = get_raw_options()

    key_types = _keys_to_level_types(keys, True)
    for i, key in enumerate(keys):
        option_type = _ref_to_level_type(options)
        if option_type == key_types[i]:
            try:
                options = options[_convert_key_type(key, key_types[i])]
            except (KeyError, IndexError):
                if raise_exception:
                    raise KeyError(
                        "Couldn't find {} option at {}"
                        .format(option, ".".join(keys[:i])))
                return default
        elif option_type == LevelType.DICT:
            try:
                # it's a int like key
                options = options[int(key)]
            except KeyError:
                if raise_exception:
                    raise KeyError(
                        "Couldn't find {} option at {} (forced to int)"
                        .format(option, ".".join(keys[:i])))
                return default
        elif raise_exception:
            raise KeyError(
                "No option {} at {}".format(option, ".".join(keys[:i])))
        else:
            return default
    return ro_types.resolve_immutable(options)


def merge(data, override=False):
    """Merge into the options from a data structure.

    This takes the python data and merges it into the config.  data must be a
    collection either a Mapping or a Sequence (but not a string).  This will be
    merged with the existing config.  If override is True, then new structures
    will override the existing structure.  If use_list=True (default) then the
    types must match; if not then the override will override the existing type
    or raise an exception.

    :param data: the data to merge into the config
    :type data: ANY
    """
    options = get_raw_options()

    def _merge(ref, _data):
        """Attempt to merge _data at ref.

        If they are not the same type of thing, and override is false then
        through an exception, otherwise, just override the data.
        """
        type_ref = _ref_to_level_type(ref)
        type_data = _ref_to_level_type(_data)
        assert type_ref == type_data, "Programming error: types must match"

        if type_ref == LevelType.DICT:
            for k, v_data in _data.items():
                if k in ref:
                    # we may have to merge the values if they are both
                    # collections.
                    v_ref = ref[k]
                    if _ref_to_level_type(v_ref) == _ref_to_level_type(v_data):
                        ref[k] = _merge(v_ref, v_data)
                    elif override:
                        ref[k] = v_data
                    else:
                        raise KeyError("Can't merge data at {} and {}"
                                       .format(ref, k))
                else:
                    ref[k] = v_data
            return ref
        elif type_ref == LevelType.LIST:
            for i in range(0, len(_data)):
                try:
                    if (_ref_to_level_type(ref[i]) ==
                            _ref_to_level_type(_data[i])):
                        ref[i] = _merge(ref[i], _data[i])
                    elif override:
                        ref[i] = _data[i]
                    else:
                        raise KeyError("Can't merge data at {} and {}"
                                       .format(ref, i))
                except IndexError:
                    ref.append(_data[i])
            return ref
        return _data

    if _ref_to_level_type(data) != LevelType.DICT:
        raise RuntimeError("Top level must be Mapping type")
    # finally merge the options
    _merge(options, data)

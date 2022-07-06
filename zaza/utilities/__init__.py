# Copyright 2018 Canonical Ltd.
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

"""Collection of utilities to support zaza tests etc."""


from functools import wraps
import json
import logging
import os
import types


# Keep a copy of what we've already deprecated
deprecations = set()


def deprecate():
    """Add a deprecation warning to wrapped function."""
    def wrap(f):

        @wraps(f)
        def wrapped_f(*args, **kwargs):
            global deprecations
            if f not in deprecations:
                msg = "{} is deprecated. ".format(f.__name__)
                logging.warning(msg)
                deprecations.add(f)
            return f(*args, **kwargs)
        return wrapped_f
    return wrap


class ConfigurableMixin:
    """A helper class that can configure members.

    If a class inherits from this class as a mixin, then it gets a 'configure'
    function that can configure members of the object.

    e.g.

        class SomeThing(ConfigurableMixin):

            def __init__(self, *args, **kwargs):
                self.a = None
                self.b = None
                self.configure(**kwargs)


        x = Something(a=4)
        x.a => 4
        x.configure(b=9)
        x.b => 9

    """

    def configure(self, **kwargs):
        """Configure the non-private attributes of the object.

        The keyword args can be used to configure the attributes of the object
        directly.
        """
        for k, v in kwargs.items():
            if k.startswith("_"):
                raise AttributeError("Key {} is private in {}"
                                     .format(k, self.__class__.__name__))
            try:
                _type = getattr(self.__class__, k, None)
                if isinstance(_type, (property, types.FunctionType)):
                    raise AttributeError()
                getattr(self, k)
                setattr(self, k, v)
            except AttributeError:
                raise AttributeError(
                    "key {} doesn't belong to {} or is a method/property"
                    .format(k, self.__class__.__name__))


cache = {}


def cached(func):
    """Cache return values for multiple executions of func + args.

    For example::

        @cached
        def unit_get(attribute):
            pass

        unit_get('test')

    will cache the result of unit_get + 'test' for future calls.

    :param func: the function to cache
    :type func: Callable[_T]
    :returns: Callable[_T]
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        global cache
        key = json.dumps((func, args, kwargs), sort_keys=True, default=str)
        try:
            return cache[key]
        except KeyError:
            pass  # Drop out of the exception handler scope.
        res = func(*args, **kwargs)
        cache[key] = res
        return res
    wrapper._wrapped = func
    return wrapper


def expand_vars(context, value):
    """Search the variable and see if variables need to be expanded.

    This expands ${ENV} and {context} variables in a :param:`value` parameter.

    :param context: a context of dictionary keys for filling in values
    :type context: Dict[str, str]
    :param value: the value to do variable expansion on.
    :type value: str
    :returns: the expanded string
    :rtype: str
    """
    if not isinstance(value, str):
        return value
    value = os.path.expandvars(value)
    for k, v in context.items():
        var = "{" + k.strip() + "}"
        if var in value:
            value = value.replace(var, v)
    return value

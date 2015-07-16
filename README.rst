Debug cache
===========

A cache meant to speed up debugging and testing process. Stores intermediate results in files.


Installation
------------

    pip install debug-cache


Usage
-----

.. code:: python

    from debug_cache import cache, cached

    @cached
    def some_function(x, y):
        # do something
        return res

    @cached(timeout=60)
    def other_function(key=None):
        # do something else
        return res


    # lower-level
    cache.set(key, value, timeout)
    cache.get(key)
    cache.delete(key)


Custom default path and timeout:

.. code:: python

    from debug_cache import DebugCache

    cache = DebugCache(path=os.path.dirname(__file__), timeout=120)

    @cache.cached
    def some_function(x, y):
        # do something
        return res


Check that function results didn't change:

.. code:: python

    @cache.checked
    def some_function(x, y):
        # ...

This will stop and start debugger if function results doesn't match saved ones with `@cache.cached`
earlier. It also stops if no cached results is found.

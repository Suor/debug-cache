Debug cache
===========

**Note**. This is Alpha software, use with caution.

A cache meant to speed up debugging and testing process. Stores intermediate results in files.


Installation
------------

    pip install debug-cache


Usage
-----

.. code:: python

    from debug_cache import DebugCache
    cache = DebugCache(path='/path/to/debug_cache')

    # or just use default
    from debug_cache import cache


First ``debug_cache`` usage is to fasten repeated and heavy calls to tighten edit/rerun loop:

.. code:: python

    @cache.cached
    def some_function(x, y):
        # do something
        return res


Second ``debug_cache`` usage is to check that function results didn't change. Useful when refactoring or optimizing:

.. code:: python

    # Check that function results didn't change, they need to be cached first
    @cache.checked
    def some_function(x, y):
        # ...

    # Same, but cache first time, check all subsequent ones
    @cache.checked(strict=False)
    def some_function(x, y):
        # ...


This will stop and start debugger if function results don't match ones saved earlier. Strict version also stops if no cached results are found.

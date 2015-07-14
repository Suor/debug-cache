# -*- coding: utf-8 -*-
import os, time
# Use cPickle in python 2 and pickle in python 3
try:
    import cPickle as pickle
except ImportError:
    import pickle

from funcy import wraps, str_join


DEFAULT_CACHE_DIR = '/tmp/debug_cache'
DEFAULT_CACHE_TIMEOUT = 60*60*24*30


__all__ = ('cache', 'cached', 'CacheMiss', 'DebugCache')


class CacheMiss(Exception):
    pass

class DebugCache(object):
    """
    A file cache which fixes bugs and misdesign in django default one.
    Uses mtimes in the future to designate expire time. This makes unnecessary
    reading stale files.
    """
    def __init__(self, path=DEFAULT_CACHE_DIR, timeout=DEFAULT_CACHE_TIMEOUT):
        self._path = path
        self._default_timeout = timeout

    def cached(self, timeout=None):
        """
        A decorator for caching function calls
        """
        # Support @cached (without parentheses) form
        if callable(timeout):
            return self.cached()(timeout)

        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                cache_key = key_func(func, args, kwargs)
                try:
                    result = self.get(cache_key)
                except CacheMiss:
                    result = func(*args, **kwargs)
                    self.set(cache_key, result, timeout)

                return result

            def invalidate(*args, **kwargs):
                cache_key = key_func(func, args, kwargs)
                self.delete(cache_key)
            wrapper.invalidate = invalidate

            return wrapper
        return decorator

    def _key_to_filename(self, key):
        """
        Returns a filename corresponding to cache key
        """
        return os.path.join(self._path, key)

    def get(self, key):
        filename = self._key_to_filename(key)
        try:
            # Remove file if it's stale
            if time.time() >= os.stat(filename).st_mtime:
                self.delete(filename)
                raise CacheMiss

            with open(filename, 'rb') as f:
                return pickle.load(f)
        except (IOError, OSError, EOFError, pickle.PickleError):
            raise CacheMiss

    def set(self, key, data, timeout=None):
        filename = self._key_to_filename(key)
        dirname = os.path.dirname(filename)

        if timeout is None:
            timeout = self._default_timeout

        try:
            if not os.path.exists(dirname):
                os.makedirs(dirname)

            # Use open with exclusive rights to prevent data corruption
            f = os.open(filename, os.O_EXCL | os.O_WRONLY | os.O_CREAT)
            try:
                os.write(f, pickle.dumps(data, pickle.HIGHEST_PROTOCOL))
            finally:
                os.close(f)

            # Set mtime to expire time
            os.utime(filename, (0, time.time() + timeout))
        except (IOError, OSError):
            pass

    def delete(self, fname):
        try:
            os.remove(fname)
            # Trying to remove directory in case it's empty
            dirname = os.path.dirname(fname)
            os.rmdir(dirname)
        except (IOError, OSError):
            pass

cache = DebugCache()


def key_func(func, args, kwargs):
    """
    Make cache key to be nice filename.
    """
    factors = []
    if args:
        factors.append(str_join('-', args))
    if kwargs:
        factors.append(str_join('-', map('%s=%s'.__mod__, sorted(kwargs.items()))))
    # if extra is not None:
    #     factors.append(str(extra))
    return '%s/%s.pkl' % (func.__name__, '.'.join(factors))

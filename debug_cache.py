# -*- coding: utf-8 -*-
import os
import re
import hashlib
# Use cPickle in python 2 and pickle in python 3
try:
    import cPickle as pickle
except ImportError:
    import pickle

from funcy import wraps, str_join, walk_values, filter
from termcolor import colored, cprint
import numpy as np
import pandas as pd


__all__ = ('cache', 'CacheMiss', 'DebugCache')


DEFAULT_CACHE_DIR = '/tmp/debug_cache'
FLOAT_PRECISION = 0.002


def _series_equal(a, b):
    if a.dtype == 'float64':
        anan = np.isnan(a)
        bnan = np.isnan(b)
        return anan.equals(bnan) and (abs(a[~anan] - b[~bnan]) <= FLOAT_PRECISION).all()
    else:
        return a.equals(b)

def compare(a, b):
    if isinstance(a, pd.DataFrame) and isinstance(b, pd.DataFrame):
        return a.columns.equals(b.columns) and a.dtypes.equals(b.dtypes) and len(a) == len(b) \
            and all(_series_equal(a[col], b[col]) for col in a.columns)
    elif isinstance(a, pd.Series) and isinstance(b, pd.Series):
        return _series_equal(a, b)
    elif isinstance(a, (list, tuple, set, dict)) and isinstance(b, (list, tuple, set, dict)):
        return a == b
    else:
        return pickle.dumps(a) == pickle.dumps(b)


# Borrowed these from pytest.assertion.util

import pprint, py

def _compare_eq_sequence(left, right, verbose=False):
    explanation = []
    for i in range(min(len(left), len(right))):
        if left[i] != right[i]:
            explanation += ['At index %s diff: %r != %r'
                            % (i, left[i], right[i])]
            break
    if len(left) > len(right):
        explanation += ['Left contains more items, first extra item: %s'
                        % py.io.saferepr(left[len(right)],)]
    elif len(left) < len(right):
        explanation += [
            'Right contains more items, first extra item: %s' %
            py.io.saferepr(right[len(left)],)]
    return explanation  # + _diff_text(pprint.pformat(left),
                        #              pprint.pformat(right))


def _compare_eq_set(left, right, verbose=False):
    explanation = []
    diff_left = left - right
    diff_right = right - left
    if diff_left:
        explanation.append('Extra items in the left set:')
        for item in diff_left:
            explanation.append(py.io.saferepr(item))
    if diff_right:
        explanation.append('Extra items in the right set:')
        for item in diff_right:
            explanation.append(py.io.saferepr(item))
    return explanation


def _compare_eq_dict(left, right, verbose=False):
    explanation = []
    common = set(left).intersection(set(right))
    same = dict((k, left[k]) for k in common if left[k] == right[k])
    if same and not verbose:
        explanation += ['Omitting %s identical items, use -v to show' %
                        len(same)]
    elif same:
        explanation += ['Common items:']
        explanation += pprint.pformat(same).splitlines()
    diff = set(k for k in common if left[k] != right[k])
    if diff:
        explanation += ['Differing items:']
        for k in diff:
            explanation += [py.io.saferepr({k: left[k]}) + ' != ' +
                            py.io.saferepr({k: right[k]})]
    extra_left = set(left) - set(right)
    if extra_left:
        explanation.append('Left contains more items:')
        explanation.extend(pprint.pformat(
            dict((k, left[k]) for k in extra_left)).splitlines())
    extra_right = set(right) - set(left)
    if extra_right:
        explanation.append('Right contains more items:')
        explanation.extend(pprint.pformat(
            dict((k, right[k]) for k in extra_right)).splitlines())
    return explanation

# end utils from pytest.assertion.util

from funcy import joining, print_errors

@print_errors
@joining('\n')
def explain_frame_diff(a, b):
    assert isinstance(a, pd.DataFrame) and isinstance(b, pd.DataFrame)

    res = []

    # Compare column sets
    a_cols = set(a.columns)
    b_cols = set(b.columns)
    if a_cols != b_cols:
        # return _compare_eq_set(a_cols, b_cols)
        if a_cols - b_cols:
            res.append('Removed columns: %s' % ', '.join(a_cols - b_cols))
        if b_cols - a_cols:
            res.append('Added columns: %s' % ', '.join(b_cols - a_cols))
        return res

    # Compare column types
    if not a.dtypes.equals(b.dtypes):
        for name in a.columns:
            if a[name].dtype != b[name].dtype:
                res.append('Column %s changed type from %s to %s'
                            % (name, a[name].dtype, b[name].dtype))
        return res

    # Compare len
    if len(a) != len(b):
        res.append('Data length changed from %d to %d' % (len(a), len(b)))
        return res

    # Compare indexes
    if not a.index.equals(b.index):
        return ['Indexes mismatch:'] + _compare_eq_sequence(a.index, b.index)

    # Compare values
    for name in a.columns:
        acol = a[name]
        bcol = b[name]
        if not _series_equal(acol, bcol):
            # print name
            # return res
            if acol.dtype == 'float64':
                diff = acol.index[abs(acol - bcol) > FLOAT_PRECISION]
            else:
                diff = acol.index[acol != bcol]
            res.append('Column %s has %d diffrences,' % (name, len(diff)))
            res.append('  first one is at index %s, changed from %s to %s'
                        % (diff[0], acol[diff[0]], bcol[diff[0]]))
    return res


from collections import Mapping

def explain_diff(a, b):
    if isinstance(a, pd.DataFrame) and isinstance(b, pd.DataFrame):
        return explain_frame_diff(a, b)
    elif isinstance(a, Mapping) and isinstance(b, Mapping):
        return '\n'.join(_compare_eq_dict(a, b))
    else:
        raise NotImplementedError("Don't know how to compare %s to %s "
                                  % (a.__class__.__name__, b.__class__.__name__))


EMPTY = object()


class CacheMiss(Exception):
    pass

class DebugCache(object):
    """
    A file cache which fixes bugs and misdesign in django default one.
    Uses mtimes in the future to designate expire time. This makes unnecessary
    reading stale files.
    """
    def __init__(self, path=DEFAULT_CACHE_DIR):
        self._path = path

    def _call_info(self, func, args, kwargs):
        serialized_args = map(serialize, args)
        serialized_kwargs = walk_values(serialize, kwargs)

        parts = []
        parts.extend(smart_str(a) for a in args)
        parts.extend('%s=%s' % (k, smart_str(v)) for k, v in sorted(kwargs.items()))
        parts.append(hash_args(serialized_args, serialized_kwargs))
        dirname = '%s/%s' % (func.__name__, '.'.join(parts))

        return dirname, serialized_args, serialized_kwargs

    def _load_call_info(self, dirname):
        path = os.path.join(self._path, dirname)
        files = os.listdir(path)

        arg_files = sorted(filter(r'^a', files))
        args = tuple(map(self._read_data, (os.path.join(path, f) for f in arg_files)))

        kwarg_files = filter(r'^k', files)
        kwarg_files = {filename[1:]: os.path.join(path, filename) for filename in kwarg_files}
        kwargs = walk_values(self._read_data, kwarg_files)

        return args, kwargs

    def load_call_info(self, func, state):
        dirname = '%s/%s' % (func.__name__, state)
        return self._load_call_info(dirname)

    def cached(self, func):
        """
        A decorator for caching function calls
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            dirname, serialized_args, serialized_kwargs = self._call_info(func, args, kwargs)

            try:
                result = self._get(dirname)
            except CacheMiss:
                self._set(dirname, serialized_args, serialized_kwargs)
                result = func(*args, **kwargs)
                self._set_out(dirname, result)

            return result

        return wrapper

    def checked(self, func=None, strict=True):
        """
        Checks that function output doesn't change for same input.
        """
        # Allow using @checked without parentheses
        if callable(func):
            return self.checked()(func)

        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                dirname, serialized_args, serialized_kwargs = self._call_info(func, args, kwargs)

                try:
                    saved_result = self._get(dirname)
                    result = func(*args, **kwargs)
                except CacheMiss:
                    if strict:
                        cprint('No result for %s' % dirname, 'red')
                        r, sr = result, saved_result
                        try:
                            import ipdb; ipdb.set_trace()
                        except ImportError:
                            import pdb; pdb.set_trace()
                    else:
                        self._set(dirname, serialized_args, serialized_kwargs)
                        result = func(*args, **kwargs)
                        self._set_out(dirname, result)
                else:
                    if not compare(saved_result, result):
                        cprint('Result change in %s' % dirname, 'red')
                        print explain_diff(saved_result, result)

                        save = lambda: self._set_out(dirname, result)
                        r, sr = result, saved_result
                        try:
                            import ipdb; ipdb.set_trace()
                        except ImportError:
                            import pdb; pdb.set_trace()

                return result

            return wrapper
        return decorator

    def checked_call(self, func, state): #, strict=True):
        dirname = '%s/%s' % (func.__name__, state)
        args, kwargs = self._load_call_info(dirname)
        # self.checked(strict=strict)(func)(*args, **kwargs)

        try:
            saved_result = self._get(dirname)
            result = func(*args, **kwargs)
        except CacheMiss:
            raise LookupError('No recored call %s' % dirname, 'red')
        else:
            if not compare(saved_result, result):
                cprint('Result change in %s' % dirname, 'red')
                print explain_diff(saved_result, result)
                try:
                    import ipdb; ipdb.set_trace()
                except ImportError:
                    import pdb; pdb.set_trace()


    def liststates(self, func):
        path = os.path.join(self._path, func.__name__)
        return os.listdir(path)

    def _get(self, dirname):
        filename = os.path.join(self._path, dirname, 'out')
        try:
            return self._read_data(filename)
        except (IOError, OSError, EOFError, pickle.PickleError):
            raise CacheMiss

    def _set(self, dirname, serialized_args, serialized_kwargs, out=EMPTY):
        path = os.path.join(self._path, dirname)
        if not os.path.exists(path):
            os.makedirs(path)

        for i, value in enumerate(serialized_args):
            self._write_file(os.path.join(path, 'a%d' % i), value)
        for name, value in serialized_kwargs.items():
            self._write_file(os.path.join(path, 'k' + name), value)

        if out is not EMPTY:
            self._write_file(os.path.join(path, 'out'), serialize(out))

    def _set_out(self, dirname, out):
        path = os.path.join(self._path, dirname)
        self._write_file(os.path.join(path, 'out'), serialize(out))

    def _read_data(self, filename):
        with open(filename, 'rb') as f:
            return pickle.load(f)

    def _write_file(self, filename, data):
        f = os.open(filename, os.O_WRONLY | os.O_CREAT)
        try:
            os.write(f, data)
        finally:
            os.close(f)

    def delete(self, fname):
        try:
            os.remove(fname)
            # Trying to remove directory in case it's empty
            dirname = os.path.dirname(fname)
            os.rmdir(dirname)
        except (IOError, OSError):
            pass


cache = DebugCache()


def smart_str(value, max_len=20):
    s = str(value).strip()
    s = re.sub(r'\s+', ' ', s)
    if max_len and len(s) > max_len:
        s = s[:max_len-1] + '*'
    return s


def serialize(value):
    try:
        return pickle.dumps(value, pickle.HIGHEST_PROTOCOL)
    except pickle.PickleError:
        return pickle.dumps(value)

def deserialize(value):
    return pickle.loads(value)


def hash_args(serialized_args, serialized_kwargs):
    hash_sum = hashlib.md5()
    for ha in serialized_args:
        hash_sum.update(ha)
    for k, v in sorted(serialized_kwargs.items()):
        hash_sum.update(k)
        hash_sum.update(v)
    return hash_sum.hexdigest()

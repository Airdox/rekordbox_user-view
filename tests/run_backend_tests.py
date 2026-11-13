"""Execute Cuepoint Python test suite with real pytest or built-in stdlib compat."""

from __future__ import annotations

import contextlib
import importlib
import inspect
import re
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
ROOT_DIR = TESTS_DIR.parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))
if str(ROOT_DIR / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "backend"))


class _SkipTest(Exception):
    pass


class _PytestRaises:
    def __init__(self, exc_type, match=None):
        self.exc_type = exc_type
        self.match = match
        self.value = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            raise AssertionError(f"Expected {self.exc_type} to be raised, but nothing was raised")
        if not issubclass(exc_type, self.exc_type):
            return False
        self.value = exc_val
        if self.match is not None and not re.search(self.match, str(exc_val)):
            raise AssertionError(f"Regex {self.match!r} did not match {str(exc_val)!r}")
        return True


class _MonkeyPatch:
    def __init__(self):
        self._undo = []

    @classmethod
    @contextlib.contextmanager
    def context(cls):
        mp = cls()
        try:
            yield mp
        finally:
            mp.undo()

    def setattr(self, target, name, value):
        sentinel = object()
        old = getattr(target, name, sentinel)
        setattr(target, name, value)
        self._undo.append((target, name, old, sentinel))

    def setitem(self, mapping, name, value):
        sentinel = object()
        old = mapping.get(name, sentinel)
        mapping[name] = value

        def undo():
            if old is sentinel:
                mapping.pop(name, None)
            else:
                mapping[name] = old

        self._undo.append(undo)

    def setenv(self, name, value):
        import os

        old = os.environ.get(name)
        os.environ[name] = str(value)

        def undo():
            if old is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = old

        self._undo.append(undo)

    def delenv(self, name, raising=True):
        import os

        if raising and name not in os.environ:
            raise KeyError(name)
        old = os.environ.pop(name, None)

        def undo():
            if old is not None:
                os.environ[name] = old

        self._undo.append(undo)

    def undo(self):
        for item in reversed(self._undo):
            if callable(item):
                item()
            else:
                target, name, old, sentinel = item
                if old is sentinel:
                    delattr(target, name)
                else:
                    setattr(target, name, old)


def _install_pytest_compat():
    if "pytest" in sys.modules:
        return sys.modules["pytest"]
    try:
        import pytest  # type: ignore
        return pytest
    except ImportError:
        pass

    mod = types.ModuleType("pytest")

    def fixture(scope="function"):
        def decorator(fn):
            fn._pytest_fixture = True
            fn._pytest_scope = scope
            return fn
        return decorator

    class _Mark:
        @staticmethod
        def parametrize(argnames, argvalues):
            names = [n.strip() for n in argnames.split(",")] if isinstance(argnames, str) else list(argnames)

            def decorator(fn):
                fn._pytest_params = (names, list(argvalues))
                return fn
            return decorator

        @staticmethod
        def skipif(condition, reason=""):
            def decorator(fn):
                fn._pytest_skipif = (bool(condition), reason)
                return fn
            return decorator

    def skip(reason=""):
        raise _SkipTest(reason)

    def raises(exc_type, match=None):
        return _PytestRaises(exc_type, match=match)

    class _Approx:
        def __init__(self, expected, rel=1e-6, abs=1e-12):
            self.expected = expected
            self.rel = rel
            self.abs = abs

        def __eq__(self, actual):
            tol = max(self.abs, self.rel * builtins_abs(self.expected))
            return builtins_abs(actual - self.expected) <= tol

    builtins_abs = abs
    mod.fixture = fixture
    mod.mark = _Mark()
    mod.skip = skip
    mod.raises = raises
    mod.approx = lambda val, rel=1e-6, abs=1e-12: _Approx(val, rel=rel, abs=abs)
    mod.MonkeyPatch = _MonkeyPatch
    sys.modules["pytest"] = mod
    return mod


def _resolve_fixture(name, fixtures_map, session_cache, module_cache, tmp_root, exit_stack, mpatch):
    if name == "tmp_path":
        d = Path(tempfile.mkdtemp(prefix="cuepoint-tmp-", dir=str(tmp_root)))
        return d
    if name == "monkeypatch":
        return mpatch
    if name not in fixtures_map:
        raise KeyError(f"Unknown fixture: {name}")
    fn = fixtures_map[name]
    scope = getattr(fn, "_pytest_scope", "function")
    if scope == "session" and name in session_cache:
        return session_cache[name]
    if scope == "module" and name in module_cache:
        return module_cache[name]
    deps = {
        param: _resolve_fixture(param, fixtures_map, session_cache, module_cache, tmp_root, exit_stack, mpatch)
        for param in inspect.signature(fn).parameters
    }
    if inspect.isgeneratorfunction(fn):
        cm = contextlib.contextmanager(fn)(**deps)
        val = exit_stack.enter_context(cm)
    else:
        val = fn(**deps)
    if scope == "session":
        session_cache[name] = val
    elif scope == "module":
        module_cache[name] = val
    return val


def run_all(module_names=None, failfast=False):
    _install_pytest_compat()
    modules = module_names or [
        "test_readonly",
        "test_live",
        "test_rekordbox_playback",
        "test_filter_groups",
        "test_combinatorial_stress",
        "test_backend_coverage",
    ]
    passed = 0
    skipped = 0
    failed = []
    session_cache = {}
    session_stack = contextlib.ExitStack()
    t0 = time.perf_counter()

    with tempfile.TemporaryDirectory(prefix="cuepoint-pytest-") as tmp_root, session_stack:
        all_fixtures = {}
        loaded = []
        for mod_name in modules:
            mod = importlib.import_module(mod_name)
            loaded.append((mod_name, mod))
            for attr_name in dir(mod):
                attr = getattr(mod, attr_name)
                if callable(attr) and getattr(attr, "_pytest_fixture", False):
                    all_fixtures[(mod_name, attr_name)] = attr

        for mod_name, mod in loaded:
            module_cache = {}
            mod_fixtures = {}
            for (m, fname), fn in all_fixtures.items():
                if m == mod_name or getattr(fn, "_pytest_scope", "function") == "session":
                    mod_fixtures[fname] = fn
            with contextlib.ExitStack() as module_stack:
                # unittest subclasses (e.g. test_live.py)
                suite = unittest.defaultTestLoader.loadTestsFromModule(mod)
                if suite.countTestCases() > 0:
                    runner = unittest.TextTestRunner(verbosity=0, failfast=failfast)
                    res = runner.run(suite)
                    passed += res.testsRun - len(res.failures) - len(res.errors) - len(res.skipped)
                    skipped += len(res.skipped)
                    for test_case, err in res.failures + res.errors:
                        failed.append((f"{mod_name}::{test_case.id()}", err))
                    if failfast and failed:
                        break

                # pytest-style test_* functions in source definition order
                test_funcs = [
                    (attr_name, getattr(mod, attr_name))
                    for attr_name in dir(mod)
                    if attr_name.startswith("test_") and callable(getattr(mod, attr_name))
                ]
                test_funcs.sort(key=lambda item: getattr(getattr(item[1], "__code__", None), "co_firstlineno", 0))
                for attr_name, fn in test_funcs:
                    skip_info = getattr(fn, "_pytest_skipif", None)
                    if skip_info and skip_info[0]:
                        skipped += 1
                        continue
                    params = getattr(fn, "_pytest_params", None)
                    param_sets = [dict(zip(params[0], v if isinstance(v, tuple) else (v,))) for v in params[1]] if params else [{}]
                    for pset in param_sets:
                        mpatch = _MonkeyPatch()
                        with contextlib.ExitStack() as func_stack:
                            try:
                                kwargs = {}
                                for pname in inspect.signature(fn).parameters:
                                    if pname in pset:
                                        kwargs[pname] = pset[pname]
                                    else:
                                        target_stack = session_stack if getattr(mod_fixtures.get(pname), "_pytest_scope", None) == "session" else module_stack
                                        kwargs[pname] = _resolve_fixture(
                                            pname, mod_fixtures, session_cache, module_cache, tmp_root, target_stack, mpatch
                                        )
                                fn(**kwargs)
                                passed += 1
                            except _SkipTest:
                                skipped += 1
                            except Exception as exc:  # noqa: BLE001
                                import traceback
                                label = f"{mod_name}::{attr_name}" + (f"[{pset}]" if pset else "")
                                failed.append((label, traceback.format_exc()))
                                if failfast:
                                    break
                            finally:
                                mpatch.undo()
                        if failfast and failed:
                            break
                    if failfast and failed:
                        break
            if failfast and failed:
                break

    elapsed = time.perf_counter() - t0
    print(f"Python tests: {passed} passed, {skipped} skipped, {len(failed)} failed in {elapsed:.2f}s")
    for label, tb in failed:
        print(f"\nFAIL {label}\n{tb}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raw_args = sys.argv[1:]
    failfast = False
    mod_args = []
    for a in raw_args:
        if a in ("-x", "--exitfirst", "--failfast"):
            failfast = True
        else:
            mod_args.append(Path(a).stem if (a.endswith(".py") or "/" in a or "\\" in a) else a)
    sys.exit(run_all(mod_args or None, failfast=failfast))

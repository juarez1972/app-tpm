#!/usr/bin/env python3
"""Simple config validator for this repository.

Scans for files: .json, .yml, .yaml, .hcl, .conf, .ini, Dockerfile, .ctx
Validates JSON (builtin json), YAML (pyyaml), HCL (python-hcl2), INI/CONF (configparser)
Basic Dockerfile heuristic: first non-empty non-comment line should start with FROM

Usage (Linux/Ubuntu / bash):

    # create and activate a venv (optional but recommended)
    python3 -m venv .venv; source .venv/bin/activate

    # install optional validators (optional, or use --install-deps below)
    python3 -m pip install --user pyyaml python-hcl2

    # run the validator (will use the current Python interpreter)
    python3 scripts/validate_configs.py [--install-deps]

If --install-deps is passed the script will attempt to pip install missing packages
(this uses the interpreter that runs the script).
"""

from __future__ import annotations
import os
import sys
import json
import argparse
import configparser
import traceback
from typing import List, Tuple

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

DEPS = {
    'yaml': 'pyyaml',
    'hcl2': 'python-hcl2'
}


def install_packages(pkgs: List[str]) -> bool:
    import subprocess
    try:
        cmd = [sys.executable, '-m', 'pip', 'install'] + pkgs
        print('Installing packages:', ' '.join(pkgs))
        subprocess.check_call(cmd)
        return True
    except Exception as e:
        print('Failed to install packages:', e)
        return False


def find_files(root: str) -> List[str]:
    exts = ('.yml', '.yaml', '.json', '.hcl', '.conf', '.ini', '.ctx')
    result = []
    for dirpath, dirnames, filenames in os.walk(root):
        # skip .git and __pycache__ and node_modules
        if any(part in ('.git', '__pycache__', 'node_modules') for part in dirpath.split(os.sep)):
            continue
        for fn in filenames:
            if fn == 'Dockerfile' or fn.endswith(exts):
                result.append(os.path.join(dirpath, fn))
    return sorted(result)


def check_json(path: str) -> Tuple[bool, str]:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            json.load(f)
        return True, 'valid JSON'
    except Exception as e:
        return False, f'JSON parse error: {e}'


def check_yaml(path: str, yaml_mod) -> Tuple[bool, str]:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            yaml_mod.safe_load(f)
        return True, 'valid YAML'
    except Exception as e:
        return False, f'YAML parse error: {e}'


def check_hcl(path: str, hcl2_mod) -> Tuple[bool, str]:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
            # python-hcl2 provides loads
            try:
                hcl2_mod.loads(content)
            except AttributeError:
                # some versions provide load on file object
                f2 = open(path, 'r', encoding='utf-8')
                hcl2_mod.load(f2)
        return True, 'valid HCL'
    except Exception as e:
        return False, f'HCL parse error: {e}'


def check_ini(path: str) -> Tuple[bool, str]:
    cp = configparser.ConfigParser()
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            cp.read_file(f)
        return True, 'valid INI/CONF'
    except Exception as e:
        return False, f'INI/CONF parse error: {e}'


def check_dockerfile(path: str) -> Tuple[bool, str]:
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                s = line.strip()
                if not s or s.startswith('#'):
                    continue
                if s.upper().startswith('FROM'):
                    return True, 'Dockerfile looks OK (has FROM)'
                else:
                    return False, 'Dockerfile first instruction is not FROM (heuristic)'
        return False, 'Dockerfile empty or only comments'
    except Exception as e:
        return False, f'Dockerfile read error: {e}'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--install-deps', action='store_true', help='Attempt to pip install pyyaml and python-hcl2')
    args = ap.parse_args()

    # attempt to import optional deps
    yaml_mod = None
    hcl2_mod = None
    missing = []
    try:
        import yaml as _yaml
    except Exception:
        _yaml = None
    try:
        import hcl2 as _hcl2
    except Exception:
        _hcl2 = None

    # Conditionally install if requested and missing
    to_install = []
    if _yaml is None:
        to_install.append(DEPS['yaml'])
    if _hcl2 is None:
        to_install.append(DEPS['hcl2'])

    if args.install_deps and to_install:
        ok = install_packages(to_install)
        if ok:
            # try imports again
            try:
                import importlib
                if _yaml is None:
                    _yaml = importlib.import_module('yaml')
                if _hcl2 is None:
                    _hcl2 = importlib.import_module('hcl2')
            except Exception:
                pass

    yaml_mod = _yaml
    hcl2_mod = _hcl2

    if yaml_mod is None:
        print('Note: PyYAML not available; YAML files will be skipped or only lightly checked. To install, run: pip install pyyaml')
    if hcl2_mod is None:
        print('Note: python-hcl2 not available; HCL files will be skipped. To install, run: pip install python-hcl2')

    files = find_files(ROOT)
    if not files:
        print('No configuration files found')
        return

    results = []
    for p in files:
        rel = os.path.relpath(p, ROOT)
        lower = rel.lower()
        try:
            if lower.endswith('.json'):
                ok, msg = check_json(p)
            elif lower.endswith('.yml') or lower.endswith('.yaml'):
                if yaml_mod:
                    ok, msg = check_yaml(p, yaml_mod)
                else:
                    ok, msg = (None, 'skipped (pyyaml missing)')
            elif lower.endswith('.hcl'):
                if hcl2_mod:
                    ok, msg = check_hcl(p, hcl2_mod)
                else:
                    ok, msg = (None, 'skipped (python-hcl2 missing)')
            elif lower.endswith('.conf') or lower.endswith('.ini'):
                ok, msg = check_ini(p)
            elif os.path.basename(rel) == 'Dockerfile':
                ok, msg = check_dockerfile(p)
            elif lower.endswith('.ctx'):
                ok, msg = (None, 'skipped (binary or unknown format)')
            else:
                ok, msg = (None, 'skipped (unknown extension)')
        except Exception as exc:
            ok = False
            msg = f'Exception while checking: {exc}\n{traceback.format_exc()}'
        results.append((rel, ok, msg))

    # print results
    print('\nValidation results:')
    good = 0
    bad = 0
    skipped = 0
    for rel, ok, msg in results:
        status = 'OK' if ok is True else ('SKIPPED' if ok is None else 'ERROR')
        print(f'- {rel}: {status} - {msg}')
        if ok is True:
            good += 1
        elif ok is None:
            skipped += 1
        else:
            bad += 1

    print('\nSummary:')
    print(f'  Valid:   {good}')
    print(f'  Errors:  {bad}')
    print(f'  Skipped: {skipped}')

    if bad > 0:
        sys.exit(2)

if __name__ == '__main__':
    main()

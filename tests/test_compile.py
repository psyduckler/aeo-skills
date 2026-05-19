"""Smoke tests for AEO Skills scripts.

Each skill is self-contained — its own `scripts/_shared.py` is a vendored copy of
the Gemini client helpers. This test verifies that every script compiles, accepts
--help without crashing, and that each `_shared.py` exposes the expected interface.
"""
import py_compile
import subprocess
import sys
import os
import glob
import importlib.util

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _all_scripts():
    """Every .py script across all skills (excludes _shared.py modules)."""
    paths = glob.glob(os.path.join(REPO_ROOT, '*/scripts/*.py'))
    paths += glob.glob(os.path.join(REPO_ROOT, 'scripts/*.py'))
    return [p for p in paths if os.path.basename(p) != '_shared.py']


def _all_shared_modules():
    """Every vendored _shared.py across all skills."""
    return glob.glob(os.path.join(REPO_ROOT, '*/scripts/_shared.py'))


def test_all_scripts_compile():
    """Every .py file in the repo should compile without errors."""
    all_py = glob.glob(os.path.join(REPO_ROOT, '*/scripts/*.py'))
    all_py += glob.glob(os.path.join(REPO_ROOT, 'scripts/*.py'))

    failures = []
    for script in all_py:
        try:
            py_compile.compile(script, doraise=True)
        except py_compile.PyCompileError as e:
            failures.append(f"{script}: {e}")

    assert not failures, "Compilation failures:\n" + "\n".join(failures)


def test_all_scripts_have_help():
    """Every entrypoint script should accept --help without crashing."""
    failures = []
    for script in _all_scripts():
        result = subprocess.run(
            [sys.executable, script, '--help'],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            failures.append(f"{script}: exit code {result.returncode}\n{result.stderr}")

    assert not failures, "--help failures:\n" + "\n".join(failures)


def test_every_skill_has_shared_module():
    """Every skill that calls Gemini must vendor its own _shared.py.

    This prevents the old bug where scripts depended on a sibling /shared/ folder
    that wasn't present when the skill was installed standalone via skills.sh.
    """
    expected_skills = [
        'aeo-ai-overview-simulator',
        'aeo-baseline',
        'aeo-cannibalization-detector',
        'aeo-citation-gap-finder',
        'aeo-competitor-monitor',
        'aeo-entity-extractor',
        'aeo-freshness-decay-tracker',
        'aeo-grounding-query-mapper',
        'aeo-multi-prompt-strategy',
        'aeo-prompt-frequency-analyzer',
    ]
    for skill in expected_skills:
        shared_path = os.path.join(REPO_ROOT, skill, 'scripts', '_shared.py')
        assert os.path.isfile(shared_path), f"Missing vendored _shared.py: {shared_path}"


def test_shared_modules_are_in_sync():
    """All vendored _shared.py files should be byte-identical.

    If you update one, run scripts/sync-shared.sh to update them all.
    """
    shared_files = _all_shared_modules()
    if not shared_files:
        return

    canonical = open(shared_files[0], 'rb').read()
    drift = []
    for path in shared_files[1:]:
        if open(path, 'rb').read() != canonical:
            drift.append(path)
    assert not drift, (
        "Vendored _shared.py files have drifted out of sync. "
        f"Canonical: {shared_files[0]}\nOut of sync:\n  " + "\n  ".join(drift) +
        "\nRun: scripts/sync-shared.sh"
    )


def test_shared_module_exposes_expected_interface():
    """Each _shared.py should export the helpers the scripts depend on."""
    expected_attrs = [
        'call_gemini', 'extract_queries', 'extract_sources', 'extract_response_text',
        'extract_domain', 'domain_matches', 'classify_intent', 'get_api_key',
        'DEFAULT_MODEL', 'DEFAULT_RUNS', 'DEFAULT_CONCURRENCY',
    ]
    for shared_path in _all_shared_modules():
        spec = importlib.util.spec_from_file_location("_shared_check", shared_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        for attr in expected_attrs:
            assert hasattr(mod, attr), f"{shared_path} missing {attr}"
        assert mod.DEFAULT_MODEL == 'gemini-3-flash-preview', (
            f"{shared_path} DEFAULT_MODEL is {mod.DEFAULT_MODEL}"
        )


def test_missing_api_key_handled():
    """Scripts should exit gracefully (no traceback) when GEMINI_API_KEY is missing."""
    env = os.environ.copy()
    env.pop('GEMINI_API_KEY', None)

    for script in _all_scripts():
        result = subprocess.run(
            [sys.executable, script, 'test prompt'],
            capture_output=True, text=True, timeout=10, env=env
        )
        # Should exit cleanly with stderr message — not crash with Python traceback
        if result.returncode != 0:
            assert 'Traceback' not in result.stderr, (
                f"{script} crashed with traceback when key was missing:\n{result.stderr}"
            )


if __name__ == '__main__':
    test_all_scripts_compile()
    print("✅ All scripts compile")
    test_all_scripts_have_help()
    print("✅ All scripts accept --help")
    test_every_skill_has_shared_module()
    print("✅ Every skill vendors its _shared.py")
    test_shared_modules_are_in_sync()
    print("✅ Vendored _shared.py copies are byte-identical")
    test_shared_module_exposes_expected_interface()
    print("✅ Each _shared.py exposes the expected interface")
    test_missing_api_key_handled()
    print("✅ Missing API key handled cleanly")
    print("\nAll smoke tests passed!")

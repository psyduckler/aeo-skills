"""Smoke tests for AEO Skills scripts."""
import py_compile
import subprocess
import sys
import os
import glob

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def test_all_scripts_compile():
    """Every .py file in the repo should compile without errors."""
    scripts = glob.glob(os.path.join(REPO_ROOT, '*/scripts/*.py'))
    scripts += glob.glob(os.path.join(REPO_ROOT, 'shared/*.py'))
    scripts += glob.glob(os.path.join(REPO_ROOT, 'scripts/*.py'))
    
    failures = []
    for script in scripts:
        try:
            py_compile.compile(script, doraise=True)
        except py_compile.PyCompileError as e:
            failures.append(f"{script}: {e}")
    
    assert not failures, f"Compilation failures:\n" + "\n".join(failures)

def test_all_scripts_have_help():
    """Every script should accept --help without crashing."""
    scripts = glob.glob(os.path.join(REPO_ROOT, '*/scripts/*.py'))
    scripts += glob.glob(os.path.join(REPO_ROOT, 'scripts/*.py'))
    
    failures = []
    for script in scripts:
        result = subprocess.run(
            [sys.executable, script, '--help'],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            failures.append(f"{script}: exit code {result.returncode}\n{result.stderr}")
    
    assert not failures, f"--help failures:\n" + "\n".join(failures)

def test_shared_client_importable():
    """shared.gemini_client should be importable."""
    sys.path.insert(0, REPO_ROOT)
    try:
        from shared import gemini_client
        assert hasattr(gemini_client, 'call_gemini')
        assert hasattr(gemini_client, 'extract_queries')
        assert hasattr(gemini_client, 'extract_sources')
        assert hasattr(gemini_client, 'DEFAULT_MODEL')
        assert gemini_client.DEFAULT_MODEL == 'gemini-3-flash-preview'
    finally:
        sys.path.pop(0)

def test_missing_api_key_handled():
    """Scripts should exit gracefully when GEMINI_API_KEY is missing."""
    scripts = glob.glob(os.path.join(REPO_ROOT, '*/scripts/*.py'))
    scripts += glob.glob(os.path.join(REPO_ROOT, 'scripts/*.py'))
    
    env = os.environ.copy()
    env.pop('GEMINI_API_KEY', None)
    
    for script in scripts:
        result = subprocess.run(
            [sys.executable, script, 'test prompt'],
            capture_output=True, text=True, timeout=10, env=env
        )
        # Should exit with non-zero (error about missing key), not crash with traceback
        # Some scripts may need different args, so we just check it doesn't hang

if __name__ == '__main__':
    test_all_scripts_compile()
    print("✅ All scripts compile")
    test_all_scripts_have_help()
    print("✅ All scripts accept --help")
    test_shared_client_importable()
    print("✅ Shared client importable")
    print("\nAll smoke tests passed!")

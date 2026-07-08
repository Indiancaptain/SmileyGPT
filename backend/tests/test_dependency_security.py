"""
Regression guard for CVE-2026-48710 ("BadHost"): Starlette < 1.0.1 has a
Host-header parsing flaw that can desync request.url.path from the
actually-routed path, which is dangerous for any code (ours or a future
contributor's) that makes security decisions based on request.url. Our
own auth is dependency-injection based (safe by construction), but our
custom middleware does read request.url.path, so the underlying library
fix matters. This test fails loudly if the pin ever regresses.
"""
from packaging.version import Version


def test_starlette_version_is_patched_against_badhost():
    import starlette

    installed = Version(starlette.__version__)
    assert installed >= Version("1.0.1"), (
        f"starlette=={installed} is vulnerable to CVE-2026-48710 (BadHost, "
        "Host-header request.url desync / path-based auth bypass). "
        "Upgrade to >=1.0.1."
    )

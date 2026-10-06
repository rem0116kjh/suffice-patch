"""Independent public-API behavioral checks; execute outside agent workspaces."""

import json
from pathlib import Path

import packaging
from packaging.specifiers import Specifier, SpecifierSet
from packaging.version import Version


checks = {}
failures = []


def check(name, actual, expected):
    passed = actual == expected
    checks[name] = passed
    if not passed:
        failures.append({"name": name, "actual": actual, "expected": expected})


check(
    "imports_checkout",
    Path(packaging.__file__).resolve().is_relative_to(Path.cwd().resolve() / "src"),
    True,
)

# Expected behavior uses ordinary numeric prefix padding and explicit epoch
# equality, independently of packaging's private splitting/padding helpers.
for epoch in (0, 2, 7):
    for release in ((1,), (1, 0), (3, 4)):
        for zero_count in (1, 3):
            prefix = release + (0,) * zero_count
            prefix_text = ".".join(map(str, prefix))
            version_text = ".".join(map(str, release))
            spec_version = f"{epoch}!{prefix_text}"
            candidate = f"{epoch}!{version_text}"
            for op, expected in (("==", True), ("!=", False)):
                spec = f"{op}{spec_version}.*"
                check(f"padding:{spec}:{candidate}", Specifier(spec).contains(candidate), expected)
                check(f"set:{spec}:{candidate}", SpecifierSet(spec).contains(candidate), expected)
                check(f"version-object:{spec}:{candidate}", Specifier(spec).contains(Version(candidate)), expected)
            for other_epoch in (0, 2, 7):
                if other_epoch == epoch:
                    continue
                other_candidate = f"{other_epoch}!{version_text}"
                for op, expected in (("==", False), ("!=", True)):
                    spec = f"{op}{spec_version}.*"
                    check(f"epoch:{spec}:{other_candidate}", Specifier(spec).contains(other_candidate), expected)

for spec, candidate, expected, prereleases in (
    ("==2!1.0.0.0.*", "2!1.0.0", True, None),
    ("==2!1.0.0.0.*", "2!1.0.0.1", False, None),
    ("==2!1.0.*", "2!1.0+local.4", True, None),
    ("==2!1.0.0.*", "2!1.0rc1", True, True),
    ("==2!1.0.0.*", "2!1.0rc1", False, False),
    ("==2!1.0.0.*", "2!1.0.post1", True, None),
    ("==0!1.0.0.*", "1", True, None),
    ("==1.0.0.*", "0!1", True, None),
    ("~=2!1.4", "2!1.9", True, None),
    ("~=2!1.4", "2!2.0", False, None),
    ("~=2!1.4", "3!1.4", False, None),
    ("~=2!1.4.5", "2!1.4.9", True, None),
    ("~=2!1.4.5", "2!1.5.0", False, None),
    ("~=1.4", "1.9", True, None),
    ("~=1.4", "2.0", False, None),
    ("~=2!1.4rc1", "2!1.4rc2", True, True),
    ("~=2!1.4rc1", "2!2.0rc1", False, True),
    ("==2!1.0", "2!1.0.0", True, None),
    (">=2!1.0", "1!99.0", False, None),
):
    check(
        f"regression:{spec}:{candidate}:{prereleases}",
        Specifier(spec).contains(candidate, prereleases=prereleases),
        expected,
    )

candidates = ["1.0", "2!1", "2!1.0.0", "2!1.0.1", "3!1.0"]
check(
    "filter:long-epoch-prefix",
    list(SpecifierSet("==2!1.0.0.0.*").filter(candidates)),
    ["2!1", "2!1.0.0"],
)
check(
    "filter:long-epoch-exclusion",
    list(SpecifierSet("!=2!1.0.0.0.*").filter(candidates)),
    ["1.0", "2!1.0.1", "3!1.0"],
)

result = {
    "passed": sum(checks.values()),
    "total": len(checks),
    "failed": len(failures),
    "checks": checks,
    "failures": failures,
    "imported_from": packaging.__file__,
}
print(json.dumps(result, sort_keys=True))
raise SystemExit(bool(failures))

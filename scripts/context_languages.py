"""Bounded, read-only language hints; never import or execute project code.

Python uses its syntax tree. Other languages use conservative textual hints, not
compiler resolution or a complete dependency/call graph. Callers still enforce
their own repository boundary and total context budget.
"""
import ast
import itertools
import json
import os
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

MAX_IMPORT_CANDIDATES = 24
MAX_AUX_BYTES = 65536
MAX_DIRECTORY_ENTRIES = 256
MAX_ANCESTORS = 12
MAX_IMPORT_SPECIFIERS = 96
MAX_SYMBOLS = 32
EXCLUDED_DIRS = frozenset({"node_modules", "vendor", ".git", ".venv", "venv", "__pycache__", "target"})

_LANGUAGE_SUFFIXES = {
    "python": {".py", ".pyi"}, "dart": {".dart"},
    "javascript": {".js", ".jsx", ".mjs", ".cjs"},
    "typescript": {".ts", ".tsx", ".mts", ".cts"},
    "vue": {".vue"}, "svelte": {".svelte"}, "go": {".go"}, "rust": {".rs"},
    "c": {".c", ".h"}, "cpp": {".cpp", ".cc", ".cxx", ".hpp", ".hh", ".hxx", ".m", ".mm"},
    "java": {".java"}, "kotlin": {".kt", ".kts"}, "csharp": {".cs"}, "swift": {".swift"},
    "ruby": {".rb", ".rake"}, "php": {".php"}, "shell": {".sh", ".bash", ".zsh", ".fish"},
    "html": {".html", ".htm"}, "css": {".css", ".scss", ".sass", ".less"}, "sql": {".sql"},
    "config": {".json", ".jsonc", ".toml", ".yaml", ".yml", ".ini", ".cfg", ".conf", ".xml", ".props", ".csproj"},
    "docs": {".md", ".mdx", ".rst", ".txt", ".adoc"},
}
CODE_SUFFIXES = frozenset(s for lang, suffixes in _LANGUAGE_SUFFIXES.items()
                          if lang not in {"config", "docs"} for s in suffixes)
TEXT_SUFFIXES = frozenset(_LANGUAGE_SUFFIXES["config"] | _LANGUAGE_SUFFIXES["docs"])
SUPPORTED_SUFFIXES = CODE_SUFFIXES | TEXT_SUFFIXES
_SUFFIX_LANGUAGE = {suffix: lang for lang, suffixes in _LANGUAGE_SUFFIXES.items() for suffix in suffixes}
_MANIFESTS = {
    "python": ("pyproject.toml", "setup.cfg", "setup.py", "tox.ini", "requirements.txt"),
    "javascript": ("package.json", "jsconfig.json", "tsconfig.json"),
    "typescript": ("package.json", "tsconfig.json", "jsconfig.json"),
    "vue": ("package.json", "tsconfig.json"), "svelte": ("package.json", "tsconfig.json", "svelte.config.js"),
    "go": ("go.mod", "go.work"), "rust": ("Cargo.toml",),
    "dart": ("pubspec.yaml",),
    "c": ("CMakeLists.txt", "Makefile", "meson.build"),
    "cpp": ("CMakeLists.txt", "Makefile", "meson.build"),
    "java": ("pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle"),
    "kotlin": ("build.gradle.kts", "build.gradle", "settings.gradle.kts", "pom.xml"),
    "csharp": ("Directory.Build.props", "global.json"), "swift": ("Package.swift",),
    "ruby": ("Gemfile",), "php": ("composer.json",), "shell": ("Makefile",),
}
MANIFEST_FILENAMES = frozenset(name for names in _MANIFESTS.values() for name in names)


def language_for(path: Path) -> str:
    """Return a stable language label, including textual fallback categories."""
    if path.name in {"Dockerfile", "Makefile", "Gemfile"}:
        return "text"
    if path.suffix == ".C":
        return "cpp"
    return _SUFFIX_LANGUAGE.get(path.suffix.lower(), "text")


def _inside(path, root):
    try:
        try:
            lexical = path.relative_to(root)
        except ValueError:
            lexical = None
        if lexical and any(part in EXCLUDED_DIRS for part in lexical.parts):
            return None
        resolved = path.resolve()
        relative = resolved.relative_to(root)
        if any(part in EXCLUDED_DIRS for part in relative.parts):
            return None
        return resolved
    except (OSError, RuntimeError, ValueError):
        return None


def _parents(path, root):
    directory = path.parent
    for _ in range(MAX_ANCESTORS):
        if _inside(directory, root) is None:
            break
        yield directory
        if directory == root:
            break
        directory = directory.parent


def discover_manifests(path: Path, root: Path) -> list[Path]:
    """Return nearby existing manifests without reading or evaluating them."""
    root = root.resolve()
    path = _inside(path if path.is_absolute() else root / path, root)
    if path is None:
        return []
    names = _MANIFESTS.get(language_for(path), tuple(sorted(MANIFEST_FILENAMES)))
    found = []
    for directory in _parents(path, root):
        for name in names:
            candidate = _inside(directory / name, root)
            if candidate and candidate != path and candidate.is_file() and candidate not in found:
                found.append(candidate)
                if len(found) >= MAX_IMPORT_CANDIDATES:
                    return found
    return found


class AnalysisCache:
    """Reuse filesystem facts within one collection only; never persist across runs."""
    def __init__(self, root):
        self.root = root.resolve()
        self.paths, self.reads, self.directories = {}, {}, {}
        self.dart_packages = {}


class _Scan:
    def __init__(self, path, root, cache=None):
        self.path, self.root = path, root
        self.cache = cache if cache is not None else AnalysisCache(root)
        if self.cache.root != root:
            raise ValueError('Analysis cache belongs to a different repository root')
        self.imports, self.notes = [], []
        self.remaining = MAX_AUX_BYTES
        self.read_cache = {}
        self.path_cache = self.cache.paths
        self.unresolved = 0

    def note(self, text):
        if text not in self.notes and len(self.notes) < 7:
            self.notes.append(text)

    def existing(self, path):
        if path not in self.path_cache:
            safe = _inside(path, self.root)
            self.path_cache[path] = safe if safe and safe.is_file() else None
        return self.path_cache[path]

    def add(self, path):
        path = self.existing(path)
        if path is None:
            return False
        if path != self.path and path not in self.imports:
            if len(self.imports) >= MAX_IMPORT_CANDIDATES:
                self.note("Local import candidate limit reached; additional dependencies may exist.")
            else:
                self.imports.append(path)
        return True

    def read(self, path):
        path = self.existing(path)
        if path is None:
            return ""
        if path in self.read_cache:
            return self.read_cache[path]
        cached = self.cache.reads.get(path)
        if cached is not None and cached[1] <= self.remaining:
            self.remaining -= cached[1]
            self.read_cache[path] = cached[0]
            return cached[0]
        if self.remaining <= 0:
            self.note("Auxiliary manifest byte limit reached; resolution is incomplete.")
            return ""
        try:
            with path.open("rb") as stream:
                oversized = os.fstat(stream.fileno()).st_size > self.remaining
                data = b"" if oversized else stream.read(self.remaining)
            if oversized:
                self.remaining = 0
                self.note("Oversized auxiliary manifest omitted; resolution is incomplete.")
                text = ""
            else:
                self.remaining -= len(data)
                text = data.decode("utf-8")
                self.cache.reads[path] = (text, len(data))
        except (OSError, UnicodeError):
            self.note("Auxiliary manifest could not be read as UTF-8.")
            text = ""
        self.read_cache[path] = text
        return text

    def files(self, directory):
        directory = _inside(directory, self.root)
        if directory is None:
            return []
        try:
            if directory not in self.cache.directories:
                with os.scandir(directory) as entries:
                    names = list(itertools.islice(entries, MAX_DIRECTORY_ENTRIES + 1))
                self.cache.directories[directory] = (
                    [Path(item.path) for item in sorted(names[:MAX_DIRECTORY_ENTRIES], key=lambda e: e.name)],
                    len(names) > MAX_DIRECTORY_ENTRIES)
            paths, truncated = self.cache.directories[directory]
            if truncated:
                self.note("Package directory entry limit reached; file selection is incomplete.")
            return paths
        except OSError:
            return []

    def missing(self):
        self.unresolved += 1

    def finish(self, symbols):
        if len(symbols) > MAX_SYMBOLS:
            self.note("Symbol hint limit reached; additional definitions may exist.")
        if self.unresolved:
            self.notes.append(f"{self.unresolved} import reference(s) external or unresolved; aliases and compiler paths are not inferred.")
        return set(sorted(symbols)[:MAX_SYMBOLS]), self.imports, self.notes


def _python(scan, source):
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, RecursionError):
        scan.note("Python AST unavailable; syntax may require another Python version.")
        return set()
    symbols = {node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
    if scan.path.suffix == ".pyi":
        scan.note("Python stub symbols only; stub imports are not traversed.")
        return symbols
    roots = list(dict.fromkeys([scan.root, scan.root / "src", *list(_parents(scan.path, scan.root))]))

    def module_at(base, module):
        candidate = base.joinpath(*module.split(".")) if module else base
        candidates = [candidate / "__init__.py"]
        if module:
            candidates.append(candidate.with_suffix(".py"))
        return any([scan.add(path) for path in candidates])

    count = 0
    for index, node in enumerate(ast.walk(tree)):
        if index >= 8000:
            scan.note("Python AST node limit reached; imports may be incomplete.")
            break
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        count += 1
        if count > MAX_IMPORT_SPECIFIERS:
            scan.note("Import reference limit reached; additional imports were not resolved.")
            break
        if isinstance(node, ast.Import):
            for alias in node.names[:MAX_IMPORT_SPECIFIERS]:
                if not any(module_at(base, alias.name) for base in roots):
                    scan.missing()
        else:
            bases = roots
            if node.level:
                base = scan.path.parent
                for _ in range(min(node.level - 1, MAX_ANCESTORS)):
                    base = base.parent
                bases = [base] if node.level <= MAX_ANCESTORS else []
            found = False
            for base in bases:
                here = module_at(base, node.module or "")
                for alias in node.names[:MAX_IMPORT_SPECIFIERS]:
                    if alias.name != "*":
                        here = module_at(base, ".".join(filter(None, [node.module, alias.name]))) or here
                if here:
                    found = True
                    break
            if not found:
                scan.missing()
    return symbols


def _without_comments(source):
    # Retain strings, including URL slashes. Walk once so unfinished comments or
    # strings cannot make a regexp retry the rest of the file at every opener.
    pieces, index, length = [], 0, len(source)
    while index < length:
        start = index
        char = source[index]
        if char in "\"'`":
            index += 1
            while index < length:
                if source[index] == "\\":
                    index = min(length, index + 2)
                elif source[index] == char:
                    index += 1
                    break
                else:
                    index += 1
            pieces.append(source[start:index])
        elif source.startswith("//", index):
            end = source.find("\n", index + 2)
            index = length if end < 0 else end
            pieces.append(" ")
        elif source.startswith("/*", index):
            end = source.find("*/", index + 2)
            index = length if end < 0 else end + 2
            pieces.append(" " + "\n" * source.count("\n", start, index))
        else:
            pieces.append(char)
            index += 1
    return "".join(pieces)


def _text_symbols(source):
    patterns = [
        r"\b(?:class|interface|enum|struct|trait|record|type|fn|function|def|fun|func|module|mod|namespace)\s+([A-Za-z_$][\w$]*)",
        r"(?m)^[ \t]*(?:export[ \t]+)?(?:const|let|var|static)[ \t]+([A-Za-z_$][\w$]*)",
        r"\bfunc\s+\([^\n)]{1,200}\)\s*([A-Za-z_]\w*)\s*\(",
        r"(?m)^[ \t]*([A-Za-z_][\w.-]*)[ \t]*[:=]",
        r'''\bid\s*=\s*["']([A-Za-z_][\w-]*)["']''',
    ]
    symbols = set()
    for pattern in patterns:
        for match in itertools.islice(re.finditer(pattern, source), MAX_SYMBOLS):
            symbols.add(match.group(1))
    return symbols


def _javascript(scan, source):
    source = _without_comments(source)
    pattern = r'''\b(?:import|export)\s+(?:[^;'"`]{0,1000}?\bfrom\s*)?["']([^"'\n]+)["']|\b(?:require|import)\s*\(\s*["']([^"'\n]+)["']\s*\)'''
    suffixes = (".ts", ".tsx", ".js", ".jsx", ".mts", ".cts", ".mjs", ".cjs", ".vue", ".svelte", ".json")

    def resolve(base):
        candidates = []
        if base.suffix in {".js", ".jsx", ".mjs", ".cjs"}:
            replacements = {".js": (".ts", ".tsx"), ".jsx": (".tsx", ".ts"), ".mjs": (".mts",), ".cjs": (".cts",)}
            candidates.extend(base.with_suffix(s) for s in replacements[base.suffix])
        candidates.append(base)
        if not base.suffix:
            candidates.extend(Path(str(base) + s) for s in suffixes)
        candidates.extend(base / ("index" + s) for s in suffixes)
        for candidate in candidates:
            if scan.add(candidate):
                return True
        raw = scan.read(base / "package.json")
        if raw:
            try:
                package = json.loads(raw)
                if isinstance(package, dict):
                    for field in ("types", "module", "main"):
                        value = package.get(field)
                        if isinstance(value, str) and scan.add(base / value):
                            return True
            except ValueError:
                scan.note("Local package.json is not valid JSON; package entry points were not resolved.")
        return False

    for index, match in enumerate(re.finditer(pattern, source)):
        if index >= MAX_IMPORT_SPECIFIERS:
            scan.note("Import reference limit reached; additional imports were not resolved.")
            break
        specifier = (match.group(1) or match.group(2)).split("?", 1)[0].split("#", 1)[0]
        if not specifier.startswith(("./", "../")) or not resolve(scan.path.parent / specifier):
            scan.missing()
    scan.note("JS/TS imports are textual hints; package exports, aliases, templates and runtime loading may need inspection.")
    return _text_symbols(source)


_DART_TOKEN = re.compile(r"""//[^\n]*|/\*|r?(?:'{3}|"{3}|'|")|[A-Za-z_$][\w$]*|[^\s]""")
_DART_COMMENT = re.compile(r"/\*|\*/")


def _dart_directives(source):
    """Yield URI literals in import, export and part directives, including conditional branches."""
    pos = 0
    directive = expect_uri = False
    while match := _DART_TOKEN.search(source, pos):
        token, pos = match[0], match.end()
        if token.startswith("//"):
            continue
        if token == "/*":
            depth = 1
            for marker in _DART_COMMENT.finditer(source, pos):
                depth += 1 if marker[0] == "/*" else -1
                if depth == 0:
                    pos = marker.end()
                    break
            else:
                return
            continue
        if token.endswith(("'", '"')):
            delimiter = token.removeprefix("r")
            start = pos
            while pos < len(source) and not source.startswith(delimiter, pos):
                pos += 2 if source[pos] == "\\" and token == delimiter else 1
            if pos >= len(source):
                return
            if expect_uri:
                yield source[start:pos]
            pos += len(delimiter)
            expect_uri = False
        elif token in {"import", "export", "part"}:
            directive = expect_uri = True
        elif token == ";":
            directive = expect_uri = False
        elif token != "of":
            expect_uri = directive and token == ")"


def _dart_uri_path(uri, allow_file=False):
    if not isinstance(uri, str):
        return None
    try:
        parsed = urlsplit(uri)
    except ValueError:
        return None
    if parsed.netloc or parsed.query or parsed.fragment or (parsed.scheme and not (allow_file and parsed.scheme == "file")):
        return None
    path = unquote(parsed.path)
    if "\x00" in path or "\\" in path or (not allow_file and Path(path).is_absolute()):
        return None
    return Path(path)


def _dart_package_map(scan, config):
    if config not in scan.cache.dart_packages:
        entries = {}
        try:
            data = json.loads(scan.read(config))
            if not isinstance(data, dict) or data.get("configVersion") != 2 or not isinstance(data.get("packages"), list):
                raise ValueError
            for entry in data["packages"]:
                if isinstance(entry, dict) and isinstance(entry.get("name"), str):
                    entries[entry["name"]] = entry
        except (ValueError, RecursionError):
            scan.note("Dart package configuration unavailable or unsupported. Cross-package imports may be missing.")
            return {}
        scan.cache.dart_packages[config] = entries
    return scan.cache.dart_packages[config]


def _dart(scan, source):
    parents = list(_parents(scan.path, scan.root))
    manifest = next((d / "pubspec.yaml" for d in parents if scan.existing(d / "pubspec.yaml")), None)
    config = next((p for d in parents if scan.existing(p := d / ".dart_tool/package_config.json")), None)
    own_name = re.search(r"""(?m)^name:[ \t]*['"]?([a-z_][a-z0-9_]*)['"]?[ \t]*(?:#[^\r\n]*)?\r?$""",
                         scan.read(manifest).lstrip("\ufeff")) if manifest else None

    def package_library(name):
        entry = _dart_package_map(scan, config).get(name) if config else None
        if entry is None:
            return _inside(manifest.parent / "lib", scan.root) if own_name and own_name[1] == name else None
        root_path = _dart_uri_path(entry.get("rootUri"), allow_file=True)
        lib_path = _dart_uri_path(entry.get("packageUri", ""))
        if root_path is None or lib_path is None:
            return None
        package = _inside(config.parent / root_path, scan.root)
        return _inside(package / lib_path, package) if package else None

    for index, uri in enumerate(_dart_directives(source)):
        if index >= MAX_IMPORT_SPECIFIERS:
            scan.note("Dart directive limit reached. Additional imports may be missing.")
            break
        if uri.startswith("dart:"):
            continue
        if uri.startswith("package:"):
            name, sep, tail = uri[8:].partition("/")
            base = package_library(name) if sep else None
            path = _dart_uri_path(tail)
            candidate = _inside(base / path, base) if base and path is not None else None
        else:
            path = _dart_uri_path(uri)
            candidate = _inside(scan.path.parent / path, scan.root) if path is not None else None
        if (candidate is None or candidate.suffix != ".dart"
                or {".dart_tool", ".pub-cache", "build"}.intersection(candidate.relative_to(scan.root).parts)
                or not scan.add(candidate)):
            scan.missing()
    code = _without_comments(source)
    symbols = _text_symbols(code)
    symbols.update(m[1] for m in itertools.islice(re.finditer(
        r"(?m)^(?:external[ \t]+)?[A-Za-z_][\w.<>?,]*[ \t]+([A-Za-z_$][\w$]*)[ \t]*\(", code), MAX_SYMBOLS))
    symbols.discard("main")
    return symbols


def dart_test_candidates(path, package, root):
    """Find existing mirrored tests for a library, including the common lib/src layout."""
    lib = package / "lib"
    if not path.is_relative_to(lib):
        return
    relative = path.relative_to(lib).with_name(path.stem + "_test.dart")
    names = [relative]
    if relative.parts[0] == "src":
        names.append(relative.relative_to("src"))
    for directory in ("test", "integration_test"):
        for name in names:
            candidate = _inside(package / directory / name, root)
            if candidate and candidate.is_relative_to(package / directory) and candidate.is_file():
                yield candidate


def _go(scan, source):
    source = _without_comments(source)
    # Go files in one package share declarations without explicit imports.
    def package_files(directory):
        matched = False
        for path in scan.files(directory):
            if path.suffix == ".go" and not path.name.endswith("_test.go"):
                matched = scan.add(path) or matched
        return matched

    package_files(scan.path.parent)
    mod = next((directory / "go.mod" for directory in _parents(scan.path, scan.root)
                if scan.existing(directory / "go.mod")), None)
    match = re.search(r'(?m)^[ \t]*module[ \t]+["`]?([^\s"`]+)', scan.read(mod)) if mod else None
    module = match.group(1) if match else None
    # Consume an unfinished block once, rather than retrying at every later
    # import keyword while searching an absent closing parenthesis.
    blocks = re.finditer(r'\bimport\s*(?:\(([^)]*)(?:\)|\Z)|((?:[\w.]+\s+)?["`][^"`]+["`]))', source)
    count = 0
    for block in blocks:
        if block.group(1) is not None and not block.group().endswith(")"):
            scan.note("Unclosed Go import block; only partial textual references are available.")
        body = block.group(1) if block.group(1) is not None else block.group(2)
        for found in re.finditer(r'["`]([^"`]+)["`]', body):
            count += 1
            if count > MAX_IMPORT_SPECIFIERS:
                scan.note("Import reference limit reached; additional imports were not resolved.")
                return _text_symbols(source)
            name = found.group(1)
            if module and (name == module or name.startswith(module + "/")):
                directory = mod.parent / name[len(module):].lstrip("/")
                if not package_files(directory):
                    scan.missing()
            else:
                scan.missing()
    scan.note("Go package hints exclude tests; build tags, replace directives and workspace dependencies are not evaluated.")
    return _text_symbols(source)


def _rust(scan, source):
    source = _without_comments(source)
    cargo = next((directory for directory in _parents(scan.path, scan.root)
                  if scan.existing(directory / "Cargo.toml")), None)
    crate = cargo / "src" if cargo else (scan.root / "src" if _inside(scan.root / "src", scan.root) and (scan.root / "src").is_dir() else scan.root)
    current = scan.path.parent if scan.path.name in {"lib.rs", "main.rs", "mod.rs"} else scan.path.parent / scan.path.stem

    def chain(base, parts):
        found = False
        for part in parts[:MAX_ANCESTORS]:
            base = base / part
            found = scan.add(base.with_suffix(".rs")) or found
            found = scan.add(base / "mod.rs") or found
        return found

    for match in itertools.islice(re.finditer(r"\bmod\s+([A-Za-z_]\w*)\s*;", source), MAX_IMPORT_SPECIFIERS):
        if not chain(current, [match.group(1)]):
            scan.missing()
    for match in itertools.islice(re.finditer(r"\buse\s+((?:[A-Za-z_]\w*::)*[A-Za-z_]\w*)(?:::\s*[{*])?", source), MAX_IMPORT_SPECIFIERS):
        parts = match.group(1).split("::")
        first = parts.pop(0)
        if first == "crate":
            base = crate
        elif first == "self":
            base = current
        elif first == "super":
            base = current.parent
            while parts and parts[0] == "super":
                base = base.parent
                parts.pop(0)
        else:
            scan.missing()
            continue
        if not parts or not chain(base, parts):
            scan.missing()
    scan.note("Rust module hints are textual; inline modules, cfg/path attributes, macros and Cargo target overrides are not resolved.")
    return _text_symbols(source)


def _c(scan, source):
    source = _without_comments(source)
    include_roots = list(dict.fromkeys([scan.path.parent,
                         *(directory / "include" for directory in _parents(scan.path, scan.root)), scan.root]))
    for match in itertools.islice(re.finditer(r'(?m)^[ \t]*#[ \t]*include[ \t]*"([^"\n]+)"', source), MAX_IMPORT_SPECIFIERS):
        name = match.group(1)
        if not any(scan.add(base / name) for base in include_roots):
            scan.missing()
    scan.note("C/C++ quoted includes and function parameter spans up to 2048 characters only; compiler paths, conditionals and macros are not evaluated.")
    symbols = _text_symbols(source)
    symbols.update(match.group(1) for match in itertools.islice(re.finditer(
        r"(?m)^[ \t]*(?:[\w:*&<>]+[ \t]+)+([A-Za-z_]\w*)[ \t]*\([^;{}]{0,2048}\)[ \t]*(?:const[ \t]*)?\{", source), MAX_SYMBOLS))
    return symbols


def analyze(path: Path, source: str, root: Path, cache=None) -> tuple[set[str], list[Path], list[str]]:
    """Return definition hints, existing local dependencies, and honest limits."""
    root = root.resolve()
    path = _inside(path if path.is_absolute() else root / path, root)
    if path is None:
        return set(), [], ["Analysis path is outside the repository or in an excluded dependency directory."]
    scan = _Scan(path, root, cache)
    language = language_for(path)
    if language == "python":
        symbols = _python(scan, source)
    elif language == "dart":
        symbols = _dart(scan, source)
    elif language in {"javascript", "typescript", "vue", "svelte"}:
        if language in {"vue", "svelte"}:
            source = "\n".join(m.group(1) for m in re.finditer(r"<script\b[^>]*>([\s\S]*?)</script\s*>", source, re.I))
            scan.note("Component analysis covers inline script blocks only; template/style dependencies are not resolved.")
        symbols = _javascript(scan, source)
    elif language == "go":
        symbols = _go(scan, source)
    elif language == "rust":
        symbols = _rust(scan, source)
    elif language in {"c", "cpp"}:
        symbols = _c(scan, source)
    else:
        symbols = _text_symbols(source)
        scan.note(f"{language} uses textual symbol/reference hints only; imports and call graphs are not resolved.")
    return scan.finish(symbols)

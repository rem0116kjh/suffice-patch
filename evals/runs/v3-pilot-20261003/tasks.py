"""Small, synthetic tasks; graders stay outside agent workspaces. Stdlib only."""

TASKS = {
    "reuse": {
        "prompt": "Fix api.customer_label so customer names display like the web view, including whitespace and empty-name handling. Preserve the response shape.",
        "files": {
            "labels.py": 'def display_name(name):\n    return " ".join(name.split()) or "Anonymous"\n',
            "web.py": 'from labels import display_name\n\ndef customer_heading(name):\n    return display_name(name)\n',
            "api.py": 'def customer_label(name):\n    return {"label": name}\n',
            "test_sample.py": 'import unittest\nfrom api import customer_label\n\nclass Sample(unittest.TestCase):\n    def test_shape(self):\n        self.assertEqual(customer_label("Lee"), {"label": "Lee"})\n',
        },
        "checks": [
            'from api import customer_label\nassert customer_label("  Ada\\tLovelace ") == {"label": "Ada Lovelace"}',
            'from api import customer_label\nassert customer_label(" \\n ") == {"label": "Anonymous"}',
            'from api import customer_label\nassert customer_label("김 진형") == {"label": "김 진형"}',
        ],
        "good": {"api.py": 'from labels import display_name\n\ndef customer_label(name):\n    return {"label": display_name(name)}\n'},
    },
    "native": {
        "prompt": "Use the browser's native date picker for the due-date field in form.html. Preserve its accessible label, required constraint, minimum date, and form submission name.",
        "files": {"form.html": '<!doctype html>\n<html lang="en"><title>Due date</title>\n<form method="get">\n<label for="due">Due date</label>\n<input id="due" name="due_date" type="text" required min="2026-01-01">\n<button>Save</button>\n</form></html>\n'},
        "checks": [
            'from html.parser import HTMLParser\nfrom pathlib import Path\nclass Parser(HTMLParser):\n    def handle_starttag(self, tag, attrs):\n        self.tags.append((tag, dict(attrs)))\np=Parser(); p.tags=[]; p.feed(Path("form.html").read_text())\ni=[a for t,a in p.tags if t=="input" and a.get("name")=="due_date"][0]\nassert i["type"]=="date"',
            'from html.parser import HTMLParser\nfrom pathlib import Path\nclass Parser(HTMLParser):\n    def handle_starttag(self, tag, attrs):\n        self.tags.append((tag, dict(attrs)))\np=Parser();p.tags=[];p.feed(Path("form.html").read_text())\ni=[a for t,a in p.tags if t=="input" and a.get("name")=="due_date"][0]\nassert "required" in i and i["min"]=="2026-01-01"\nassert any(t=="label" and a.get("for")==i["id"] for t,a in p.tags)',
        ],
        "good": {"form.html": '<!doctype html>\n<html lang="en"><title>Due date</title>\n<form method="get">\n<label for="due">Due date</label>\n<input id="due" name="due_date" type="date" required min="2026-01-01">\n<button>Save</button>\n</form></html>\n'},
    },
    "shared": {
        "prompt": "The API fails for malformed page-size query values and accepts zero/negative sizes. Fix normalization: integer values 1..100 remain unchanged, larger integers cap at 100, invalid or nonpositive inputs (including None and empty text) default to 20. Web and export callers must follow the same contract.",
        "files": {
            "paging.py": 'def page_size(raw):\n    return min(int(raw), 100)\n',
            "api.py": 'from paging import page_size\n\ndef limit(query):\n    return page_size(query.get("limit"))\n',
            "web.py": 'from paging import page_size\n\ndef limit(value):\n    return page_size(value)\n',
            "export.py": 'from paging import page_size\n\ndef limit(value):\n    return page_size(value)\n',
            "test_sample.py": 'import unittest\nfrom paging import page_size\n\nclass Sample(unittest.TestCase):\n    def test_valid(self):\n        self.assertEqual(page_size("5"), 5)\n',
        },
        "checks": [
            'from paging import page_size\nassert [page_size(x) for x in ["1", "100", "300", 5]] == [1,100,100,5]',
            'from paging import page_size\nassert all(page_size(x)==20 for x in [None,"", "bad", "0", "-7", 0, -1])',
            'import api, web, export\nfor x in [None,"0","-4","bad","200","3"]:\n    expected=100 if x=="200" else 3 if x=="3" else 20\n    assert api.limit({"limit":x})==web.limit(x)==export.limit(x)==expected',
        ],
        "good": {"paging.py": 'def page_size(raw):\n    try:\n        value = int(raw)\n    except (ValueError, TypeError):\n        return 20\n    return min(value, 100) if value > 0 else 20\n'},
    },
    "auth": {
        "prompt": "Implement update_note(user_id, note_id, text) in notes.py. Apply the same access rules and missing-note behavior as read_note. Return the updated note. Rejected requests must not modify stored notes.",
        "files": {
            "notes.py": 'NOTES = {1: {"owner": 7, "text": "first"}, 2: {"owner": 8, "text": "private"}}\n\ndef read_note(user_id, note_id):\n    if user_id is None:\n        raise PermissionError("sign in")\n    note = NOTES[note_id]\n    if note["owner"] != user_id:\n        raise PermissionError("not your note")\n    return dict(note)\n\ndef update_note(user_id, note_id, text):\n    raise NotImplementedError\n',
        },
        "checks": [
            'from notes import update_note, NOTES\nr=update_note(7,1,"new"); assert r=={"owner":7,"text":"new"}; assert NOTES[1]==r',
            'from notes import update_note, NOTES\nfrom copy import deepcopy\nold=deepcopy(NOTES)\nfor who in [None,8]:\n    try: update_note(who,1,"stolen")\n    except PermissionError: pass\n    else: raise AssertionError("unauthorized update accepted")\nassert NOTES==old',
            'from notes import update_note, NOTES\nfrom copy import deepcopy\nold=deepcopy(NOTES)\ntry: update_note(7,999,"new")\nexcept KeyError: pass\nelse: raise AssertionError("missing ID must fail")\nassert NOTES==old',
        ],
        "good": {"notes.py": 'NOTES = {1: {"owner": 7, "text": "first"}, 2: {"owner": 8, "text": "private"}}\n\ndef read_note(user_id, note_id):\n    if user_id is None:\n        raise PermissionError("sign in")\n    note = NOTES[note_id]\n    if note["owner"] != user_id:\n        raise PermissionError("not your note")\n    return dict(note)\n\ndef update_note(user_id, note_id, text):\n    read_note(user_id, note_id)\n    NOTES[note_id]["text"] = text\n    return read_note(user_id, note_id)\n'},
    },
    "atomic": {
        "prompt": "Fix settings.save_settings(path, data): a serialization or replacement failure must leave the old file intact. Save valid UTF-8 JSON to new or existing files, propagate failures, and clean up temporary files. The parent directory already exists. Keep the API.",
        "files": {"settings.py": 'import json\n\ndef save_settings(path, data):\n    with open(path, "w", encoding="utf-8") as f:\n        json.dump(data, f, ensure_ascii=False)\n'},
        "checks": [
            'from settings import save_settings\nfrom pathlib import Path\nimport tempfile,json\nwith tempfile.TemporaryDirectory() as d:\n    p=Path(d)/"a.json"\n    for value in [{"한글":"값"},{"next":42}]:\n        save_settings(p,value);assert json.loads(p.read_text(encoding="utf-8"))==value\n    assert len(list(Path(d).iterdir()))==1',
            'from settings import save_settings\nfrom pathlib import Path\nimport tempfile\nwith tempfile.TemporaryDirectory() as d:\n    p=Path(d)/"a.json";p.write_text("old")\n    try: save_settings(p,{"bad":object()})\n    except (TypeError, ValueError): pass\n    else: raise AssertionError("serialization error swallowed")\n    assert p.read_text()=="old";assert len(list(Path(d).iterdir()))==1',
            'from settings import save_settings\nfrom pathlib import Path\nfrom unittest.mock import patch\nimport tempfile,settings,os\nwith tempfile.TemporaryDirectory() as d:\n    p=Path(d)/"a.json";p.write_text("old")\n    with patch.object(os,"replace",side_effect=OSError("disk failure")), patch.object(Path,"replace",side_effect=OSError("disk failure")), patch.object(os,"rename",side_effect=OSError("disk failure")):\n        # Also cover a function imported directly before monkeypatching.\n        from contextlib import ExitStack\n        with ExitStack() as stack:\n            for name in ["replace","rename"]:\n                if hasattr(settings,name): stack.enter_context(patch.object(settings,name,side_effect=OSError("disk failure")))\n            try: save_settings(p,{"new":1})\n            except OSError: pass\n            else: raise AssertionError("replacement failure not propagated")\n    assert p.read_text()=="old";assert len(list(Path(d).iterdir()))==1',
        ],
        "good": {"settings.py": 'import json\nimport os\nimport tempfile\nfrom pathlib import Path\n\ndef save_settings(path, data):\n    path = Path(path)\n    payload = json.dumps(data, ensure_ascii=False)\n    tmp = None\n    try:\n        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as f:\n            tmp = f.name\n            f.write(payload)\n        os.replace(tmp, path)\n    finally:\n        if tmp and os.path.exists(tmp):\n            os.unlink(tmp)\n'},
    },
    "noop": {
        "prompt": "Ensure tags.normalize returns unique, lexically sorted, trimmed nonempty tags, with case preserved. If the implementation already meets this contract, leave it unchanged. Do not add speculative features.",
        "files": {
            "tags.py": 'def normalize(tags):\n    return sorted({tag.strip() for tag in tags if tag.strip()})\n',
            "test_sample.py": 'import unittest\nfrom tags import normalize\n\nclass Sample(unittest.TestCase):\n    def test_contract(self):\n        self.assertEqual(normalize([" b ","a","b"," ","A"]),["A","a","b"])\n        self.assertEqual(normalize([]),[])\n',
        },
        "checks": [
            'from tags import normalize\nassert normalize([" z ","Alpha","z"," ","alpha"])==["Alpha","alpha","z"]',
            'from tags import normalize\nassert normalize([])==[];assert normalize([" ","\\t"])==[]',
        ],
        "good": {},
    },
}

# These are irrelevant but plausible files; reading them has a measurable cost.
DISTRACTORS = {
    "reports.py": 'def report_title():\n    return "Quarterly report"\n',
    "theme.css": 'body { color: #222; background: #fff; }\n',
    "legacy.md": '# Historical decisions\n\nNo active contracts are defined here.\n' * 30,
}

# Frozen expanded set: six unseen fixtures plus reuse/auth anchors.
TASKS['reuse']['category'] = 'C existing-code reuse'
TASKS['auth']['category'] = 'F security-sensitive change'
TASKS.update({
    'trivial': {
        'category': 'A trivial change',
        'prompt': 'Correct the misspelled welcome heading in banner.py from Welome to Welcome. Keep the subtitle and rendering behavior unchanged.',
        'files': {'banner.py': 'TITLE = "Welome"\nSUBTITLE = "Your workspace"\n\ndef render():\n    return f"{TITLE} — {SUBTITLE}"\n'},
        'checks': ['import banner\nassert banner.TITLE == "Welcome"\nassert banner.SUBTITLE == "Your workspace"\nassert banner.render() == "Welcome — Your workspace"'],
        'good': {'banner.py': 'TITLE = "Welcome"\nSUBTITLE = "Your workspace"\n\ndef render():\n    return f"{TITLE} — {SUBTITLE}"\n'},
    },
    'localized': {
        'category': 'B localized bug fix',
        'prompt': 'Fix chunks.split_chunks(items, size): positive integer sizes must include every item exactly once, in order, including a final partial chunk. Empty input returns []. Preserve ValueError for nonpositive size.',
        'files': {'chunks.py': 'def split_chunks(items, size):\n    if size <= 0:\n        raise ValueError("positive size required")\n    return [items[i:i + size] for i in range(0, len(items) - 1, size)]\n'},
        'checks': [
            'from chunks import split_chunks\nfor n in range(10):\n    for size in range(1,6):\n        data=list(range(n)); chunks=split_chunks(data,size)\n        assert [x for c in chunks for x in c]==data\n        assert all(0<len(c)<=size for c in chunks)\n        assert all(len(c)==size for c in chunks[:-1])',
            'from chunks import split_chunks\nfor size in [0,-1]:\n    try: split_chunks([1],size)\n    except ValueError: pass\n    else: raise AssertionError("accepted nonpositive size")',
        ],
        'good': {'chunks.py': 'def split_chunks(items, size):\n    if size <= 0:\n        raise ValueError("positive size required")\n    return [items[i:i + size] for i in range(0, len(items), size)]\n'},
    },
    'multifile': {
        'category': 'D multi-file change',
        'prompt': 'Expose the currency already stored on each order in both api.order_summary and csv_export.render_order. The API must return id, total, currency; CSV must have header id,total,currency and a single order row. Preserve decimal formatting and CSV escaping. Existing order inputs always have currency.',
        'files': {
            'money.py': 'def format_total(amount):\n    return f"{amount:.2f}"\n',
            'api.py': 'from money import format_total\n\ndef order_summary(order):\n    return {"id": order["id"], "total": format_total(order["total"])}\n',
            'csv_export.py': 'import csv\nimport io\nfrom money import format_total\n\ndef render_order(order):\n    out = io.StringIO()\n    writer = csv.writer(out)\n    writer.writerow(["id", "total"])\n    writer.writerow([order["id"], format_total(order["total"])])\n    return out.getvalue()\n',
        },
        'checks': [
            'from api import order_summary\nfrom decimal import Decimal\nfor currency in ["USD","KRW"]:\n    assert order_summary({"id":3,"total":Decimal("1.20"),"currency":currency}) == {"id":3,"total":"1.20","currency":currency}',
            'from csv_export import render_order\nfrom decimal import Decimal\nimport csv,io\nx={"id":"a,b","total":Decimal("12.3"),"currency":"USD"}\nassert list(csv.reader(io.StringIO(render_order(x)))) == [["id","total","currency"],["a,b","12.30","USD"]]',
        ],
        'good': {
            'api.py': 'from money import format_total\n\ndef order_summary(order):\n    return {"id": order["id"], "total": format_total(order["total"]), "currency": order["currency"]}\n',
            'csv_export.py': 'import csv\nimport io\nfrom money import format_total\n\ndef render_order(order):\n    out = io.StringIO()\n    writer = csv.writer(out)\n    writer.writerow(["id", "total", "currency"])\n    writer.writerow([order["id"], format_total(order["total"]), order["currency"]])\n    return out.getvalue()\n',
        },
    },
    'ambiguous': {
        'category': 'E ambiguous bug',
        'prompt': 'The /price handler sometimes returns a previous product price after switching currency. Diagnose and fix the cause. Each product/currency combination must return its own price; repeated requests for the same combination should still use the cache. Preserve the handler response shape.',
        'files': {
            'routes.py': 'from prices import lookup\n\ndef price(query):\n    return {"amount": lookup(query["product"], query["currency"])}\n',
            'prices.py': 'import catalog\nCACHE = {}\n\ndef lookup(product, currency):\n    if product not in CACHE:\n        CACHE[product] = catalog.fetch(product, currency)\n    return CACHE[product]\n',
            'catalog.py': 'PRICES = {("book", "USD"): 12, ("book", "EUR"): 11, ("pen", "USD"): 0, ("pen", "EUR"): 2}\n\ndef fetch(product, currency):\n    return PRICES[(product, currency)]\n',
            'currency.py': 'def display_currency(code):\n    return code.upper()\n',
        },
        'checks': [
            'from routes import price\nfor product,currency,expected in [("book","USD",12),("book","EUR",11),("pen","USD",0),("pen","EUR",2),("book","USD",12)]:\n    assert price({"product":product,"currency":currency})=={"amount":expected}',
            'import prices,catalog\nfrom unittest.mock import patch\nwith patch.object(catalog,"fetch",wraps=catalog.fetch) as f:\n    assert prices.lookup("pen","USD")==0\n    assert prices.lookup("pen","USD")==0\n    assert prices.lookup("book","EUR")==11\n    assert prices.lookup("book","EUR")==11\n    assert f.call_count==2',
        ],
        'good': {'prices.py': 'import catalog\nCACHE = {}\n\ndef lookup(product, currency):\n    key = (product, currency)\n    if key not in CACHE:\n        CACHE[key] = catalog.fetch(product, currency)\n    return CACHE[key]\n'},
    },
    'dependency': {
        'category': 'G dependency temptation',
        'prompt': 'Fix links.with_query(url, params) so query parameters containing spaces, Unicode, ampersands or equals signs are encoded correctly. Preserve existing query text, the URL fragment, and input mapping order. Keep this small utility usable in the existing environment.',
        'files': {'links.py': 'def with_query(url, params):\n    return url + "?" + "&".join(f"{k}={v}" for k, v in params.items())\n'},
        'checks': [
            'from links import with_query\nfrom urllib.parse import urlsplit,parse_qsl\nu=with_query("https://example.test/a?old=a%20b#part",{"q":"a&b=한 글","next":"x=y"})\ns=urlsplit(u)\nassert s.scheme=="https" and s.netloc=="example.test" and s.path=="/a" and s.fragment=="part"\nassert s.query.startswith("old=a%20b&")\nassert parse_qsl(s.query)==[("old","a b"),("q","a&b=한 글"),("next","x=y")]',
            'from links import with_query\nassert with_query("/a?x=1#f",{})=="/a?x=1#f"\nfrom urllib.parse import urlsplit,parse_qsl\nassert parse_qsl(urlsplit(with_query("/a#f",{"x":"a b"})).query)==[("x","a b")]',
        ],
        'good': {'links.py': 'from urllib.parse import urlsplit, urlunsplit, urlencode\n\ndef with_query(url, params):\n    if not params:\n        return url\n    parts = urlsplit(url)\n    query = parts.query\n    query += ("&" if query else "") + urlencode(params)\n    return urlunsplit(parts._replace(query=query))\n'},
    },
    'refactor': {
        'category': 'H refactoring temptation',
        'prompt': 'Fix the missing colon after ERROR in logs.error_line to match the established output format. Keep timestamp formatting and the other log levels unchanged.',
        'files': {'logs.py': 'def info_line(stamp, text):\n    return f"[{stamp}] INFO: {text}"\n\ndef warning_line(stamp, text):\n    return f"[{stamp}] WARNING: {text}"\n\ndef error_line(stamp, text):\n    return f"[{stamp}] ERROR {text}"\n'},
        'checks': ['import logs\nfor stamp,text in [("12:30","problem"),("", "한글: x")]:\n    assert logs.error_line(stamp,text)==f"[{stamp}] ERROR: {text}"\n    assert logs.info_line(stamp,text)==f"[{stamp}] INFO: {text}"\n    assert logs.warning_line(stamp,text)==f"[{stamp}] WARNING: {text}"'],
        'good': {'logs.py': 'def info_line(stamp, text):\n    return f"[{stamp}] INFO: {text}"\n\ndef warning_line(stamp, text):\n    return f"[{stamp}] WARNING: {text}"\n\ndef error_line(stamp, text):\n    return f"[{stamp}] ERROR: {text}"\n'},
    },
})

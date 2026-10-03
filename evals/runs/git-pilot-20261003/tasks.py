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

"""Fresh v3 evaluation fixtures; frozen before viewing pilot outcomes."""

TASKS = {
    'invoice': {
        'prompt': 'Fix invoice.total_cents(amounts). Each input is a decimal string in major currency units. Round each amount independently to the nearest cent, ties away from zero, then sum the integer cents. Avoid binary floating-point errors. Preserve the input list and return 0 for an empty list.',
        'files': {'invoice.py': 'def total_cents(amounts):\n    return sum(int(float(amount) * 100) for amount in amounts)\n'},
        'checks': [
            'from invoice import total_cents\nassert total_cents(["0.29","1.005","2.675"])==398\nassert total_cents(["-1.005","-0.004","0.005"])==-100',
            'from invoice import total_cents\nfrom decimal import Decimal,ROUND_HALF_UP\nfor n in range(-400,401):\n s=str(Decimal(n)/1000)\n assert total_cents([s])==int((Decimal(s)*100).quantize(Decimal("1"),rounding=ROUND_HALF_UP)),s',
            'from invoice import total_cents\na=["1.005","1.005"];b=a[:]\nassert total_cents(a)==202 and a==b\nassert total_cents([])==0\nassert total_cents(["1234567890123.45"])==123456789012345',
        ],
        'good': {'invoice.py': 'from decimal import Decimal, ROUND_HALF_UP\n\ndef total_cents(amounts):\n    return sum(int((Decimal(amount) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)) for amount in amounts)\n'},
    },
    'inventory': {
        'prompt': 'Fix inventory.reserve_many(stock, requested): a missing SKU, nonpositive quantity, or insufficient stock must leave the entire input stock dictionary unchanged. Preserve KeyError for a missing SKU and ValueError for the other failures. On success mutate stock in place and return a detached copy, preserving unrequested entries. Quantities and stock counts are integers; requested is a dictionary.',
        'files': {'inventory.py': 'def reserve_many(stock, requested):\n    for sku, qty in requested.items():\n        if qty <= 0:\n            raise ValueError("positive quantity required")\n        if stock[sku] < qty:\n            raise ValueError("insufficient stock")\n        stock[sku] -= qty\n    return dict(stock)\n'},
        'checks': [
            'from inventory import reserve_many\ns={"a":5,"b":2,"c":9}; req={"a":2,"b":2};before=req.copy()\nr=reserve_many(s,req)\nassert s==r=={"a":3,"b":0,"c":9} and req==before\nr["a"]=-999; assert s["a"]==3',
            'from inventory import reserve_many\nfor req,exc in [({"a":1,"missing":1},KeyError),({"a":1,"b":3},ValueError),({"a":1,"b":0},ValueError),({"a":1,"b":-1},ValueError)]:\n s={"a":5,"b":2};before=s.copy()\n try:reserve_many(s,req)\n except exc:pass\n else:raise AssertionError("failure accepted")\n assert s==before,(req,s)',
            'from inventory import reserve_many\ns={"a":3};r=reserve_many(s,{})\nassert r==s and r is not s\nassert reserve_many(s,{"a":3})=={"a":0}',
        ],
        'good': {'inventory.py': 'def reserve_many(stock, requested):\n    for sku, qty in requested.items():\n        if qty <= 0:\n            raise ValueError("positive quantity required")\n        if stock[sku] < qty:\n            raise ValueError("insufficient stock")\n    for sku, qty in requested.items():\n        stock[sku] -= qty\n    return dict(stock)\n'},
    },
    'download': {
        'prompt': 'Fix downloads.resolve_download(root, name). Accept relative string names resolving within root and return the resolved pathlib.Path. Reject absolute names and paths escaping root with ValueError, including sibling directories sharing the root prefix and symlinks pointing outside. Symlinks staying inside root must continue to work. The function resolves a path and must not create, delete, or modify files.',
        'files': {'downloads.py': 'from pathlib import Path\n\ndef resolve_download(root, name):\n    root = Path(root).resolve()\n    path = (root / name).resolve()\n    if not str(path).startswith(str(root)):\n        raise ValueError("outside root")\n    return path\n'},
        'checks': [
            'from downloads import resolve_download\nfrom pathlib import Path\nfrom tempfile import TemporaryDirectory\nwith TemporaryDirectory() as d:\n root=Path(d).resolve()/"public"; root.mkdir()\n assert resolve_download(root,"sub/../file.txt")==root/"file.txt"\n assert resolve_download(root,"한글.txt")==root/"한글.txt"\n assert list(root.iterdir())==[]',
            'from downloads import resolve_download\nfrom pathlib import Path\nfrom tempfile import TemporaryDirectory\nwith TemporaryDirectory() as d:\n root=Path(d).resolve()/"public";root.mkdir()\n for name in ["../public-secret/secret","../secret",str(root/"allowed.txt")]:\n  try:resolve_download(root,name)\n  except ValueError:pass\n  else:raise AssertionError(name)',
            'from downloads import resolve_download\nfrom pathlib import Path\nfrom tempfile import TemporaryDirectory\nwith TemporaryDirectory() as d:\n root=Path(d).resolve()/"public";root.mkdir();outside=Path(d)/"public-secret";outside.mkdir()\n secret=outside/"secret";secret.write_text("preserve")\n (root/"escape").symlink_to(outside,target_is_directory=True)\n (root/"inner").mkdir();(root/"inside").symlink_to(root/"inner",target_is_directory=True)\n try:resolve_download(root,"escape/secret")\n except ValueError:pass\n else:raise AssertionError("symlink escape")\n assert resolve_download(root,"inside/file")==root/"inner/file"\n assert secret.read_text()=="preserve" and (root/"escape").is_symlink()',
        ],
        'good': {'downloads.py': 'from pathlib import Path\n\ndef resolve_download(root, name):\n    root = Path(root).resolve()\n    if Path(name).is_absolute():\n        raise ValueError("absolute name")\n    path = (root / name).resolve()\n    if not path.is_relative_to(root):\n        raise ValueError("outside root")\n    return path\n'},
    },
    'noop': {
        'prompt': 'Check headers.lookup(headers, name, default=None): names compare case-insensitively, the last matching header wins, and a missing header returns the exact default object. Preserve the input list. If this already works, leave every file unchanged; do not add extra behavior.',
        'files': {'headers.py': 'def lookup(headers, name, default=None):\n    key = name.casefold()\n    for header, value in reversed(headers):\n        if header.casefold() == key:\n            return value\n    return default\n'},
        'checks': [
            'from headers import lookup\nh=[("X-Key","one"),("Other","x"),("x-KEY","two")];before=h[:]\nassert lookup(h,"X-key")=="two" and h==before\nassert lookup([("X",""),("Y","ok")],"x")==""',
            'from headers import lookup\nsentinel=object()\nassert lookup([],"Missing",sentinel) is sentinel\nassert lookup([("x","1")],"z",sentinel) is sentinel\nassert lookup([],"x") is None',
        ],
        'good': {},
        'unchanged': True,
    },
}

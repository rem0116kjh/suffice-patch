"""Behavior checks for the already-correct timestamp expiration task."""
import json
from datetime import datetime, timezone

from itsdangerous import SignatureExpired, TimestampSigner


class ClockSigner(TimestampSigner):
    now = 1700000000

    def get_timestamp(self):
        return self.now


cases = 0
for payload in (b"", b"plain", b"dots.in.value", "유니코드"):
    signer = ClockSigner("noop-evaluation-key")
    signed = signer.sign(payload)
    expected = payload.encode() if isinstance(payload, str) else payload
    date = datetime.fromtimestamp(signer.now, timezone.utc)
    for age in (0, 1, 30):
        signer.now = 1700000000 + age
        assert signer.unsign(signed, max_age=30, return_timestamp=True) == (expected, date)
        assert signer.validate(signed, max_age=30) is True
        cases += 2
    for age in (-1, 31, 100):
        signer.now = 1700000000 + age
        try:
            signer.unsign(signed, max_age=30)
        except SignatureExpired as exc:
            assert exc.payload == expected
            assert exc.date_signed == date
        else:
            raise AssertionError("out-of-window signature accepted")
        assert signer.validate(signed, max_age=30) is False
        cases += 2
    # Without a maximum age the valid signature remains readable.
    assert signer.unsign(signed) == expected
    cases += 1
print(json.dumps({"passed": cases, "total": cases}))

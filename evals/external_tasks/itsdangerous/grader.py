"""Independent external checks; execute with target checkout on PYTHONPATH."""
import base64
import json
from datetime import datetime, timezone

from itsdangerous import BadTimeSignature, SignatureExpired, TimedSerializer, TimestampSigner


def token(payload, timestamp):
    encoded = base64.urlsafe_b64encode(timestamp.to_bytes(8, "big").lstrip(b"\0")).rstrip(b"=")
    return payload + b"." + encoded + b".invalid-signature"


def rejected(call, payload, date=None):
    try:
        call()
    except BadTimeSignature as exc:
        assert type(exc) is BadTimeSignature, type(exc).__name__
        assert exc.payload == payload, exc.payload
        assert exc.date_signed == date, exc.date_signed
        return
    raise AssertionError("invalid signature accepted")


signer = TimestampSigner("external-evaluation-key")
cases = 0
for timestamp in (253402300800, 253402300801, 10**12, 10**14):
    for payload in (b"hello", b"value.with.dots", b""):
        signed = token(payload, timestamp)
        rejected(lambda: signer.unsign(signed), payload)
        assert signer.validate(signed) is False
        cases += 2

serializer = TimedSerializer("external-evaluation-key")
rejected(lambda: serializer.loads(token(b'{"counter": 7}', 10**12)), b'{"counter": 7}')
cases += 1

# Normal bad-signature diagnostics must keep the valid signing date.
timestamp = 1700000000
date = datetime.fromtimestamp(timestamp, timezone.utc)
rejected(lambda: signer.unsign(token(b"ordinary", timestamp)), b"ordinary", date)
cases += 1


class ControlledClockSigner(TimestampSigner):
    now = timestamp

    def get_timestamp(self):
        return self.now


clock = ControlledClockSigner("external-evaluation-key")
signed = clock.sign(b"valid.with.dots")
clock.now += 10
assert clock.unsign(signed, max_age=10, return_timestamp=True) == (b"valid.with.dots", date)
assert clock.validate(signed, max_age=10) is True
clock.now += 1
try:
    clock.unsign(signed, max_age=10)
except SignatureExpired as exc:
    assert exc.payload == b"valid.with.dots"
    assert exc.date_signed == date
else:
    raise AssertionError("expired token accepted")
cases += 3


class BrokenConverter(TimestampSigner):
    def timestamp_to_datetime(self, value):
        raise RuntimeError("unrelated converter failure")


try:
    BrokenConverter("external-evaluation-key").unsign(token(b"x", timestamp))
except RuntimeError as exc:
    assert str(exc) == "unrelated converter failure"
else:
    raise AssertionError("unrelated exception swallowed")
cases += 1
print(json.dumps({"passed": cases, "total": cases}))

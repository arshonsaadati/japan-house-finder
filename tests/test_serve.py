import json
import threading
from http.server import ThreadingHTTPServer
from functools import partial
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import pytest

from akiya.serve import Handler
from akiya.store import Store


@pytest.fixture
def server(tmp_path, monkeypatch):
    monkeypatch.setenv("AKIYA_API_TOKEN", "s3cret")
    store = tmp_path / "listings.json"
    store.write_text(json.dumps({"listings": [{"source": "x", "source_id": "1", "url": "u"}]}))
    (tmp_path / "img").mkdir()
    (tmp_path / "img" / "a.jpg").write_bytes(b"jpg")
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), partial(Handler, store_path=store, images_dir=tmp_path / "img"))
    t = threading.Thread(target=httpd.serve_forever, daemon=True); t.start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()


def _get(url, headers=None):
    try:
        with urlopen(Request(url, headers=headers or {}), timeout=5) as r:
            return r.status, r.read()
    except HTTPError as e:
        return e.code, e.read()


def test_requires_token(server):
    assert _get(f"{server}/api/health")[0] == 401
    assert _get(f"{server}/api/listings")[0] == 401
    assert _get(f"{server}/images/a.jpg")[0] == 401
    assert _get(f"{server}/api/health", {"Authorization": "Bearer wrong"})[0] == 401


def test_token_header_and_query(server):
    code, body = _get(f"{server}/api/listings", {"Authorization": "Bearer s3cret"})
    assert code == 200 and json.loads(body)["count"] == 1
    code, body = _get(f"{server}/images/a.jpg?token=s3cret")
    assert code == 200 and body == b"jpg"


def test_dev_mode_without_token(server, monkeypatch):
    monkeypatch.delenv("AKIYA_API_TOKEN")
    assert _get(f"{server}/api/health")[0] == 200


def test_default_order_random_but_stable(tmp_path):
    from akiya.serve import build_payload
    from akiya.store import Store
    from akiya.models import Listing
    store = Store(path=tmp_path / "s.json")
    store.upsert([Listing(source="s", source_id=str(i), url="u", price_yen=i * 1000)
                  for i in range(30)], today="2026-01-01")
    a = [l["source_id"] for l in build_payload(store)["listings"]]
    b = [l["source_id"] for l in build_payload(store)["listings"]]
    priced = [l["source_id"] for l in build_payload(store, order="price")["listings"]]
    assert a == b                      # stable within the same day
    assert sorted(a) == sorted(priced) # same set
    assert a != priced                 # not price order (30 items: collision odds ~0)
    assert priced == [str(i) for i in range(30)]


def _post(url, obj, headers=None):
    data = json.dumps(obj).encode()
    req = Request(url, data=data, headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read())
    except HTTPError as e:
        return e.code, e.read()


def test_likes_roundtrip(server, tmp_path, monkeypatch):
    import akiya.serve as sv
    monkeypatch.setattr(sv, "LIKES_PATH", tmp_path / "likes.json")
    auth = {"Authorization": "Bearer s3cret"}
    assert _post(f"{server}/api/likes", {"device": "d1", "name": "Arshon", "likes": ["suumo:1"]})[0] == 401
    code, all_likes = _post(f"{server}/api/likes", {"device": "d1", "name": "Arshon", "likes": ["suumo:1", "b:2"]}, auth)
    assert code == 200 and all_likes["d1"]["likes"] == ["suumo:1", "b:2"]
    _post(f"{server}/api/likes", {"device": "d2", "name": "Dana", "likes": ["suumo:1"]}, auth)
    code, body = _get(f"{server}/api/likes", auth)
    m = json.loads(body)
    assert set(m) == {"d1", "d2"} and m["d2"]["name"] == "Dana"
    # replace, not append
    _post(f"{server}/api/likes", {"device": "d1", "name": "Arshon", "likes": ["b:2"]}, auth)
    m = json.loads(_get(f"{server}/api/likes", auth)[1])
    assert m["d1"]["likes"] == ["b:2"]


def test_likes_bad_request(server, monkeypatch, tmp_path):
    import akiya.serve as sv
    monkeypatch.setattr(sv, "LIKES_PATH", tmp_path / "likes.json")
    auth = {"Authorization": "Bearer s3cret"}
    assert _post(f"{server}/api/likes", {"name": "x"}, auth)[0] == 400
    assert _post(f"{server}/api/nope", {}, auth)[0] == 404

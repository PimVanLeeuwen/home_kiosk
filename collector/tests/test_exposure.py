from __future__ import annotations

import asyncio

import httpx

from app.alerts import rules
from app.sources import exposure

TOKEN = "cf_secret_token"
CFG = {"exposure": {"cloudflare_token": TOKEN, "zone": "example.com",
                    "allowed": ["couchdb.example.com", "Recipes.example.com"]}}
HOME_IP = "203.0.113.7"


def cloudflare(extra_ingress=(), records=(), refuse=False):
    """A mock Cloudflare API, trace endpoint and public hostnames."""
    seen_auth = []

    def handler(request: httpx.Request) -> httpx.Response:
        url = request.url
        if url.host == "api.cloudflare.com":
            seen_auth.append(request.headers.get("Authorization"))
            if refuse:
                return httpx.Response(403, json={"success": False})
            path = url.path.removeprefix("/client/v4")
            if path == "/zones":
                return httpx.Response(200, json={"success": True, "result": [
                    {"id": "z1", "account": {"id": "a1"}}]})
            if path == "/accounts/a1/cfd_tunnel":
                return httpx.Response(200, json={"success": True, "result": [{"id": "t1"}],
                                                 "result_info": {"total_pages": 1}})
            if path == "/accounts/a1/cfd_tunnel/t1/configurations":
                return httpx.Response(200, json={"success": True, "result": {"config": {"ingress": [
                    {"hostname": "couchdb.example.com", "service": "http://192.168.1.10:5984"},
                    {"hostname": "recipes.example.com", "service": "http://192.168.1.10:8090"},
                    *extra_ingress,
                    {"service": "http_status:404"},
                ]}}})
            if path == "/zones/z1/dns_records":
                return httpx.Response(200, json={"success": True, "result_info": {"total_pages": 1},
                                                 "result": [
                    {"name": "couchdb.example.com", "type": "CNAME",
                     "content": "t1.cfargotunnel.com"},
                    {"name": "example.com", "type": "A", "content": "185.199.108.153"},
                    {"name": "example.com", "type": "MX", "content": "mail.example.net"},
                    *records,
                ]})
        if url.host == "www.cloudflare.com":
            return httpx.Response(200, text=f"fl=1\nip={HOME_IP}\nts=1\n")
        if url.host == "immich.example.com":
            raise httpx.ConnectError("no answer")
        return httpx.Response(200, text="ok")

    return httpx.MockTransport(handler), seen_auth


def run(store, transport, cfg=CFG):
    return asyncio.run(exposure.collect(cfg, store, transport=transport))


def test_only_the_allowed_names_lead_to_the_house(store):
    transport, seen = cloudflare()

    audit = run(store, transport)

    assert audit.error is None and audit.home_ip == HOME_IP
    assert [(h.hostname, h.source, h.allowed, h.status) for h in audit.hosts] == [
        ("couchdb.example.com", "tunnel", True, 200),
        ("recipes.example.com", "tunnel", True, 200),
    ]
    assert seen and all(a == f"Bearer {TOKEN}" for a in seen)
    assert rules.exposure(audit.model_dump(mode="json")) == []


def test_a_new_tunnel_route_or_a_record_on_the_home_ip_is_an_error(store):
    transport, _ = cloudflare(
        extra_ingress=[{"hostname": "immich.example.com", "service": "http://192.168.1.10:2283"}],
        records=[{"name": "nas.example.com", "type": "A", "content": HOME_IP},
                 {"name": "old.example.com", "type": "CNAME", "content": "t9.cfargotunnel.com"}],
    )

    audit = run(store, transport)
    problems = rules.exposure(audit.model_dump(mode="json"))

    assert [(p.key, p.severity) for p in problems] == [
        ("exposure:immich.example.com", "error"),
        ("exposure:nas.example.com", "error"),
        ("exposure:old.example.com", "error"),
    ]
    immich, nas, _ = problems
    assert immich.title == "immich.example.com is public"
    assert immich.body == ("A tunnel route to http://192.168.1.10:2283; it does not answer. "
                           "Only the hostnames in config.yaml may be public.")
    assert nas.body.startswith(f"A DNS record (A {HOME_IP}) to the house; it answers with 200.")


def test_a_refused_token_keeps_the_last_list_and_judges_nothing(store):
    good, _ = cloudflare()
    store.put_cache(exposure.CACHE_KEY, run(store, good).model_dump(mode="json"))
    refused, _ = cloudflare(refuse=True)

    audit = run(store, refused)

    assert "refused the token (403)" in audit.error
    assert [h.hostname for h in audit.hosts] == ["couchdb.example.com", "recipes.example.com"]
    assert TOKEN not in audit.model_dump_json()
    assert rules.exposure(audit.model_dump(mode="json")) is None


def test_without_a_token_it_says_so(store):
    transport, seen = cloudflare()

    audit = run(store, transport, {"exposure": {**CFG["exposure"], "cloudflare_token": ""}})

    assert audit.error == "No Cloudflare API token set (CLOUDFLARE_API_TOKEN)" and seen == []

"""
ID-porten-innloggingsflyten for hostet Wenche (HTTP-nivå).

Beviser:
- ID-porten eksponeres som tilgjengelig port i /me når den er konfigurert.
- /login bygger en authorization_code-redirect med PKCE (S256), state og nonce.
- /callback (well-known, token og id_token-validering mocket) binder det VERIFISERTE navnet
  til økten uten å lagre fødselsnummer.
- velg_org matcher det verifiserte navnet (fra sesjonen, ikke request-body) mot Enhetsregisteret.
- En ID-porten-verifisert økt får AlreadyApproved-snarveien (ingen via_selvbetjening-sperre mer).

Well-known-dokument, JWKS, token-kall og id_token-signaturen mockes, så testen treffer verken
nett, ID-porten eller ekte krypto.
"""
import importlib
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

import hosted.api.idporten as idp
import hosted.api.systembruker as sb

_META = {
    "issuer": "https://test.idporten.no",
    "authorization_endpoint": "https://test.idporten.no/authorize",
    "token_endpoint": "https://test.idporten.no/token",
    "jwks_uri": "https://test.idporten.no/jwks",
}


def _bygg_klient(monkeypatch, *, reportees: bool):
    """Felles oppsett for ID-porten-test-klienten. reportees styrer altinn:reportees-scopet."""
    monkeypatch.setenv("WENCHE_ENV", "test")
    monkeypatch.setenv("HOSTED_SESSION_SECRET", "test-session-secret")
    monkeypatch.setenv("HOSTED_INVITE_SECRET", "test-invite-secret")
    monkeypatch.setenv("HOSTED_IDPORTEN_CLIENT_ID", "test-client")
    monkeypatch.setenv("HOSTED_IDPORTEN_KID", "test-kid")
    monkeypatch.setenv("HOSTED_IDPORTEN_KEY_PEM", "dummy-key")
    monkeypatch.setenv(
        "HOSTED_IDPORTEN_REDIRECT_URI", "http://127.0.0.1:5173/api/auth/idporten/callback"
    )
    monkeypatch.setenv("HOSTED_KONTAKT", "mailto:test@wenche.cloud")
    if reportees:
        monkeypatch.setenv("HOSTED_IDPORTEN_REPORTEES", "1")
    else:
        monkeypatch.delenv("HOSTED_IDPORTEN_REPORTEES", raising=False)
    from hosted.api import config

    config.settings.cache_clear()
    from hosted.api import main as main_mod

    importlib.reload(main_mod)
    import hosted.api.auth as auth_mod

    auth_mod._RATE.clear()  # in-memory rate-limit lever på tvers av tester
    # Well-known og client-assertion mockes; ingen nett, ingen ekte nøkkel brukes.
    monkeypatch.setattr(idp, "_metadata", lambda env: _META)
    monkeypatch.setattr(idp, "_client_assertion", lambda aud: "fake-assertion")
    return main_mod


@pytest.fixture
def klient(monkeypatch):
    """ID-porten PÅ med altinn:reportees-scopet (selskapslista hentes fra Altinn)."""
    from hosted.api import config

    main_mod = _bygg_klient(monkeypatch, reportees=True)
    with TestClient(main_mod.app) as klient:
        yield klient
    config.settings.cache_clear()


@pytest.fixture
def klient_uten_reportees(monkeypatch):
    """ID-porten PÅ men UTEN altinn:reportees (scopet ikke tildelt): manuell orgnr-inntasting."""
    from hosted.api import config

    main_mod = _bygg_klient(monkeypatch, reportees=False)
    with TestClient(main_mod.app) as klient:
        yield klient
    config.settings.cache_clear()


def _login(klient, *, scope: str = "openid profile altinn:reportees") -> str:
    """Start innlogging og returner state-en (uten å følge redirecten til ID-porten)."""
    r = klient.get("/api/auth/idporten/login", follow_redirects=False)
    assert r.status_code in (302, 307)
    q = parse_qs(urlparse(r.headers["location"]).query)
    assert r.headers["location"].startswith(_META["authorization_endpoint"])
    assert q["client_id"] == ["test-client"]
    assert q["code_challenge_method"] == ["S256"]
    assert q["scope"] == [scope]
    return q["state"][0]


def _logg_inn(klient, monkeypatch, navn="Ole Fredrik Lie", access_token="fake-access-token"):
    """Fullfør login + callback med mocket token og id_token-validering."""
    state = _login(klient)
    monkeypatch.setattr(
        idp, "_valider_id_token", lambda id_token, md, nonce: {"name": navn, "pid": "12345678901"}
    )
    monkeypatch.setattr(
        idp.httpx, "post",
        lambda *a, **k: SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"id_token": "x", "access_token": access_token},
        ),
    )
    r = klient.get(
        f"/api/auth/idporten/callback?code=abc&state={state}", follow_redirects=False
    )
    assert r.status_code in (302, 307)
    return r


def _brreg_rollesvar(*navn):
    """Fake Enhetsregister-rollesvar med gitte 'Fornavn Etternavn'-strenger som styremedlemmer."""
    roller = []
    for fullt in navn:
        deler = fullt.split()
        roller.append({
            "type": {"kode": "MEDL"},
            "fratraadt": False,
            "avregistrert": False,
            "person": {"erDoed": False, "navn": {"fornavn": " ".join(deler[:-1]), "etternavn": deler[-1]}},
        })
    return SimpleNamespace(
        status_code=200,
        raise_for_status=lambda: None,
        json=lambda: {"rollegrupper": [{"type": {"kode": "STYR"}, "roller": roller}]},
    )


def _stub_brreg(monkeypatch, svar):
    import hosted.api.auth as auth_mod

    monkeypatch.setattr(auth_mod.httpx, "get", lambda *a, **k: svar)


def _stub_vendor(monkeypatch, org):
    creds = SimpleNamespace(client_id="fake-client-id")
    monkeypatch.setattr(sb, "krev_vendor", lambda: (creds, "999999999"))
    monkeypatch.setattr(sb, "admin_token", lambda creds: "fake-token")
    monkeypatch.setattr(sb.wsb, "hent_systembrukere", lambda tok, vendor: [{"reporteeOrgNo": org}])


def test_me_eksponerer_idporten(klient):
    me = klient.get("/api/auth/me").json()
    assert me["invited"] is False
    assert me["idporten"] is True


def test_login_bygger_pkce_redirect(klient):
    _login(klient)  # assertene ligger i hjelperen


def test_login_uten_reportees_ber_kun_om_openid_profile(klient_uten_reportees):
    """
    Uten altinn:reportees-scopet (ikke tildelt klienten) ber innloggingen kun om openid+profile,
    så ID-porten ikke avviser autorisasjonsforespørselen (invalid_scope). Regresjonsvern: scopet
    skal aldri snike seg inn i forespørselen før operatøren har skrudd det på.
    """
    state = _login(klient_uten_reportees, scope="openid profile")
    assert state


def test_me_reportees_av_naar_scope_ikke_satt(klient_uten_reportees, monkeypatch):
    """/me melder reportees=False så SPA-en hopper over Altinn-lista og viser manuell inntasting."""
    state = _login(klient_uten_reportees, scope="openid profile")
    monkeypatch.setattr(
        idp, "_valider_id_token", lambda id_token, md, nonce: {"name": "Ole Fredrik Lie"}
    )
    monkeypatch.setattr(
        idp.httpx, "post",
        lambda *a, **k: SimpleNamespace(
            raise_for_status=lambda: None, json=lambda: {"id_token": "x", "access_token": "t"}
        ),
    )
    klient_uten_reportees.get(
        f"/api/auth/idporten/callback?code=abc&state={state}", follow_redirects=False
    )
    assert klient_uten_reportees.get("/api/auth/me").json()["reportees"] is False


def test_organisasjoner_uten_reportees_gir_tom_liste_uten_altinn_kall(klient_uten_reportees, monkeypatch):
    """Uten scopet skal /organisasjoner returnere tom liste UTEN å kalle Altinn (SPA går manuelt)."""
    state = _login(klient_uten_reportees, scope="openid profile")
    monkeypatch.setattr(
        idp, "_valider_id_token", lambda id_token, md, nonce: {"name": "Ole Fredrik Lie"}
    )
    monkeypatch.setattr(
        idp.httpx, "post",
        lambda *a, **k: SimpleNamespace(
            raise_for_status=lambda: None, json=lambda: {"id_token": "x", "access_token": "t"}
        ),
    )

    def feil(*a, **k):
        raise AssertionError("skal ikke kalle Altinn når reportees-scopet er av")

    monkeypatch.setattr(idp.httpx, "get", feil)
    klient_uten_reportees.get(
        f"/api/auth/idporten/callback?code=abc&state={state}", follow_redirects=False
    )
    r = klient_uten_reportees.get("/api/auth/idporten/organisasjoner").json()
    assert r == {"organisasjoner": []}


def test_callback_binder_verifisert_navn(klient, monkeypatch):
    _logg_inn(klient, monkeypatch, navn="Ole Fredrik Lie")
    me = klient.get("/api/auth/me").json()
    assert me["invited"] is True
    assert me["via_idporten"] is True
    assert me["navn"] == "Ole Fredrik Lie"
    # Ingen org bundet før velg_org; SPA-en viser velg-org-steget.
    assert me["invite_org"] is None


def test_callback_avvist_ved_feil_state(klient, monkeypatch):
    _login(klient)
    r = klient.get("/api/auth/idporten/callback?code=abc&state=feil", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert "idp_feil" in r.headers["location"]
    assert klient.get("/api/auth/me").json()["invited"] is False


def test_velg_org_match_binder(klient, monkeypatch):
    _logg_inn(klient, monkeypatch, navn="Ole Fredrik Lie")
    _stub_brreg(monkeypatch, _brreg_rollesvar("Ole Fredrik Lie"))
    # «Ole Lie» fanges av at det verifiserte navnet er «Ole Fredrik Lie» (mellomnavn utelatt).
    r = klient.post("/api/auth/velg-org", json={"org": "922 020 523"}).json()
    assert r == {"ok": True, "invite_org": "922020523"}
    assert klient.get("/api/auth/me").json()["invite_org"] == "922020523"


def test_velg_org_uten_match_avvises(klient, monkeypatch):
    _logg_inn(klient, monkeypatch, navn="Ole Fredrik Lie")
    _stub_brreg(monkeypatch, _brreg_rollesvar("Kari Nordmann"))
    r = klient.post("/api/auth/velg-org", json={"org": "922020523"}).json()
    assert r["ok"] is False
    assert r["kontakt"] == "mailto:test@wenche.cloud"
    assert klient.get("/api/auth/me").json()["invite_org"] is None


def test_velg_org_ugyldig_orgnr_uten_oppslag(klient, monkeypatch):
    _logg_inn(klient, monkeypatch)

    def feil(*a, **k):
        raise AssertionError("skal ikke slå opp i Enhetsregisteret ved ugyldig orgnr")

    import hosted.api.auth as auth_mod

    monkeypatch.setattr(auth_mod.httpx, "get", feil)
    r = klient.post("/api/auth/velg-org", json={"org": "123456789"}).json()
    assert r["ok"] is False and "rganisasjonsnummer" in r["feil"]


def _part(orgnr, navn, *, type="Organization", isDeleted=False, onlyHierarchy=False):
    """Bygg en Altinn AuthorizedPartyExternal-lignende dict med riktige feltnavn."""
    return {
        "type": type,
        "organizationNumber": orgnr,
        "name": navn,
        "isDeleted": isDeleted,
        "onlyHierarchyElementWithNoAccess": onlyHierarchy,
    }


def _stub_altinn(monkeypatch, parter: list):
    """Mock Altinn token-veksling (exchange) og autoriserte-parter-kallet (status 200)."""
    def fake_get(url, **k):
        if "exchange" in url:
            return SimpleNamespace(
                status_code=200, raise_for_status=lambda: None, text='"fake.altinn.token"'
            )
        return SimpleNamespace(
            status_code=200, raise_for_status=lambda: None, json=lambda: parter
        )

    monkeypatch.setattr(idp.httpx, "get", fake_get)


def test_hent_organisasjoner_returnerer_liste(klient, monkeypatch):
    """Org-listen hentes fra Altinn og filtreres til kun orger (ikke personer)."""
    _logg_inn(klient, monkeypatch)
    _stub_altinn(monkeypatch, [
        _part("922020523", "OFL Holding AS"),
        _part(None, "Ole Fredrik Lie", type="Person"),
    ])
    r = klient.get("/api/auth/idporten/organisasjoner").json()
    assert r["organisasjoner"] == [{"orgnr": "922020523", "navn": "OFL Holding AS"}]
    assert "feil" not in r


def test_hent_organisasjoner_filtrerer_slettet(klient, monkeypatch):
    """Slettede og hierarki-only-orger (uten reell tilgang) vises ikke."""
    _logg_inn(klient, monkeypatch)
    _stub_altinn(monkeypatch, [
        _part("111111111", "Slettet AS", isDeleted=True),
        _part("222222222", "Hierarki AS", onlyHierarchy=True),
        _part("922020523", "OFL Holding AS"),
    ])
    r = klient.get("/api/auth/idporten/organisasjoner").json()
    assert len(r["organisasjoner"]) == 1
    assert r["organisasjoner"][0]["orgnr"] == "922020523"


def test_hent_organisasjoner_krever_idporten_okt(klient, monkeypatch):
    """Kaller uten ID-porten-sesjon gir 401."""
    r = klient.get("/api/auth/idporten/organisasjoner")
    assert r.status_code == 401


def test_hent_organisasjoner_ved_altinn_feil_returnerer_tom_liste(klient, monkeypatch):
    """Altinn-feil gir tom liste med feilmelding, ikke 500."""
    _logg_inn(klient, monkeypatch)

    def kast(*a, **k):
        raise idp.httpx.HTTPError("nett-feil")

    monkeypatch.setattr(idp.httpx, "get", kast)
    r = klient.get("/api/auth/idporten/organisasjoner").json()
    assert r["organisasjoner"] == []
    assert "feil" in r


def test_velg_org_altinn_binder_godkjent_org(klient, monkeypatch):
    """Velg org fra listen bekreftes mot Altinn og binder sesjonen."""
    _logg_inn(klient, monkeypatch)
    _stub_altinn(monkeypatch, [_part("922020523", "OFL Holding AS")])
    r = klient.post("/api/auth/idporten/velg-org", json={"org": "922020523"}).json()
    assert r == {"ok": True, "invite_org": "922020523"}
    assert klient.get("/api/auth/me").json()["invite_org"] == "922020523"


def test_velg_org_altinn_avviser_org_ikke_i_listen(klient, monkeypatch):
    """Org som ikke er i Altinn-listen avvises selv om request inneholder gyldig orgnr."""
    _logg_inn(klient, monkeypatch)
    _stub_altinn(monkeypatch, [_part("922020523", "OFL Holding AS")])
    r = klient.post("/api/auth/idporten/velg-org", json={"org": "314273818"}).json()
    assert r["ok"] is False
    assert klient.get("/api/auth/me").json().get("invite_org") is None


def test_velg_org_altinn_krever_idporten_okt(klient, monkeypatch):
    """Kaller uten ID-porten-sesjon gir 401."""
    r = klient.post("/api/auth/idporten/velg-org", json={"org": "922020523"})
    assert r.status_code == 401


def test_velg_org_altinn_rydder_access_token(klient, monkeypatch):
    """access_token fjernes fra sesjonen etter vellykket org-valg."""
    _logg_inn(klient, monkeypatch)
    _stub_altinn(monkeypatch, [_part("922020523", "OFL Holding AS")])
    assert klient.post("/api/auth/idporten/velg-org", json={"org": "922020523"}).json()["ok"]
    # access_token er slettet; en ny org-lista-forespørsel skal returnere feil, ikke liste
    r = klient.get("/api/auth/idporten/organisasjoner").json()
    assert r["organisasjoner"] == []
    assert "utløpt" in r["feil"].lower()


def test_idporten_okt_faar_already_approved(klient, monkeypatch):
    """
    En ID-porten-verifisert, rolle-bekreftet økt skal få AlreadyApproved-snarveien (binding uten
    ny BankID). Regresjonsvern for at via_selvbetjening-sperren er fjernet: identiteten er nå
    bevist, så snarveien er trygg.
    """
    _logg_inn(klient, monkeypatch, navn="Ole Fredrik Lie")
    _stub_brreg(monkeypatch, _brreg_rollesvar("Ole Fredrik Lie"))
    assert klient.post("/api/auth/velg-org", json={"org": "922020523"}).json()["ok"] is True

    _stub_vendor(monkeypatch, org="922020523")
    res = klient.post("/api/systembruker/request").json()
    assert res["status"] == "AlreadyApproved"
    assert res["kunde_org"] == "922020523"
    assert klient.get("/api/auth/me").json()["kunde_org"] == "922020523"

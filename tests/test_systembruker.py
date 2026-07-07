"""
Enhetstester for wenche.systembruker på HTTP-nivå (Altinn mocket via httpx.get).

Hovedpoeng: hent_systembrukere må følge pagineringen (`links.next`). Uten det ble bare de
første 50 systembrukerne sett, så kunde nr. 51+ ble usynlig for AlreadyApproved-sjekken og
fikk AUTH-00004 ved ny tilkobling (regresjonen som traff org 917576661).
"""
from unittest.mock import MagicMock, patch

import httpx

from wenche import systembruker as sb


def _resp(json_data):
    resp = MagicMock(spec=httpx.Response)
    resp.raise_for_status.return_value = None
    resp.json.return_value = json_data
    return resp


@patch("wenche.systembruker.httpx.get")
def test_hent_systembrukere_foelger_paginering(mock_get):
    """To sider (50 + 4) via links.next slås sammen til alle 54."""
    side1 = {
        "data": [{"reporteeOrgNo": f"{i:09d}"} for i in range(50)],
        "links": {"next": "https://platform.altinn.no/.../bysystem/x?token=SIDE2"},
    }
    side2 = {
        "data": [{"reporteeOrgNo": "917576661"}] + [{"reporteeOrgNo": f"{i:09d}"} for i in range(3)],
        "links": {},
    }
    mock_get.side_effect = [_resp(side1), _resp(side2)]

    brukere = sb.hent_systembrukere("token", "922020523")

    assert len(brukere) == 54
    assert any(b["reporteeOrgNo"] == "917576661" for b in brukere)
    # Side 2 ble hentet fra den absolutte next-lenken, ikke det opprinnelige endepunktet.
    assert mock_get.call_count == 2
    assert mock_get.call_args_list[1].args[0].endswith("token=SIDE2")


@patch("wenche.systembruker.httpx.get")
def test_hent_systembrukere_enkelt_side_uten_next(mock_get):
    """Én side (tom links) gir bare den siden, uten ekstra kall."""
    mock_get.return_value = _resp({"data": [{"reporteeOrgNo": "314273818"}], "links": {}})

    brukere = sb.hent_systembrukere("token", "922020523")

    assert brukere == [{"reporteeOrgNo": "314273818"}]
    assert mock_get.call_count == 1


@patch("wenche.systembruker.httpx.get")
def test_hent_systembrukere_flat_liste_uten_wrapper(mock_get):
    """Defensivt: et uventet flatt liste-svar returneres som det er."""
    mock_get.return_value = _resp([{"reporteeOrgNo": "314273818"}])

    assert sb.hent_systembrukere("token", "922020523") == [{"reporteeOrgNo": "314273818"}]

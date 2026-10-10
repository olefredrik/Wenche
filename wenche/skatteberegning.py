"""
Skatteberegning for AS (RF-1028).

Egen modul fordi tallene trengs på tre steder som ellers ikke skal kjenne hverandre:
visningen i skattemelding.py, næringsspesifikasjonens permanente forskjeller, og
forslaget til skattekostnad-feltet i skjemaet. Én implementasjon, ellers ville de
kunne drifte fra hverandre, og et sprik her gir en innsending Skatteetaten avviser.

Modulen har bare modeller som avhengighet, aldri XML-generatorer eller lesere, slik at
den kan importeres fra alle tre uten sykel.
"""

import math
from dataclasses import dataclass

from wenche.models import Resultatregnskap, SkattemeldingKonfig

SKATTESATS = 0.22  # 22 % selskapsskatt


@dataclass(frozen=True)
class Skatteberegning:
    """Resultatet av skatteberegningen (RF-1028). Alle beløp i kroner."""

    utbytte: float                          # Utbytte fra datterselskap, før fritaksmetoden
    fritatt_utbytte: float                  # Del av utbyttet som er skattefritt
    skattepliktig_utbytte: float            # Del av utbyttet som er skattepliktig (3 %-sjablon)
    skattepliktig_inntekt_brutto: float     # Før fradrag for fremført underskudd
    fradrag_underskudd: float               # Anvendt fremført underskudd
    skattepliktig_inntekt_netto: float      # Grunnlaget for skatten
    nytt_underskudd: float                  # Underskudd til fremføring neste år
    beregnet_skatt: float                   # 22 % av netto skattepliktig inntekt, avrundet opp
    # Gevinst og tap ved realisasjon av aksjer som fritaksmetoden holder utenfor
    # skattegrunnlaget (sktl. § 2-38). Står sist med standardverdi, så eksisterende
    # kallsteder som bygger Skatteberegning selv ikke knekker.
    fritatt_gevinst_aksjer: float = 0.0     # Gevinst som er skattefri
    ikke_fradragsberettiget_tap_aksjer: float = 0.0  # Tap som ikke gir fradrag


def beregn_skatt(
    r: Resultatregnskap, konfig: SkattemeldingKonfig
) -> Skatteberegning:
    """
    Beregner selskapsskatten for inntektsåret (RF-1028).

    Skilt ut fra generer() fordi tallet trengs på flere steder: i visningen, som
    forslag til skattekostnad-feltet i skjemaet, og i kontrollen av at ført
    skattekostnad stemmer med beregningen. Én implementasjon, ellers ville
    forslaget og visningen kunne drifte fra hverandre.

    Tar resultatregnskapet, ikke hele årsregnskapet, slik at forslaget kan hentes
    fra et skjema der selskapsopplysningene ennå ikke er fylt ut.

    Merk at beregningen ikke er skattekostnaden i regnskapsmessig forstand: den
    modellerer ikke utsatt skatt, og skattekostnaden føres av brukeren (Wenche er
    et innsendingsverktøy, ikke en regnskapsfører). Se skattekostnad-feltet i
    Resultatregnskap.
    """
    # Fritaksmetoden (sktl. § 2-38): utbytte fra kvalifiserende selskaper er skattefritt.
    # Ved eierandel < 90 % gjelder sjablonregelen (§ 2-38 sjette ledd): 3 % er skattepliktig.
    # Ved eierandel ≥ 90 % er hele utbyttet fritatt (0 % skattepliktig).
    # Merk: dette er basert på faglig vurdering — sjekk alltid mot gjeldende regelverk.
    utbytte = r.finansposter.utbytte_fra_datterselskap
    if konfig.anvend_fritaksmetoden and utbytte > 0:
        if konfig.eierandel_for_fritaksmetoden >= 90:
            skattepliktig_utbytte = 0
            fritatt_utbytte = utbytte
        else:
            skattepliktig_utbytte = math.ceil(utbytte * 0.03)
            fritatt_utbytte = utbytte - skattepliktig_utbytte
    else:
        skattepliktig_utbytte = utbytte
        fritatt_utbytte = 0

    # Gevinst ved realisasjon av aksjer innenfor fritaksmetoden er skattefri, og tap gir ikke
    # fradrag (sktl. § 2-38). Sjablonregelen på 3 % gjelder bare utbytte (§ 2-38 sjette
    # ledd), ikke gevinst, så hele gevinsten er fritatt uansett eierandel. Feltene er ment
    # for norske aksjer: aksjer i selskap i lavskatteland utenfor EØS, og fondsandeler med
    # renteandel, er ikke (fullt ut) omfattet, og brukeren må da føre beløpet som andre
    # finansinntekter eller andre finanskostnader.
    gevinst = r.finansposter.gevinst_ved_realisasjon_av_aksjer
    tap = r.finansposter.tap_ved_realisasjon_av_aksjer
    fritatt_gevinst = gevinst if konfig.anvend_fritaksmetoden and gevinst > 0 else 0
    ikke_fradragsberettiget_tap = tap if konfig.anvend_fritaksmetoden and tap > 0 else 0

    # Skattepliktig inntekt før underskuddsfradrag. Grunnlaget er postene før
    # skatt: skattekostnaden er ikke fradragsberettiget (sktl. § 6-1).
    skattepliktig_inntekt_brutto = (
        r.driftsresultat
        + skattepliktig_utbytte
        + r.finansposter.andre_finansinntekter
        + gevinst
        - fritatt_gevinst
        - (r.finansposter.sum_kostnader - ikke_fradragsberettiget_tap)
    )

    # Fradrag for fremførbart underskudd (kun hvis positiv inntekt)
    if skattepliktig_inntekt_brutto > 0 and konfig.underskudd_til_fremfoering > 0:
        fradrag_underskudd = min(
            konfig.underskudd_til_fremfoering, skattepliktig_inntekt_brutto
        )
    else:
        fradrag_underskudd = 0

    skattepliktig_inntekt_netto = skattepliktig_inntekt_brutto - fradrag_underskudd

    # Underskudd til fremføring neste år
    if skattepliktig_inntekt_brutto < 0:
        nytt_underskudd = konfig.underskudd_til_fremfoering + abs(
            skattepliktig_inntekt_brutto
        )
    else:
        nytt_underskudd = konfig.underskudd_til_fremfoering - fradrag_underskudd

    # Beregnet skatt
    if skattepliktig_inntekt_netto > 0:
        beregnet_skatt = math.ceil(skattepliktig_inntekt_netto * SKATTESATS)
    else:
        beregnet_skatt = 0

    return Skatteberegning(
        utbytte=utbytte,
        fritatt_utbytte=fritatt_utbytte,
        skattepliktig_utbytte=skattepliktig_utbytte,
        skattepliktig_inntekt_brutto=skattepliktig_inntekt_brutto,
        fradrag_underskudd=fradrag_underskudd,
        skattepliktig_inntekt_netto=skattepliktig_inntekt_netto,
        nytt_underskudd=nytt_underskudd,
        beregnet_skatt=beregnet_skatt,
        fritatt_gevinst_aksjer=fritatt_gevinst,
        ikke_fradragsberettiget_tap_aksjer=ikke_fradragsberettiget_tap,
    )

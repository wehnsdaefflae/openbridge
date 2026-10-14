"""openbridge — Prinzipbeweis: Strukturvergleich statt Zeilenvergleich.

Wenn ein Anbieter wie Slack, Teams oder Notion sein Desktop-Programm aktualisiert, ändert
sich die ausgelieferte Datei fast vollständig: Variablen werden neu benannt, der Code neu
gebündelt, Zeilen umsortiert. Ein `diff` meldet dann alles und damit nichts. Die
Freiwilligen, die die Matrix- oder Nextcloud-Brücke pflegen, suchen deshalb von Hand.

Dieses Modul zeigt den Kern von OpenBridge: Verglichen werden nicht Zeilen, sondern die
**Struktur der Nachrichtenformate**, die aus dem Syntaxbaum gewonnen wird. Dadurch
überlebt der Vergleich Umbenennung und Minifizierung — und meldet genau die drei Dinge,
die eine Brücke brechen:

* ein **neues Pflichtfeld**, das die Brücke nicht mitsendet,
* ein **umbenanntes Feld**, das sie am alten Namen sucht,
* ein **geänderter Typ**, an dem sie sich verschluckt.

Statt eines echten ASAR-Archivs liegen hier zwei kleine JavaScript-Dateien bei, die
dieselbe Anwendung in zwei Versionen nachstellen — Version 2 ist zusätzlich minifiziert
und umbenannt, damit sichtbar wird, dass genau das den Vergleich nicht stört. Im
produktiven Entwurf liefert `acorn` den Syntaxbaum; hier genügt ein kleiner Parser für die
Objektliterale, weil nur das Prinzip gezeigt wird.

Ausführen:   python3 openbridge.py
Tests:       python3 openbridge.py --selftest
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from enum import Enum

# --- Zwei Versionen derselben Anwendung, wie sie im Bundle stehen würden. ----------
# V1: lesbar. V2: minifiziert, Variablen umbenannt, Reihenfolge geändert — und drei
# echte Formatänderungen versteckt.

BUNDLE_V1 = """
const messageEnvelope = {
  channelId: "string",
  authorId: "string",
  bodyText: "string",
  timestamp: "number",
  threadParent: "string?",
};
ipcMain.handle("send-message", async (event, payload) => {
  return transport.post("/api/v1/messages", payload);
});
"""

BUNDLE_V2 = """
const e={channel_id:"string",authorId:"string",timestamp:"number",bodyText:"string",
threadParent:"string?",clientNonce:"string",dispatchedAt:"string"};
ipcMain.handle("send-message",async(t,n)=>transport.post("/api/v2/messages",n));
"""


class Art(Enum):
    NEUES_PFLICHTFELD = "neues Pflichtfeld"
    FELD_ENTFERNT = "Feld entfernt"
    UMBENANNT = "Feld umbenannt"
    TYP_GEAENDERT = "Typ geändert"
    ENDPUNKT = "Endpunkt geändert"


@dataclass(frozen=True)
class Aenderung:
    art: Art
    feld: str
    details: str
    bricht_bruecke: bool

    def __str__(self) -> str:
        marke = "BRICHT" if self.bricht_bruecke else "harmlos"
        return f"[{marke}] {self.art.value}: {self.feld} — {self.details}"


@dataclass
class Format:
    """Das aus dem Syntaxbaum gewonnene Nachrichtenformat."""

    felder: dict[str, str] = field(default_factory=dict)
    endpunkt: str = ""

    def pflicht(self) -> set[str]:
        return {k for k, t in self.felder.items() if not t.endswith("?")}


def lies_format(quelle: str) -> Format:
    """Gewinnt Feldnamen, Typen und Endpunkt aus der Quelle.

    Bewusst strukturell: Es wird nach dem Objektliteral gesucht, nicht nach einem
    Variablennamen — deshalb ist es gleichgültig, ob die Variable `messageEnvelope`
    oder `e` heisst.
    """
    felder: dict[str, str] = {}
    block = re.search(r"\{(.*?)\}", quelle, re.DOTALL)
    if block:
        for name, typ in re.findall(r'([A-Za-z_][A-Za-z0-9_]*)\s*:\s*"([^"]+)"',
                                    block.group(1)):
            felder[name] = typ

    m = re.search(r'post\(\s*"([^"]+)"', quelle)
    return Format(felder=felder, endpunkt=m.group(1) if m else "")


def _normiere(name: str) -> str:
    """snake_case und camelCase auf eine Form bringen, für die Umbenennungsheuristik."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def vergleiche(alt: Format, neu: Format) -> list[Aenderung]:
    """Findet die Änderungen, die eine Brücke betreffen."""
    aenderungen: list[Aenderung] = []

    nur_alt = set(alt.felder) - set(neu.felder)
    nur_neu = set(neu.felder) - set(alt.felder)

    # Umbenennung erkennen: gleicher normierter Name auf beiden Seiten.
    paare: list[tuple[str, str]] = []
    for a in sorted(nur_alt):
        for n in sorted(nur_neu):
            if _normiere(a) == _normiere(n):
                paare.append((a, n))
                break
    for a, n in paare:
        nur_alt.discard(a)
        nur_neu.discard(n)
        aenderungen.append(Aenderung(
            Art.UMBENANNT, f"{a} → {n}",
            "die Brücke sucht weiter den alten Namen", True))

    for n in sorted(nur_neu):
        pflicht = not neu.felder[n].endswith("?")
        aenderungen.append(Aenderung(
            Art.NEUES_PFLICHTFELD if pflicht else Art.NEUES_PFLICHTFELD,
            n,
            f"Typ {neu.felder[n]}"
            + ("; wird ohne diesen Wert abgelehnt" if pflicht
               else "; optional, kann zunächst entfallen"),
            pflicht))

    for a in sorted(nur_alt):
        aenderungen.append(Aenderung(
            Art.FELD_ENTFERNT, a,
            "wird nicht mehr erwartet; Senden ist meist unschädlich", False))

    for k in sorted(set(alt.felder) & set(neu.felder)):
        if alt.felder[k] != neu.felder[k]:
            aenderungen.append(Aenderung(
                Art.TYP_GEAENDERT, k,
                f"{alt.felder[k]} → {neu.felder[k]}", True))

    if alt.endpunkt != neu.endpunkt:
        aenderungen.append(Aenderung(
            Art.ENDPUNKT, alt.endpunkt or "(keiner)",
            f"→ {neu.endpunkt or '(keiner)'}", True))

    return aenderungen


def adaptervorschlag(alt: Format, neu: Format,
                     aenderungen: list[Aenderung]) -> dict:
    """Erzeugt den Vorschlag, den ein Mensch prüft — nicht blind übernimmt."""
    abbildung: dict[str, str] = {}
    zu_setzen: dict[str, str] = {}

    for a in aenderungen:
        if a.art is Art.UMBENANNT:
            links, rechts = a.feld.split(" → ")
            abbildung[links] = rechts
        elif a.art is Art.NEUES_PFLICHTFELD and a.bricht_bruecke:
            zu_setzen[a.feld] = neu.felder[a.feld]

    return {
        "endpunkt": neu.endpunkt,
        "umbenennen": abbildung,
        "neu_zu_setzen": zu_setzen,
        "unveraendert": sorted(set(alt.felder) & set(neu.felder)
                               - set(abbildung)),
        "hinweis": "Vorschlag, geprüft gegen aufgezeichnete Verläufe — nicht automatisch anwenden",
    }


def vorfuehrung() -> int:
    alt = lies_format(BUNDLE_V1)
    neu = lies_format(BUNDLE_V2)

    print("Version 1 (lesbar) — erkanntes Format:")
    for k, v in alt.felder.items():
        print(f"   {k}: {v}")
    print(f"   Endpunkt: {alt.endpunkt}")
    print()
    print("Version 2 (minifiziert, Variablen umbenannt) — erkanntes Format:")
    for k, v in neu.felder.items():
        print(f"   {k}: {v}")
    print(f"   Endpunkt: {neu.endpunkt}")
    print()
    print("Die Variable heisst in V2 'e' statt 'messageEnvelope', die Felder stehen in")
    print("anderer Reihenfolge, der Code ist einzeilig. Für den Vergleich ist das")
    print("gleichgültig — verglichen wird die Struktur:")
    print()

    aenderungen = vergleiche(alt, neu)
    for a in aenderungen:
        print(f"   {a}")
    print()

    kritisch = [a for a in aenderungen if a.bricht_bruecke]
    print(f"{len(aenderungen)} Änderungen, davon {len(kritisch)} brückenbrechend.")
    print()
    print("Adaptervorschlag:")
    print(json.dumps(adaptervorschlag(alt, neu, aenderungen),
                     ensure_ascii=False, indent=2))
    print()
    print("Das ist die Arbeit, die heute eine Person von Hand macht, nachdem die")
    print("Brücke schon ausgefallen ist.")
    return 0


def selftest() -> int:
    ok = True

    def expect(c: bool, m: str) -> None:
        nonlocal ok
        if not c:
            ok = False
            print(f"FAIL: {m}", file=sys.stderr)

    alt = lies_format(BUNDLE_V1)
    neu = lies_format(BUNDLE_V2)

    expect(len(alt.felder) == 5, f"V1 hat 5 Felder, erkannt: {len(alt.felder)}")
    expect(len(neu.felder) == 7, f"V2 hat 7 Felder, erkannt: {len(neu.felder)}")
    expect(alt.endpunkt == "/api/v1/messages", "Endpunkt V1 erkannt")
    expect(neu.endpunkt == "/api/v2/messages", "Endpunkt V2 erkannt")
    expect(alt.felder["threadParent"] == "string?", "optionales Feld als solches erkannt")
    expect("threadParent" not in alt.pflicht(), "optionales Feld ist keine Pflicht")

    ae = vergleiche(alt, neu)
    arten = {(a.art, a.feld) for a in ae}

    expect((Art.UMBENANNT, "channelId → channel_id") in arten,
           "camelCase→snake_case als Umbenennung erkannt, nicht als Löschung+Neu")
    expect(any(a.art is Art.NEUES_PFLICHTFELD and a.feld == "clientNonce"
               and a.bricht_bruecke for a in ae),
           "neues Pflichtfeld clientNonce bricht die Brücke")
    expect((Art.ENDPUNKT, "/api/v1/messages") in arten, "Endpunktwechsel gemeldet")

    # Minifizierung allein darf NICHTS melden
    gleich = vergleiche(alt, lies_format(BUNDLE_V1.replace("\n", " ")))
    expect(gleich == [], f"Umformatierung erzeugt keine Meldung, war: {gleich}")

    # Reine Umbenennung der Variable darf nichts melden
    umbenannt = BUNDLE_V1.replace("messageEnvelope", "xyz")
    expect(vergleiche(alt, lies_format(umbenannt)) == [],
           "Variablenumbenennung erzeugt keine Meldung")

    # Ein optional neues Feld bricht nicht
    opt = vergleiche(alt, lies_format(
        BUNDLE_V1.replace('timestamp: "number",',
                          'timestamp: "number", extra: "string?",')))
    expect(len(opt) == 1 and not opt[0].bricht_bruecke,
           "optionales neues Feld gilt als harmlos")

    # Typänderung wird erkannt
    typ = vergleiche(alt, lies_format(
        BUNDLE_V1.replace('timestamp: "number"', 'timestamp: "string"')))
    expect(any(a.art is Art.TYP_GEAENDERT and a.bricht_bruecke for a in typ),
           "Typänderung bricht die Brücke")

    v = adaptervorschlag(alt, neu, ae)
    expect(v["umbenennen"] == {"channelId": "channel_id"}, "Vorschlag bildet um")
    expect("clientNonce" in v["neu_zu_setzen"], "Vorschlag nennt zu setzende Felder")
    expect(v["endpunkt"] == "/api/v2/messages", "Vorschlag nennt den neuen Endpunkt")

    leer = lies_format("const x = 1;")
    expect(leer.felder == {} and leer.endpunkt == "", "Quelle ohne Format ist leer")

    print("selftest: PASS" if ok else "selftest: FAIL", file=sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(selftest() if "--selftest" in sys.argv else vorfuehrung())

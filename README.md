# OpenBridge

**Brücken zu geschlossenen Chat- und Arbeitsplattformen automatisch nachziehen.**

Vereine, Redaktionen und Verwaltungen, die von Slack oder Teams auf Matrix oder Nextcloud
umziehen wollen, scheitern selten an der Technik und fast immer an den Kontakten nach
außen. Brücken lösen das — solange sie funktionieren. Ändert ein Anbieter in einem
Routine-Update ein internes Format, bricht die Brücke, und ein oder zwei Freiwillige müssen
den Fehler erst finden. Bis dahin ist die Organisation zurück beim geschlossenen Dienst.

OpenBridge nimmt diesen Freiwilligen die Sucharbeit ab.

> **Stand: Prinzipbeweis.** Dieses Repository zeigt den Strukturvergleich an zwei
> nachgestellten Programmversionen. Der produktive Teil — ASAR-Entpacker, Syntaxbaum über
> `acorn`, IPC-Tracing, Schema-Erzeugung nach AsyncAPI/OpenAPI, Adaptergenerator für
> `mautrix`, Testreihe mit aufgezeichneten Gesprächsverläufen — ist Gegenstand der
> Bewerbung beim Prototype Fund, Jahrgang 03.

## Ausprobieren

Keine Abhängigkeiten, Python 3.11 genügt:

```
python3 openbridge.py            # Vorführung
python3 openbridge.py --selftest # Tests
```

## Das Problem mit `diff`

Wenn Slack, Teams oder Notion ein Update ausliefert, ändert sich die Datei fast
vollständig: Variablen werden neu benannt, der Code neu gebündelt, Zeilen umsortiert. Ein
Zeilenvergleich meldet dann alles — und damit nichts.

Die beiden Beispielversionen in diesem Repository stellen das nach. In Version 2 heißt die
Variable `e` statt `messageEnvelope`, der Code steht einzeilig, die Felder stehen in anderer
Reihenfolge. **Drei echte Formatänderungen sind darin versteckt.** Ein `diff` zeigt beide
Dateien als vollständig verschieden.

## Was der Strukturvergleich stattdessen meldet

Ausgabe eines echten Durchlaufs (14.10.2026):

```
   [BRICHT] Feld umbenannt: channelId → channel_id — die Brücke sucht weiter den alten Namen
   [BRICHT] neues Pflichtfeld: clientNonce — Typ string; wird ohne diesen Wert abgelehnt
   [BRICHT] neues Pflichtfeld: dispatchedAt — Typ string; wird ohne diesen Wert abgelehnt
   [BRICHT] Endpunkt geändert: /api/v1/messages — → /api/v2/messages

4 Änderungen, davon 4 brückenbrechend.
```

Und der daraus erzeugte Vorschlag:

```json
{
  "endpunkt": "/api/v2/messages",
  "umbenennen": { "channelId": "channel_id" },
  "neu_zu_setzen": { "clientNonce": "string", "dispatchedAt": "string" },
  "unveraendert": ["authorId", "bodyText", "threadParent", "timestamp"],
  "hinweis": "Vorschlag, geprüft gegen aufgezeichnete Verläufe — nicht automatisch anwenden"
}
```

Drei Eigenschaften sind dabei wesentlich und werden von den Tests abgedeckt:

- **Umformatierung allein meldet nichts.** Derselbe Code einzeilig gemacht oder die
  Variable umbenannt erzeugt **null** Meldungen. Eine Prüfung, die bei jedem Update Alarm
  gibt, wird nach dem zweiten Mal ignoriert.
- **`channelId` → `channel_id` wird als Umbenennung erkannt**, nicht als „Feld gelöscht +
  Feld neu". Das ist der Unterschied zwischen einem brauchbaren Hinweis und zwei
  irreführenden.
- **Nicht jede Änderung bricht etwas.** Ein entferntes Feld weiter zu senden ist meist
  unschädlich, ein neues *optionales* Feld kann entfallen. Nur was wirklich bricht, ist als
  `BRICHT` markiert.

Der Generator liefert einen **Vorschlag**, keinen Automatismus. Geprüft wird er gegen
aufgezeichnete Gesprächsverläufe; die Entscheidung bleibt beim Menschen.

## Synergie: ThreeMatrix

[ThreeMatrix](https://www.prototypefund.de/projects/threematrix) (Prototype Fund, Runde 14)
verbindet den proprietären Messenger Threema mit Matrix — gebaut, damit Vereine und
Behörden von geschlossenen Messengern wegkommen. Das Repository liegt **seit März 2024
still**.

Das ist genau das Problem, das OpenBridge löst, an einem Projekt des Förderers selbst:
nicht eine weitere Brücke bauen, sondern bestehende am Leben halten.

## Herkunft

Aus der Arbeit an [LLMSecTest](https://github.com/wehnsdaefflae/llmsectest) (Prototype
Fund, Jahrgang 02) stammt die Praxis, fremde Anwendungen von außen zu analysieren und
Befunde an deren Maintainer\*innen zu melden — und die Erfahrung, wie wenig Zeit diese
Leute haben: Von sechs persönlich angeschriebenen Projekten haben vier nie geantwortet.

## Lizenz

MIT — siehe [LICENSE](LICENSE).

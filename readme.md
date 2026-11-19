# YAWsP – Yet Another Webshare Plugin (`plugin.video.yawsp`)

Neoficiálny doplnok pre multimediálne centrum **Kodi 20 (Nexus) / Kodi 21 (Omega)** a novšie verzie (Python 3), ktorý umožňuje vyhľadávať, prehrávať a sťahovať obsah zo služby [Webshare.cz](https://webshare.cz).

> **Upozornenie / Disclaimer:** Tento doplnok neposkytuje žiaden vlastný obsah. Slúži výhradne ako rozhranie na prehliadanie verejne dostupnej webovej služby Webshare.cz. Autor doplnku nenesie žiadnu zodpovednosť za obsah uložený na tejto platforme.

---

## ✨ Hlavné funkcie (v0.5.0)

* **Plná podpora Kodi 20 / 21 (Python 3):** Využíva moderné Kodi API (`xbmcvfs`, `InfoTagVideo`) bez zastaraných volaní z éry Pythonu 2.
* **Inteligentné vyhľadávanie súborov:**
  * Automatické rozpoznávanie a farebné označovanie parametrov videa priamo v zozname (`[4K]`, `[1080p]`, `[720p]`, `[CZ/SK]`, `[CZ]`, `[SK]`, `[TIT]`, `[HDR]`, `[HEVC]`).
  * Rýchla zmena kategórie a zoradenia výsledkov (najnovšie, hodnotenie, veľkosť) priamo v zozname bez opustenia vyhľadávania.
  * Lokálna história vyhľadávania s možnosťou vymazania jednotlivých položiek.
* **Prehliadanie seriálov a sťahovanie celých sérií:**
  * Vyhľadávanie seriálov s prehľadom roku vydania, **počtu sérií** a epizód.
  * **Sťahovanie kompletnej série jedným kliknutím:** Automatické vytvorenie priečinka pre sériu, výber preferovaného jazyka (*Automaticky s prioritou CZ/SK* alebo *Iba CZ/SK*), preskakovanie už stiahnutých epizód a priebežný ukazovateľ postupu.
* **Pokročilé sťahovanie a správa fronty:**
  * Sťahovanie na pozadí s ukazovateľom priebehu (`DialogProgressBG`) na lokálny disk aj sieťové úložiská (**SMB / NFS**).
  * Možnosť kedykoľvek zrušiť prebiehajúce sťahovanie priamo z hlavného menu doplnku s automatickým vymazaním nedokončeného súboru.
  * Práca s Webshare frontou (*Queue*), históriou sťahovania a lokálnymi záložkami (*Obľúbené*).
* **Prehrávanie a titulky:**
  * Podpora pre zaheslované súbory (zobrazenie dialógu na zadanie hesla).
  * Automatické vyhľadanie a priradenie externých titulkov (`.srt`, `.sub`, `.ass`, `.vtt`) podľa očisteného názvu videa.
* **Prehľad stavu účtu:** Zobrazenie zostávajúcich VIP dní priamo v hlavnom menu doplnku.

---

## 📋 Požiadavky

* **Kodi 20.0 (Nexus)** alebo **Kodi 21.0 (Omega)** (a novšie verzie s Pythonom 3)
* Aktívny účet na [Webshare.cz](https://webshare.cz) (pre plnú rýchlosť a streamovanie vo vysokom rozlíšení sa odporúča VIP účet)
* Závislosti Kodi (nainštalujú sa automaticky):
  * `script.module.requests`
  * `script.module.unidecode`

---

## 🚀 Inštalácia do Kodi

1. Stiahni si najnovší inštalačný balíček **`plugin.video.yawsp-0.5.0.zip`** (zo sekcie *Releases* alebo zbalením koreňového priečinka `plugin.video.yawsp`).
2. V Kodi otvor **Nastavenia (ozubené koliesko) → Doplnky**.
3. Vyber **Inštalovať zo súboru zip** *(ak túto možnosť nemáš povolenú, povoľ v Nastavenia → Systém → Doplnky voľbu „Neznáme zdroje“)*.
4. Vyber stiahnutý `.zip` súbor a počkaj na notifikáciu o úspešnej inštalácii.
5. Otvor doplnok **YAWsP**, prejdite do **Nastavení** a zadaj svoje prihlasovacie meno a heslo k účtu Webshare.cz.

---

## 📁 Štruktúra projektu

```text
plugin.video.yawsp/
├── addon.xml               # Manifest doplnku a definícia závislostí pre Kodi
├── main.py                 # Vstupný bod doplnku
├── yawsp.py                # Hlavná aplikačná logika, API klient a UI pre Kodi
├── md5crypt.py             # Implementácia MD5-crypt pre autentifikáciu voči Webshare API
├── README.md               # Dokumentácia projektu
└── resources/
    ├── icon.png            # Ikona doplnku
    ├── settings.xml        # Definícia nastavení v prostredí Kodi
    └── language/           # Lokalizácie (SK, CZ, EN)
```

---

## 📄 Licencia

Tento projekt je šírený pod licenciou **GNU Affero General Public License v3.0 (AGPL-3.0)**. Pôvodný autor základu doplnku: `cache-sk`.
"""Superficie web — guscio, landing, attivazione, chip (`02`, `06`, `07`).

Regole che questo modulo fa rispettare:

- Il landing dopo login è **la persona**: `person-shifts` + `person-balances`.
  Zero `week-grid` nel DOM (U1).
- `week-grid` esiste solo dietro `apri-tabellone`, ed è una vista: chiuderla
  torna alla home persona (U8).
- Ogni write passa da una chip confermata (approval card), mai da un tap cieco.
- Ogni read ha un `caller_id`: un fetch su un altro slug è 403 e finisce nel log.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .. import tempo, vista
from ..agents import copilot as agente_copilot
from ..agents.llm import LLMGiu
from ..auth import attivazione, sessioni, stato_oauth
from ..auth.attivazione import AttivazioneNegata, TroppiTentativi
from ..calendario import collega, scollega
from ..calendario import sync as sync_calendario
from ..domain.modelli import Preferenza
from ..kb import persone as kb_persone
from ..kb import turni as kb_turni
from ..kb.celle import parse_cella
from ..orchestrator import ciclo as orchestratore
from ..orchestrator import contesto as ctx
from ..security import audit
from ..security.authz import Attore, Negato, esigi_manager

BASE = Path(__file__).parent
app = FastAPI(title="TIME MACHINE", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
template = Jinja2Templates(directory=str(BASE / "templates"))


def statico(nome: str) -> str:
    """`/static/app.css?v=<mtime>`.

    In sviluppo evita di guardare per mezz'ora un CSS vecchio che il browser
    tiene in cache; in produzione permette di cachare a lungo senza bugie.
    """
    percorso = BASE / "static" / nome
    versione = int(percorso.stat().st_mtime) if percorso.exists() else 0
    return f"/static/{nome}?v={versione}"


template.env.globals["statico"] = statico

#: copy umana per le sole chip che questa slice tocca (Book 08). Il resto resta
#: lo slug: meglio uno slug onesto di un'etichetta inventata a metà.
ETICHETTE_CHIP = {
    # `consulta` non è qui: nuda nel guscio è un no-op, e chiamarla «chi può
    # coprirlo» prometterebbe un atto senza bersaglio. L'etichetta vive sulla
    # riga del gap, dove il buco c'è.
    "accetta-bozza": "Accetta la bozza",
    "rifiuta-bozza": "Rifiuta",
    "pubblica": "Pubblica la settimana",
    "sposta-turno": "Sposta il turno",
    "apri-tabellone": "apri tabellone",
}
template.env.globals["ETICHETTE_CHIP"] = ETICHETTE_CHIP

#: widget iniettati nel flusso della sessione corrente (P-F: non si naviga via)
_FLUSSO: dict[str, dict[str, Any]] = {}

#: un callback OAuth senza `state` valido non è «un errore dell'utente»:
#: è un tentativo di far completare a lei un consenso che non ha iniziato.
ERRORE_CONSENSO = "Consenso non valido o scaduto. Rifallo partire da qui."

MESI = (
    "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
    "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre",
)


# --- utilità -----------------------------------------------------------------


def attore(request: Request) -> Attore:
    return sessioni.REGISTRO.attore(request.cookies.get(sessioni.NOME_COOKIE))


def _oggi() -> dt.date:
    return tempo.oggi()


def _settimana_corrente() -> dt.date:
    return kb_turni.lunedi_di(_oggi())


def _settimana_del_ciclo() -> dt.date:
    """«Data la settimana che arriva» (`01` §1): si pianifica la prossima,
    non quella in corso — quella è già pubblicata e si vive, non si riscrive."""
    return _settimana_corrente() + dt.timedelta(days=7)


def _ciclo() -> orchestratore.Ciclo:
    return orchestratore.ciclo(_settimana_del_ciclo())


def _flusso(request: Request) -> dict[str, Any]:
    sid = request.cookies.get(sessioni.NOME_COOKIE) or ""
    return _FLUSSO.setdefault(sid, {"widget": []})


def _pulisci_flusso(request: Request) -> None:
    sid = request.cookies.get(sessioni.NOME_COOKIE) or ""
    _FLUSSO.pop(sid, None)


def _apri_sessione(response: Response, sessione) -> Response:
    response.set_cookie(sessioni.NOME_COOKIE, sessione.id, **sessioni.cookie_kwargs())
    return response


def _verso_home() -> RedirectResponse:
    return RedirectResponse("/home", status_code=303)


# --- landing e login ---------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
def landing(request: Request, errore: str = ""):
    if not attore(request).anonimo():
        return _verso_home()
    return template.TemplateResponse(request, "landing.html", {"errore": errore})


@app.post("/login")
def login(request: Request, uid: str = Form(""), password: str = Form("")):
    try:
        sessione = attivazione.login_password(
            uid, password, request.cookies.get(sessioni.NOME_COOKIE)
        )
    except TroppiTentativi:
        return template.TemplateResponse(
            request, "landing.html", {"errore": "Troppi tentativi. Riprova fra qualche minuto."}, status_code=429
        )
    except AttivazioneNegata:
        return template.TemplateResponse(
            request, "landing.html", {"errore": attivazione.MESSAGGIO_CREDENZIALI}, status_code=401
        )
    return _apri_sessione(_verso_home(), sessione)


@app.get("/login/google")
def login_google_avvio(request: Request):
    from ..auth.oidc import url_login

    state = stato_oauth.REGISTRO.crea("login")
    return RedirectResponse(url_login(str(request.url_for("login_google_ritorno")), state))


@app.get("/login/google/callback", name="login_google_ritorno")
def login_google_ritorno(request: Request, code: str = "", state: str = ""):
    try:
        stato_oauth.REGISTRO.consuma(state, "login")  # CSRF: state a uso singolo
        sessione = attivazione.login_google(
            code, str(request.url_for("login_google_ritorno")), request.cookies.get(sessioni.NOME_COOKIE)
        )
    except stato_oauth.StatoNonValido:
        return template.TemplateResponse(
            request, "landing.html", {"errore": ERRORE_CONSENSO}, status_code=400
        )
    except (AttivazioneNegata, PermissionError):
        return template.TemplateResponse(
            request, "landing.html", {"errore": attivazione.MESSAGGIO_CREDENZIALI}, status_code=401
        )
    return _apri_sessione(_verso_home(), sessione)


@app.get("/password-dimenticata", response_class=HTMLResponse)
def password_dimenticata_form(request: Request):
    return template.TemplateResponse(request, "password.html", {})


@app.post("/password-dimenticata", response_class=HTMLResponse)
def password_dimenticata(request: Request, uid: str = Form("")):
    """Risposta identica per account esistente o no (`07` §2, enumerazione)."""
    try:
        esito = attivazione.password_dimenticata(uid, str(request.base_url).rstrip("/"))
    except TroppiTentativi:
        esito = {"messaggio": "Troppi tentativi. Riprova fra qualche minuto.", "link": ""}
    return template.TemplateResponse(
        request, "password.html", {"messaggio": esito["messaggio"]}
    )


@app.get("/logout")
def logout(request: Request):
    sessioni.REGISTRO.chiudi(request.cookies.get(sessioni.NOME_COOKIE))
    _pulisci_flusso(request)
    r = RedirectResponse("/", status_code=303)
    r.delete_cookie(sessioni.NOME_COOKIE, path="/")
    return r


# --- attivazione -------------------------------------------------------------


@app.get("/attiva", response_class=HTMLResponse)
def attiva(request: Request, t: str = ""):
    try:
        invito = attivazione.apri_invito(t)
    except (AttivazioneNegata, TroppiTentativi):
        return template.TemplateResponse(
            request,
            "attiva.html",
            {"valido": False, "messaggio": attivazione.MESSAGGIO_INVITO_NON_VALIDO},
            status_code=400,
        )
    persona = kb_persone.leggi(invito.persona)
    return template.TemplateResponse(
        request,
        "attiva.html",
        {"valido": True, "token": t, "nome": persona.nome if persona else "", "email": invito.email},
    )


@app.post("/attiva")
def attiva_password(
    request: Request,
    t: str = Form(""),
    uid: str = Form(""),
    password: str = Form(""),
    password2: str = Form(""),
):
    def errore(messaggio: str, stato: int = 400):
        try:
            invito = attivazione.apri_invito(t)
        except Exception:
            return template.TemplateResponse(
                request,
                "attiva.html",
                {"valido": False, "messaggio": attivazione.MESSAGGIO_INVITO_NON_VALIDO},
                status_code=400,
            )
        persona = kb_persone.leggi(invito.persona)
        return template.TemplateResponse(
            request,
            "attiva.html",
            {
                "valido": True,
                "token": t,
                "nome": persona.nome if persona else "",
                "email": invito.email,
                "errore": messaggio,
            },
            status_code=stato,
        )

    if password != password2:
        return errore("Le due password non coincidono.")
    try:
        sessione = attivazione.crea_account_password(t, uid, password)
    except AttivazioneNegata as e:
        return errore(str(e))
    except Exception as e:  # password debole
        return errore(f"Password non accettata: {e}")
    return _apri_sessione(_verso_home(), sessione)


@app.get("/attiva/google")
def attiva_google_avvio(request: Request, t: str = ""):
    """Il token d'invito resta **server-side**: nel `state` va solo un opaco."""
    from ..auth.oidc import url_login

    state = stato_oauth.REGISTRO.crea("attivazione", dati=t)
    return RedirectResponse(url_login(str(request.url_for("attiva_google_ritorno")), state))


@app.get("/attiva/google/callback", name="attiva_google_ritorno")
def attiva_google_ritorno(request: Request, code: str = "", state: str = ""):
    try:
        stato = stato_oauth.REGISTRO.consuma(state, "attivazione")
        sessione = attivazione.crea_account_google(
            stato.dati, code, str(request.url_for("attiva_google_ritorno"))
        )
    except stato_oauth.StatoNonValido:
        return template.TemplateResponse(
            request, "attiva.html", {"valido": False, "messaggio": ERRORE_CONSENSO}, status_code=400
        )
    except (AttivazioneNegata, PermissionError) as e:
        return template.TemplateResponse(
            request,
            "attiva.html",
            {"valido": False, "messaggio": str(e)},
            status_code=400,
        )
    return _apri_sessione(_verso_home(), sessione)


# --- home --------------------------------------------------------------------


@app.get("/home", response_class=HTMLResponse)
def home(request: Request):
    return _render_home(request)


def _render_home(request: Request, status_code: int = 200):
    """La home è l'unica casa: ci si torna anche dagli errori (Book 05).

    Un input rifiutato è un 400 **su questa pagina**, non un'altra schermata e
    non un 500: chi ha sbagliato bersaglio deve vedere di nuovo i suoi turni,
    la bozza e il composer, con una riga che dice cosa manca.
    """
    a = attore(request)
    if a.anonimo():
        return RedirectResponse("/", status_code=303)
    persona = kb_persone.leggi(a.slug)
    ciclo = _ciclo()
    flusso = _flusso(request)

    # «il negozio sa che…»: retrieval, non spam proattivo (`02` §4.5)
    from ..kb import secondo as kb_secondo

    note = kb_secondo.retrieval(
        [MESI[_oggi().month - 1], _settimana_corrente().isoformat()], limite=3
    )

    # Una bozza in attesa è **stato del ciclo**, non un messaggio di chat: la
    # vede il manager anche se l'ha chiesta ieri, da un altro dispositivo o da
    # un job. Il flusso della sessione resta per il copilota.
    widget = list(flusso.get("widget", []))
    if a.manager and ciclo.stato == "attesa_umano" and ciclo.bozza is not None:
        if not any(w.get("tipo") == "proposal-pack" for w in widget):
            widget = _widget_bozza(ciclo, a) + widget

    return template.TemplateResponse(
        request,
        "home.html",
        {
            "secondo": vista.secondo_note(note) if note else None,
            "persona": persona,
            # slot fisso: la **mia** settimana in corso, senza overlay della
            # bozza della settimana dopo (Book 02 «shell vs generative»).
            # L'overlay vive nel pack e sui candidati, dove è il soggetto.
            "turni": vista.person_shifts(a.slug, a, oggi=_oggi()),
            "saldi": vista.person_balances(a.slug, a),
            "ciclo": ciclo.stato_visibile() if a.manager else None,
            "attivatore": a.attivatore,
            "widget": widget,
            # l'esito di un tap si monta **sotto la riga tappata**: serve
            # sapere quale riga era (Book 02 Loop A2)
            "candidati": flusso.get("candidati_gap"),
            "gap_scelto": flusso.get("gap_scelto"),
            "sblocco": flusso.get("sblocco"),
            "blocco_scelto": flusso.get("blocco_scelto"),
            "conferma": flusso.get("conferma"),
            "copilota_spento": flusso.get("copilota_spento", False),
        },
        status_code=status_code,
    )


@app.post("/copilota")
def copilota(request: Request, testo: str = Form("")):
    a = attore(request)
    if a.anonimo():
        return RedirectResponse("/", status_code=303)
    flusso = _flusso(request)
    contesto = ctx.carica(_settimana_del_ciclo())
    try:
        risposta = agente_copilot.AGENTE.rispondi(testo, a, contesto)
        flusso["widget"] = [risposta.turno, *risposta.widget]
        # solo un guasto spegne il composer: senza modello si continua a scrivere
        flusso["copilota_spento"] = risposta.spento
    except LLMGiu:
        # spento in modo onesto: i widget deterministici restano a schermo
        flusso["widget"] = [agente_copilot.spento()]
        flusso["copilota_spento"] = True
    except Negato:
        flusso["widget"] = [vista.copilot_turn(agente_copilot.RIFIUTO_ALTRUI, [])]
    return _verso_home()


# --- chip --------------------------------------------------------------------


@app.post("/chip/{nome}", response_class=HTMLResponse)
async def chip(request: Request, nome: str):
    a = attore(request)
    if a.anonimo():
        return RedirectResponse("/", status_code=303)
    dati = dict(await request.form())
    conferma = str(dati.get("conferma", ""))
    ciclo = _ciclo()
    flusso = _flusso(request)

    # Annulla, una volta sola per tutte le chip: si butta la conferma pendente
    # e si torna a casa. Rirenderizzare la preview era il modo per restare
    # incastrati sulla pagina che si stava chiudendo (Book 02, «cosa non
    # succede più»).
    if conferma == "0":
        flusso.pop("conferma", None)
        return _verso_home()

    try:
        if nome == "consulta":
            # Con un payload è un atto deterministico, senza prompt di mezzo:
            # «chi può coprirlo» su un buco, «come lo sciolgo» su un blocco.
            # Senza payload resta il no-op di sempre.
            if dati.get("persona") and str(dati.get("motivo") or "") == "blocco":
                esigi_manager(a, "chip/consulta")
                carte, violazione, mosse, problema = _celle_del_blocco(dati, ciclo, a)
                if problema:
                    flusso["widget"] = [vista.copilot_turn(problema, [])]
                    return _render_home(request, status_code=400)
                flusso["sblocco"] = carte
                flusso["blocco_scelto"] = violazione
                audit.accesso(
                    a.slug,
                    f"blocco_consultato/{violazione['persona']}/{violazione['regola']}",
                    f"celle={len(mosse)}",
                )
                return _verso_home()

            if dati.get("data") and dati.get("fascia") and dati.get("reparto"):
                esigi_manager(a, "chip/consulta")
                candidati, problema = _candidati_del_gap(dati, ciclo, a)
                if problema:
                    flusso["widget"] = [vista.copilot_turn(problema, [])]
                    return _render_home(request, status_code=400)
                flusso["candidati_gap"] = candidati
                flusso["gap_scelto"] = {
                    "data": str(dati["data"]),
                    "fascia": str(dati["fascia"]),
                    "reparto": str(dati["reparto"]),
                }
                audit.accesso(
                    a.slug,
                    f"gap_consultato/{dati['data']}/{dati['fascia']}/{dati['reparto']}",
                    f"candidati={sum(1 for c in candidati if c['tipo'] == 'person-shifts')}",
                )
            return _verso_home()

        if nome == "apri-tabellone":
            return RedirectResponse("/tabellone", status_code=303)

        if nome == "apri-scheda":
            slug = str(dati.get("persona") or a.slug)
            return RedirectResponse(f"/scheda/{slug}", status_code=303)

        if nome == "genera-bozza":
            ciclo.genera_bozza(a)
            _scarta_esiti(flusso)
            flusso["widget"] = _widget_bozza(ciclo, a)
            return _verso_home()

        if nome == "scegli-variante":
            ciclo.scegli_variante(a, int(dati.get("indice", 0)))
            _scarta_esiti(flusso)
            flusso["widget"] = _widget_bozza(ciclo, a)
            return _verso_home()

        if nome == "accetta-bozza":
            if conferma != "1":
                _apri_conferma(
                    flusso,
                    domanda="Accetto questa bozza?",
                    azione="/chip/accetta-bozza",
                    toccati=_toccati(ciclo),
                    avvisi=_avvisi(ciclo),
                    blocco=bool(ciclo.bozza and not ciclo.bozza.pubblicabile),
                    conferma_testo="Accetta",
                )
                return _verso_home()
            flusso.pop("conferma", None)
            ciclo.accetta(a)
            flusso["widget"] = _widget_bozza(ciclo, a)
            return _verso_home()

        if nome == "rifiuta-bozza":
            if conferma != "1":
                _apri_conferma(
                    flusso,
                    domanda="Rifiuto la bozza? Il negozio impara dal no.",
                    azione="/chip/rifiuta-bozza",
                    toccati=_toccati(ciclo),
                    conferma_testo="Rifiuta",
                )
                return _verso_home()
            flusso.pop("conferma", None)
            ciclo.rifiuta(a, str(dati.get("motivo", "")))
            _scarta_esiti(flusso)
            flusso["widget"] = []
            return _verso_home()

        if nome == "pubblica":
            if conferma != "1":
                _apri_conferma(
                    flusso,
                    domanda="Pubblico la settimana?",
                    azione="/chip/pubblica",
                    toccati=_toccati(ciclo),
                    avvisi=_avvisi(ciclo),
                    conferma_testo="Pubblica",
                )
                return _verso_home()
            flusso.pop("conferma", None)
            ciclo.pubblica(a)
            flusso["widget"] = []
            return _verso_home()

        if nome == "sposta-turno":
            esigi_manager(a, "chip/sposta-turno")
            bersaglio, problema = _bersaglio_sposta(dati, ciclo)
            if problema:
                # Manca (o non si legge) il bersaglio: 400 sulla home con una
                # riga che lo dice. Prima qui si passava `None` a
                # `date.fromisoformat` e il server cadeva con un 500 (Book 07).
                flusso["widget"] = [vista.copilot_turn(problema, [])]
                flusso.pop("conferma", None)
                return _render_home(request, status_code=400)

            if conferma != "1":
                scheda = kb_persone.leggi(bersaglio["persona"])
                nome_persona = scheda.nome if scheda else bersaglio["persona"]
                _apri_conferma(
                    flusso,
                    # **prima → dopo**, non solo la destinazione: `imposta`
                    # sostituisce la cella del giorno, non aggiunge un pezzo.
                    # Coprire pizze con chi è già in turno apre un altro buco,
                    # e va detto prima di confermare (Book 08, «Layer 2»).
                    domanda=(
                        f"{nome_persona} {_giorno_esteso(bersaglio['data'])}: "
                        f"{_cella_attuale(ciclo, bersaglio)} → {bersaglio['fascia']}. "
                        "Sostituisco la cella di quel giorno?"
                    ),
                    azione="/chip/sposta-turno",
                    campi=bersaglio,
                    toccati=_toccati(ciclo),
                    avvisi=_avvisi(ciclo),
                    blocco=bool(ciclo.bozza and not ciclo.bozza.pubblicabile),
                    conferma_testo="Sposta",
                )
                return _verso_home()

            ciclo.sposta_turno(
                a,
                persona=bersaglio["persona"],
                data=dt.date.fromisoformat(bersaglio["data"]),
                fascia=bersaglio["fascia"],
            )
            flusso.pop("conferma", None)
            _scarta_esiti(flusso)  # ricalcolati al prossimo tap
            flusso["widget"] = _widget_bozza(ciclo, a)
            return _verso_home()

        if nome == "salva-preferenza":
            slug = str(dati.get("persona") or a.slug)
            if conferma in ("", "0"):
                flusso["widget"] = []
                return _verso_home()
            from ..security.authz import esigi_scrittura_scheda

            esigi_scrittura_scheda(a, slug)
            kb_persone.salva_preferenza(
                slug,
                Preferenza(
                    vincolo=str(dati.get("vincolo", "")),
                    storia="" if conferma == "solo-vincolo" else str(dati.get("storia", "")),
                    origine="confermata",
                    data=_oggi().isoformat(),
                ),
            )
            audit.decisione("-", "preferenza-salvata", a.slug)
            flusso["widget"] = []
            return _verso_home()

        if nome == "collega-google":
            slug = str(dati.get("persona") or a.slug)
            return RedirectResponse(f"/calendario/collega?persona={slug}", status_code=303)

        if nome == "scollega-google":
            slug = str(dati.get("persona") or a.slug)
            if conferma != "1":
                _apri_conferma(
                    flusso,
                    domanda="Scollego il calendario? Cancello gli eventi che ho creato io.",
                    azione="/chip/scollega-google",
                    campi={"persona": slug},
                    conferma_testo="Scollega",
                )
                return _verso_home()
            flusso.pop("conferma", None)
            scollega(a, slug)
            return _verso_home()

        if nome in ("aggiorna-saldi", "riprova"):
            from .. import saldi as porta

            adattatore = porta.porta()
            if hasattr(adattatore, "invalida"):
                adattatore.invalida(a.slug)
            if nome == "riprova":
                sync_calendario.dopo_pubblicazione_persona(a.slug)
            return _verso_home()

    except Negato:
        return JSONResponse({"errore": "non autorizzato"}, status_code=403)
    except orchestratore.CicloBloccato as e:
        flusso["widget"] = [vista.copilot_turn(str(e), [])]
        return _verso_home()

    return JSONResponse({"errore": f"chip sconosciuta: {nome}"}, status_code=400)


def _widget_bozza(ciclo: orchestratore.Ciclo, a: Attore) -> list[dict]:
    if ciclo.bozza is None:
        return []
    fuori = [vista.proposal_pack(ciclo.bozza, a, oggi=ciclo.settimana)]
    if ciclo.bozza.gap:
        fuori.append(vista.coverage_gap(ciclo.bozza.gap))
    if ciclo.bozza.violazioni or ciclo.bozza.segnalazioni:
        fuori.append(vista.compliance_block(ciclo.bozza.violazioni, ciclo.bozza.segnalazioni))
    fuori.append(vista.rationale(ciclo.bozza.rationale, ciclo.bozza.fonti))
    return fuori


GIORNI_ESTESI = ("lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica")


def _giorno_esteso(iso: str) -> str:
    data = dt.date.fromisoformat(iso)
    return f"{GIORNI_ESTESI[data.weekday()]} {data.day:02d}/{data.month:02d}"


def _candidati_del_gap(
    dati: dict, ciclo: orchestratore.Ciclo, a: Attore
) -> tuple[list[dict], str]:
    """Valida il buco e monta i candidati. Ricalcolati **a ogni tap**.

    Non si cachano sul `Gap`: dopo uno spostamento sarebbero già vecchi, e una
    lista di persone vecchia è peggio di nessuna lista (Book 05).
    """
    from ..agents.forecast import FASCE  # noqa: F401  (usata sotto)

    if ciclo.stato != "attesa_umano" or ciclo.bozza is None:
        return [], "Non c'è una bozza aperta: nessun buco da coprire."
    fascia = str(dati.get("fascia") or "")
    reparto = str(dati.get("reparto") or "")
    if fascia not in [n for n, _, _ in FASCE]:
        return [], f"«{fascia}» non è una fascia del punto vendita."
    try:
        data = dt.date.fromisoformat(str(dati.get("data")))
    except ValueError:
        return [], "Data del buco non valida."
    if data not in ciclo.bozza.piano.giorni:
        return [], "Quel giorno è fuori dalla settimana in bozza."

    from ..agents.scheduling import candidati_per_gap

    liberi = candidati_per_gap(
        ciclo.bozza.piano, data, fascia, reparto, kb_persone.per_slug()
    )
    dalle, alle = next((d, al) for n, d, al in FASCE if n == fascia)
    orario = f"{dalle.hour}-{alle.hour}"
    return vista.candidati_gap(ciclo.bozza, a, data, fascia, reparto, liberi, orario), ""


def _celle_del_blocco(
    dati: dict, ciclo: orchestratore.Ciclo, a: Attore
) -> tuple[list[dict], dict, list[dict], str]:
    """Valida la violazione tappata e monta le celle che la sciolgono.

    Solo le **violazioni** aprono il gesto. Una segnalazione («41h su contratto
    40h») non toglie la chip `pubblica`: darle un bottone «come lo sciolgo»
    direbbe che finché non la tocchi non chiudi la settimana, e non è vero
    (Book 02 A2, spec `02` Loop A2).
    """
    if ciclo.stato != "attesa_umano" or ciclo.bozza is None:
        return [], {}, [], "Non c'è una bozza aperta: nessun blocco da sciogliere."

    persona = str(dati.get("persona") or "").strip()
    regola = str(dati.get("regola") or "").strip()
    quando = str(dati.get("data") or "").strip()
    trovate = [
        v
        for v in ciclo.bozza.violazioni
        if v["persona"] == persona
        and (not regola or v["regola"] == regola)
        and (not quando or str(v.get("data") or "") == quando)
    ]
    if not trovate:
        return [], {}, [], (
            f"Non c'è (più) un blocco su «{persona}»: Compliance ha già rigirato la bozza."
        )
    violazione = trovate[0]

    from ..agents.compliance import celle_che_sciolgono

    mosse = celle_che_sciolgono(ciclo.bozza.piano, violazione, kb_persone.per_slug())
    return vista.celle_blocco(ciclo.bozza, a, violazione, mosse), violazione, mosse, ""


def _cella_attuale(ciclo: orchestratore.Ciclo, bersaglio: dict) -> str:
    """Cosa c'è **adesso** in quella cella: il «prima» della preview."""
    if ciclo.bozza is None:
        return "—"
    turno = ciclo.bozza.piano.turno(
        bersaglio["persona"], dt.date.fromisoformat(bersaglio["data"])
    )
    return (turno.etichetta().replace("–", "-") if turno else "") or "—"


def _scarta_esiti(flusso: dict[str, Any]) -> None:
    """L'esito di un tap vale per **quella** bozza.

    Dopo uno spostamento (o una bozza nuova) candidati e celle di sblocco sono
    già vecchi, e una lista vecchia è peggio di nessuna lista: si ricalcola al
    prossimo tap, che costa millisecondi.
    """
    for chiave in ("candidati_gap", "gap_scelto", "sblocco", "blocco_scelto"):
        flusso.pop(chiave, None)


def _bersaglio_sposta(dati: dict, ciclo: orchestratore.Ciclo) -> tuple[dict, str]:
    """Valida persona, data e fascia **prima** di toccare il ciclo (Book 05 §validazione).

    Ritorna `(bersaglio, "")` oppure `({}, motivo)`. Il motivo è testo per la
    persona, non un traceback: è quello che finisce a schermo.
    """
    if ciclo.stato != "attesa_umano" or ciclo.bozza is None:
        return {}, "Non c'è una bozza in attesa da modificare."

    persona = str(dati.get("persona") or "").strip()
    grezza = str(dati.get("data") or "").strip()
    fascia = str(dati.get("fascia") or "").strip()
    if not (persona and grezza and fascia):
        return {}, "Manca il bersaglio: serve la persona, il giorno e la fascia."
    if not kb_persone.esiste(persona):
        return {}, f"«{persona}» non ha una scheda in kb/persone."
    try:
        data = dt.date.fromisoformat(grezza)
    except ValueError:
        return {}, f"«{grezza}» non è una data valida."
    if data not in ciclo.bozza.piano.giorni:
        return {}, f"{grezza} è fuori dalla settimana in bozza."

    spezzoni, badge, _ = parse_cella(fascia)
    if not spezzoni and not badge:
        return {}, f"«{fascia}» non è una fascia che so leggere (es. 7-12, 16-20, R)."

    return {"persona": persona, "data": data.isoformat(), "fascia": fascia}, ""


#: quante persone si elencano per esteso nella preview prima di riassumere
MAX_TOCCATI = 8


def _toccati(ciclo: orchestratore.Ciclo) -> list[dict]:
    """«Chi non è nella stanza» (`05` §4.2): la preview dice chi cambia.

    Una lista di trenta righe non è una preview, è di nuovo il tabellone: si
    mostrano i primi e si dice **quante** persone restano, senza nasconderle.
    """
    if ciclo.bozza is None:
        return []
    pubblicato = kb_turni.piano_di_riferimento(ciclo.settimana)
    toccate = ciclo.bozza.persone_toccate(pubblicato)
    fuori = []
    for slug in toccate[:MAX_TOCCATI]:
        righe = ciclo.bozza.diff(pubblicato, slug)
        cosa = "; ".join(
            f"{r['giorno']} {r['prima'] or '—'} → {r['dopo'] or '—'}" for r in righe[:3]
        )
        if len(righe) > 3:
            cosa += f" · e altri {len(righe) - 3} giorni"
        fuori.append({"persona": slug, "cosa": cosa})
    resto = len(toccate) - MAX_TOCCATI
    if resto > 0:
        fuori.append({"persona": f"e altre {resto} persone", "cosa": "cambi minori"})
    return fuori


def _avvisi(ciclo: orchestratore.Ciclo) -> list[str]:
    if ciclo.bozza is None:
        return []
    return [f"{v['persona']}: {v['dettaglio']}" for v in ciclo.bozza.segnalazioni[:8]]


def _apri_conferma(
    flusso: dict[str, Any],
    domanda: str,
    azione: str,
    toccati: list[dict] | None = None,
    avvisi: list[str] | None = None,
    campi: dict[str, str] | None = None,
    conferma_testo: str = "",
    blocco: bool = False,
) -> None:
    """Mette una conferma **in attesa sulla home**, non su un'altra pagina.

    P-F: un atto inietta il prossimo passo nello stesso flusso. Mandare il
    manager su `/chip/accetta-bozza` come destinazione lo sbalzava fuori casa,
    e l'Annulla non aveva un posto dove tornare (Book 02, 08).
    """
    flusso["conferma"] = {
        "domanda": domanda,
        "azione": azione,
        "toccati": toccati or [],
        "avvisi": avvisi or [],
        "campi": campi or {},
        "conferma_testo": conferma_testo,
        "blocco": blocco,
    }


# --- tabellone ---------------------------------------------------------------


@app.get("/scheda/{slug}", response_class=HTMLResponse)
def scheda(request: Request, slug: str):
    """Chip `apri-scheda`: la md **così com'è** (`02` §4.2). Nessuna generazione.

    Il manager vede la forma operativa; la storia di una preferenza resta alla
    persona (`05` §4.2), quindi la si oscura per chi non è lei.
    """
    a = attore(request)
    try:
        from ..security.authz import esigi_scheda

        esigi_scheda(a, slug)
    except Negato:
        return JSONResponse({"errore": "403"}, status_code=403)
    persona = kb_persone.leggi(slug)
    if persona is None:
        return JSONResponse({"errore": "nessuna scheda"}, status_code=404)
    testo = kb_persone.percorso(slug).read_text(encoding="utf-8")
    if a.slug != slug:
        for pref in persona.preferenze:
            if pref.storia:
                testo = testo.replace(f" — storia: «{pref.storia}»", "")
                testo = testo.replace(pref.storia, "…")
    return template.TemplateResponse(
        request,
        "scheda.html",
        {
            "persona": persona,
            "testo": testo,
            "path": f"kb/persone/{slug}.md",
            "mia": a.slug == slug,
        },
    )


@app.get("/tabellone", response_class=HTMLResponse)
def tabellone(request: Request, settimana: str = ""):
    a = attore(request)
    if a.anonimo():
        return RedirectResponse("/", status_code=303)
    if not a.manager:
        return JSONResponse({"errore": "il tabellone è del manager"}, status_code=403)
    # Se il manager apre il foglio, è quello che sta pianificando — non l'ultima
    # settimana pubblicata. Il fallback al 29/06 mentre il ciclo è sul 06/07
    # faceva sembrare vecchia una vista che era solo puntata male (Book 05, 07).
    ciclo = _ciclo()
    giorno = dt.date.fromisoformat(settimana) if settimana else ciclo.settimana
    bozza = ciclo.bozza if (not settimana and ciclo.bozza) else None
    piano = bozza.piano if bozza else kb_turni.leggi(giorno)
    return template.TemplateResponse(
        request,
        "tabellone.html",
        {
            "griglia": vista.week_grid(piano, bozza=bozza) if piano else None,
            "settimana": giorno.isoformat(),
            "in_bozza": bool(bozza),
        },
    )


# --- attivatore --------------------------------------------------------------


@app.get("/attivatore", response_class=HTMLResponse)
def lista_attivazione(request: Request, messaggio: str = ""):
    a = attore(request)
    try:
        persone = attivazione.non_ancora_entrate(a)
    except Negato:
        return JSONResponse({"errore": "non autorizzato"}, status_code=403)
    return template.TemplateResponse(
        request, "attivatore.html", {"persone": persone, "messaggio": messaggio}
    )


@app.post("/attivatore", response_class=HTMLResponse)
def azione_attivazione(
    request: Request, persona: str = Form(""), email: str = Form(""), azione: str = Form("")
):
    a = attore(request)
    base = str(request.base_url).rstrip("/")
    messaggio = link = qr = ""
    try:
        if azione == "invia-attivazione":
            esito = attivazione.invia_attivazione(a, persona, email, base)
            link = esito["link"]
            messaggio = f"Invito inviato a {esito['email'] or persona}."
        elif azione == "mostra-qr":
            esito = attivazione.mostra_qr(a, persona, base, email)
            link, qr = esito["link"], esito["qr_svg"]
            messaggio = f"QR per {persona}: inquadralo dal suo telefono."
        elif azione == "revoca-invito":
            n = attivazione.revoca_invito(a, persona)
            messaggio = f"{n} invito/i revocato/i."
    except Negato:
        return JSONResponse({"errore": "non autorizzato"}, status_code=403)
    except AttivazioneNegata as e:
        messaggio = str(e)
    return template.TemplateResponse(
        request,
        "attivatore.html",
        {
            "persone": attivazione.non_ancora_entrate(a),
            "messaggio": messaggio,
            "link": link,
            "qr": qr,
        },
    )


# --- calendario (`03`) -------------------------------------------------------


@app.get("/calendario/collega")
def calendario_collega(request: Request, persona: str = ""):
    a = attore(request)
    slug = persona or a.slug
    if a.anonimo() or a.slug != slug:
        return JSONResponse({"errore": "solo la persona collega il proprio calendario"}, status_code=403)
    from ..calendario import url_consenso

    state = stato_oauth.REGISTRO.crea(
        "calendario", dati=slug, sessione=request.cookies.get(sessioni.NOME_COOKIE) or ""
    )
    return RedirectResponse(
        url_consenso(slug, str(request.url_for("calendario_ritorno")), state)
    )


@app.get("/calendario/callback", name="calendario_ritorno")
def calendario_ritorno(request: Request, code: str = "", state: str = ""):
    a = attore(request)
    try:
        # legato allo scopo **e** alla sessione che ha avviato il consenso
        stato = stato_oauth.REGISTRO.consuma(
            state, "calendario", request.cookies.get(sessioni.NOME_COOKIE) or ""
        )
    except stato_oauth.StatoNonValido:
        return JSONResponse({"errore": ERRORE_CONSENSO}, status_code=400)
    if a.anonimo() or a.slug != stato.dati:
        return JSONResponse({"errore": "consenso non riferibile a questa sessione"}, status_code=403)
    persona = kb_persone.leggi(a.slug)
    collega(
        a,
        a.slug,
        access_token=code or "token-finto",
        refresh_token=f"refresh-{a.slug}",
        email=(persona.email if persona else "") or f"{a.slug}@example.com",
    )
    return _verso_home()


# --- API JSON (authz esplicita) ---------------------------------------------


@app.get("/api/turni/{slug}")
def api_turni(request: Request, slug: str):
    a = attore(request)
    try:
        return vista.person_shifts(slug, a, oggi=_oggi())
    except Negato:
        return JSONResponse({"errore": "403"}, status_code=403)


@app.get("/api/saldi/{slug}")
def api_saldi(request: Request, slug: str):
    a = attore(request)
    try:
        return vista.person_balances(slug, a)
    except Negato:
        return JSONResponse({"errore": "403"}, status_code=403)


@app.get("/api/stato-ciclo")
def api_stato_ciclo(request: Request):
    a = attore(request)
    if a.anonimo():
        return JSONResponse({"errore": "403"}, status_code=403)
    return _ciclo().stato_visibile()


@app.post("/api/copilota")
async def api_copilota(request: Request):
    a = attore(request)
    if a.anonimo():
        return JSONResponse({"errore": "403"}, status_code=403)
    corpo = await request.json()
    contesto = ctx.carica(_settimana_del_ciclo())
    try:
        risposta = agente_copilot.AGENTE.rispondi(str(corpo.get("testo", "")), a, contesto)
    except LLMGiu:
        return {"turno": agente_copilot.spento(), "widget": [], "copilota": "giu"}
    except Negato:
        return {"turno": vista.copilot_turn(agente_copilot.RIFIUTO_ALTRUI, []), "widget": []}
    return risposta.come_dict()

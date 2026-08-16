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
from ..auth import attivazione, sessioni
from ..auth.attivazione import AttivazioneNegata, TroppiTentativi
from ..calendario import collega, scollega
from ..calendario import sync as sync_calendario
from ..domain.modelli import Preferenza
from ..kb import persone as kb_persone
from ..kb import turni as kb_turni
from ..orchestrator import ciclo as orchestratore
from ..orchestrator import contesto as ctx
from ..security import audit
from ..security.authz import Attore, Negato

BASE = Path(__file__).parent
app = FastAPI(title="TIME MACHINE", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
template = Jinja2Templates(directory=str(BASE / "templates"))

#: widget iniettati nel flusso della sessione corrente (P-F: non si naviga via)
_FLUSSO: dict[str, dict[str, Any]] = {}

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

    return RedirectResponse(url_login(str(request.url_for("login_google_ritorno")), "login"))


@app.get("/login/google/callback", name="login_google_ritorno")
def login_google_ritorno(request: Request, code: str = ""):
    try:
        sessione = attivazione.login_google(
            code, str(request.url_for("login_google_ritorno")), request.cookies.get(sessioni.NOME_COOKIE)
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
    from ..auth.oidc import url_login

    return RedirectResponse(url_login(str(request.url_for("attiva_google_ritorno")), t))


@app.get("/attiva/google/callback", name="attiva_google_ritorno")
def attiva_google_ritorno(request: Request, code: str = "", state: str = ""):
    try:
        sessione = attivazione.crea_account_google(
            state, code, str(request.url_for("attiva_google_ritorno"))
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
    return template.TemplateResponse(
        request,
        "home.html",
        {
            "secondo": vista.secondo_note(note) if note else None,
            "persona": persona,
            "turni": vista.person_shifts(
                a.slug, a, oggi=_oggi(), bozza=ciclo.bozza if a.manager else None
            ),
            "saldi": vista.person_balances(a.slug, a),
            "ciclo": ciclo.stato_visibile() if a.manager else None,
            "attivatore": a.attivatore,
            "widget": flusso.get("widget", []),
            "copilota_spento": flusso.get("copilota_spento", False),
        },
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
        flusso["copilota_spento"] = risposta.degradato
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

    try:
        if nome == "consulta":
            return _verso_home()

        if nome == "apri-tabellone":
            return RedirectResponse("/tabellone", status_code=303)

        if nome == "apri-scheda":
            slug = str(dati.get("persona") or a.slug)
            return RedirectResponse(f"/scheda/{slug}", status_code=303)

        if nome == "genera-bozza":
            ciclo.genera_bozza(a)
            flusso["widget"] = _widget_bozza(ciclo, a)
            return _verso_home()

        if nome == "scegli-variante":
            ciclo.scegli_variante(a, int(dati.get("indice", 0)))
            flusso["widget"] = _widget_bozza(ciclo, a)
            return _verso_home()

        if nome == "accetta-bozza":
            if conferma != "1":
                return _conferma(
                    request,
                    domanda="Accetto questa bozza?",
                    azione="/chip/accetta-bozza",
                    toccati=_toccati(ciclo),
                    avvisi=_avvisi(ciclo),
                    widget=_widget_bozza(ciclo, a),
                )
            ciclo.accetta(a)
            flusso["widget"] = _widget_bozza(ciclo, a)
            return _verso_home()

        if nome == "rifiuta-bozza":
            if conferma != "1":
                return _conferma(
                    request,
                    domanda="Rifiuto la bozza? Il negozio impara dal no.",
                    azione="/chip/rifiuta-bozza",
                    toccati=_toccati(ciclo),
                    conferma_testo="Rifiuta",
                )
            ciclo.rifiuta(a, str(dati.get("motivo", "")))
            flusso["widget"] = []
            return _verso_home()

        if nome == "pubblica":
            if conferma != "1":
                return _conferma(
                    request,
                    domanda="Pubblico la settimana?",
                    azione="/chip/pubblica",
                    toccati=_toccati(ciclo),
                    avvisi=_avvisi(ciclo),
                    conferma_testo="Pubblica",
                )
            ciclo.pubblica(a)
            flusso["widget"] = []
            return _verso_home()

        if nome == "sposta-turno":
            ciclo.sposta_turno(
                a,
                persona=str(dati.get("persona", "")),
                data=dt.date.fromisoformat(str(dati.get("data"))),
                fascia=str(dati.get("fascia", "")),
            )
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
                return _conferma(
                    request,
                    domanda="Scollego il calendario? Cancello gli eventi che ho creato io.",
                    azione="/chip/scollega-google",
                    campi={"persona": slug},
                    conferma_testo="Scollega",
                )
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


def _toccati(ciclo: orchestratore.Ciclo) -> list[dict]:
    """«Chi non è nella stanza» (`05` §4.2): la preview dice chi cambia."""
    if ciclo.bozza is None:
        return []
    pubblicato = kb_turni.leggi(ciclo.settimana)
    fuori = []
    for slug in ciclo.bozza.persone_toccate(pubblicato):
        righe = ciclo.bozza.diff(pubblicato, slug)
        fuori.append(
            {
                "persona": slug,
                "cosa": "; ".join(f"{r['giorno']} {r['prima'] or '—'} → {r['dopo'] or '—'}" for r in righe[:4]),
            }
        )
    return fuori


def _avvisi(ciclo: orchestratore.Ciclo) -> list[str]:
    if ciclo.bozza is None:
        return []
    return [f"{v['persona']}: {v['dettaglio']}" for v in ciclo.bozza.segnalazioni[:8]]


def _conferma(
    request: Request,
    domanda: str,
    azione: str,
    toccati: list[dict] | None = None,
    avvisi: list[str] | None = None,
    campi: dict[str, str] | None = None,
    widget: list[dict] | None = None,
    conferma_testo: str = "",
) -> HTMLResponse:
    return template.TemplateResponse(
        request,
        "conferma.html",
        {
            "domanda": domanda,
            "azione": azione,
            "toccati": toccati or [],
            "avvisi": avvisi or [],
            "campi": campi or {},
            "widget": widget or [],
            "conferma_testo": conferma_testo,
        },
    )


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
    giorno = dt.date.fromisoformat(settimana) if settimana else _settimana_corrente()
    piano = kb_turni.leggi(giorno) or kb_turni.ultimo_pubblicato(giorno)
    return template.TemplateResponse(
        request,
        "tabellone.html",
        {"griglia": vista.week_grid(piano) if piano else None},
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

    return RedirectResponse(
        url_consenso(slug, str(request.url_for("calendario_ritorno")), slug)
    )


@app.get("/calendario/callback", name="calendario_ritorno")
def calendario_ritorno(request: Request, code: str = "", state: str = ""):
    a = attore(request)
    if a.anonimo() or a.slug != state:
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

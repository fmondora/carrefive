# 07 — Landing, attivazione e login

Specifica di **costruzione**. Superficie pubblica: una persona entra. Non si iscrive da sola. **Emilio** la attiva (email o QR/link). Poi lei completa con **uid/password** oppure **account Google**.

Zero AI su questa superficie. Identità ≠ calendario Google (`03`).

> **Lenti.** Lead `[AIUxer]` sulla landing (fresco, `06`). `[AIEngineer]` su token, password, OIDC. `[05]` ha veto su leak e enumerazione.

---

## 1. Problema & job-to-be-done

Anna esiste già in `kb/persone/`. Non ha ancora un modo di *entrare*. Il foglio del negozio non è un signup aperto: Emilio decide chi è del PV.

**Job.**

1. Emilio attiva Anna sull'email che usa, o le mostra un QR / le manda un link.
2. Anna apre il link (o inquadra il QR), sceglie come entrare: uid+password **oppure** Google.
3. Da quel momento la landing è login. Dopo il login: home `02` (`person-shifts` + `person-balances`).

Chiunque dal web vede la landing. Non crea un account. Non vede turni.

---

## 2. Metrica d'esito

- **Attivazione chiusa:** 0 account nati senza token valido di Emilio (canary L4).
- **Tempo Anna:** dal tap sul link alla home < 2 min (password o Google).
- **Canale:** ≥ 80% delle persone attivate nel pilota fanno il primo login entro 7 giorni (email o QR).
- **Separazione Google:** un login Google **non** scrive eventi sul calendario. `collega-google` (`03`) resta un secondo consenso.
- **Enumerazione:** risposta identica se l'email è sconosciuta o già attiva (login e «reinvia»).

---

## 3. Vincoli

- Niente self-signup. La persona è già una scheda kb; l'attivazione **lega** uno slug a un'identità.
- Un'identità ↔ una persona del PV. Stesso Google / stesso uid non si attacca a due schede.
- Password: hash (argon2id o bcrypt cost ≥ 12), mai in `kb/`, mai in log. Reset solo via nuovo link di Emilio o «password dimenticata» sull'email *già* attivata.
- Token di attivazione: un uso, scadenza 7 giorni, bound a `persona` + `email`, entropy ≥ 128 bit. Il QR è lo stesso URL HTTPS.
- Google login: OIDC `openid email profile`. **Non** `calendar.*`. Scope calendario = `03`.
- Landing pubblica: TLS, no dati di colleghi, no elenco «chi lavora oggi».
- Design `06`. Testi italiani, aria, niente form da gestionale.
- Emilio è un ruolo **attivatore** (può coincidere col manager). Non attiva on-behalf l'OAuth di Anna.

Chiude l'aperto di `05` sull'IdP: email+password **e** Google, dopo attivazione.

---

## 4. Approccio

### 4.1 Due superfici

| Superficie | Chi | Autenticato? | Cosa c'è |
|---|---|---|---|
| **Landing** `/` | chiunque | no | marca TIME MACHINE / Le Rocce, login, «Ho un invito» |
| **Attivazione** `/attiva?t=` | titolare del token | no (diventa sì alla fine) | nome della persona, scelta uid/pwd **o** Google |
| **QR** | stesso URL | no | stampabile / telefono di Emilio |
| Home prodotto | persona attiva | sì | `02` — non è questa spec |

La landing **non** è una marketing site lunga. Una card (carta `06`), un composer di credenziali, un link piccolo all'invito. Prompt bar Beautiful UI come *forma*, non come chat.

### 4.2 Emilio attiva

Precondizione: esiste `kb/persone/{slug}.md`. Emilio è loggato, ruolo `attivatore`.

Da una lista «non ancora entrate» (solo slug + se ha email in scheda — non saldi, non preferenze):

| Chip | Atto |
|---|---|
| `invia-attivazione` | chiede/ conferma email → genera token → manda mail con link |
| `mostra-qr` | stesso token → QR a schermo (e «copia link»). Emilio lo mostra o lo stampa |
| `revoca-invito` | invalida il token ancora unused |

In scheda, solo il fatto:

```
account:
  stato: invitata | attiva | sospesa
  email: anna@…
  da: 2026-08-16
  via: email | qr
```

Niente token in `kb/`. Store cifrato, come `03`.

Email: oggetto secco («I tuoi turni — Le Rocce»). Un link. Nessun elenco turni nel corpo (minimizzazione `05`: la casella può essere condivisa).

QR: URL `https://<host>/attiva?t=<token>`. Scade come il link. Un secondo `mostra-qr` prima dell'uso ruota il token (il vecchio muore).

Emilio non «registra» la password di Anna e non fa login Google al posto suo.

### 4.3 Anna completa

Apre `/attiva?t=…` (mail o QR).

Token invalido/scaduto/già usato: card onesta + «chiedi un nuovo invito a Emilio». Zero dettaglio sul perché (no «già usato» vs «inesistente» se aiuta un attaccante a sondare — in pilota si può essere più chiari *dopo* un captcha / rate limit; default: messaggio unico).

Token ok: «Ciao Anna» (nome dalla scheda) + due vie, stesso peso visivo:

**A — uid e password**

- `uid` di default = email di attivazione. Può sceglierne uno (univoco nel PV, 3–32, `[a-z0-9._-]`).
- password ≥ 10, check base (non la mail, non `LeRocce2026`). Conferma doppia.
- Chip `crea-account` → sessione → home `02`.
- `account.stato: attiva`. Hash in store.

**B — Google**

- Chip `entra-con-google` → OIDC.
- Email Google deve **coincidere** con l'email di attivazione, *oppure* Emilio ha lasciato il campo email vuoto e il primo Google **fissa** quell'email sulla scheda (caso QR in negozio senza mail nota).
- Se Google email ≠ email invitata: stop, messaggio «questo Google non è quello su cui Emilio ti ha attivato». Niente account orfano.
- Si salva `google_sub` identità (distinto dal token calendar `03`).
- Sessione → home. **Nessuno** scope calendar.

Può aggiungere l'altra via dopo (da scheda: «imposta una password» / «collega Google per entrare»). Sempre lei, mai Emilio.

### 4.4 Login (già attiva)

Landing:

- campo uid o email + password → sessione
- oppure `entra-con-google` (stesso OIDC, match su `google_sub` o email già legata)
- «password dimenticata» → mail all'email *già* in scheda, nuovo token (non è un'attivazione: non crea persone)

Rate limit su `/login` e `/attiva`. Lockout progressivo. Log `caller` senza password.

Sessione: cookie httpOnly, secure, SameSite=Lax, rotazione all'attivazione. Logout visibile in guscio `02`.

### 4.5 Google identità vs Google calendario

| | `07` entra-con-google | `03` collega-google |
|---|---|---|
| Scopo | chi sei | dove scrivere i turni |
| Scope | `openid email profile` | `calendar.events` (calendario dedicato) |
| Quando | attivazione o login | da `person-shifts`, già autenticata |
| Revoca | scollega identità Google (resta uid/pwd se c'è) | cancella eventi nostri |

Un solo account Google della persona, due consensi. Togliere il calendar non la slogga. Togliere l'identità Google non cancella i turni.

### 4.6 Landing `[AIUxer]` / `[06]`

Fondo `carta`. Una card `carta-alta`. Fraunces sul nome prodotto. Niente hero da SaaS, niente «Built for retail».

- Titolo: i turni, non «Piattaforma workforce».
- Sotto: Le Rocce.
- Form login (uid/email + password) + chip `entra-con-google`.
- Testo piccolo: «Ti ha invitato Emilio? Apri il link della mail o inquadra il QR.»
- Campo opzionale «incolla il codice» se il QR è stato letto male (stesso `t`).

Niente Copilot sulla landing. Niente turni di nessuno. Niente `person-balances`.

Dopo login: redirect alla home `02`, zero tabellone.

---

## 5. Confine di fiducia

| Atto | Chi |
|---|---|
| Decidere che Anna può entrare | Emilio (`invia-attivazione` / `mostra-qr`) |
| Completare l'account (pwd o Google) | Anna, sul suo dispositivo |
| Login successivo | Anna |
| Vedere la lista «non ancora entrate» | Emilio |
| Creare una scheda persona | già in kb (fuori; non signup) |
| Collegare il calendario | Anna, `03`, dopo essere dentro |

L'AI non invita, non autentica, non manda mail.

---

## 6. Evals

| # | Caso | Gate |
|---|---|---|
| L1 | GET `/` anonimo | 200 landing; zero nomi di colleghi; zero turni |
| L2 | POST registrazione senza token | 4xx; 0 account creati |
| L3 | Token scaduto / riusato | messaggio unico; 0 sessione |
| L4 | Emilio invita Anna → lei setta pwd | `account.stato: attiva`; hash assente da `kb/`; login uid/pwd → home Anna |
| L5 | Stesso token, secondo tentativo | fail; il primo account resta |
| L6 | QR = stesso URL del link mail | attivazione unica |
| L7 | Google email ≠ email invitata | no account; Anna resta `invitata` |
| L8 | Login Google dopo L4 con *stessa* email (se ha collegato) o solo OIDC su B | sessione Anna; **zero** chiamate Calendar API |
| L9 | Sconosciuto prova uid `anna` / email Anna | stesso messaggio di credenziali sbagliate; timing allineato |
| L10 | Jessica loggata non vede chip `invia-attivazione` | 403 sulle API attivatore |

---

## 7. Aperto / decisioni già prese

**Prese**

- Invite-only. Emilio attiva.
- Email e/o QR, stesso token.
- Completamento: uid/pwd **o** Google identità.
- Google login ≠ Google calendar.
- Landing pubblica minima, fresco.
- Token e password fuori da `kb/`.

**Aperti**

- Provider mail (SES / Workspace dello studio) — non blocca il contratto.
- Se Emilio è anche store manager: stesso utente, due chip in più, non un'app admin.
- Username visibile vs solo email: default email come uid; username opzionale.
- 2FA: fuori da questa edizione (password + Google bastano al pilota).

**Fuori**

- Signup pubblico, social oltre Google, SAML insegna, magic-link come *unico* login permanente (il link è solo attivazione/reset).
- Emilio che imposta la password di Anna.

---

## 8. Use case

### UC-19 Emilio attiva Anna per email
- **Chi:** Emilio (attivatore); Anna Mondora
- **Quando:** Anna ha scheda, `account` assente
- **Fa:**
  1. Emilio apre «non ancora entrate», sceglie Anna, `invia-attivazione`, conferma `anna@…`.
  2. Anna riceve la mail, tap sul link.
  3. Vede «Ciao Anna» e due vie. Sceglie password, uid = email.
  4. `crea-account` → home: `person-shifts` 29/06 + `person-balances`.
  5. Il link, riaperto, non funziona.
- **Esito:** Anna è dentro. Emilio non ha visto la password.
- **AI può / non può:** non c'entra.

### UC-20 QR in corsia
- **Chi:** Emilio; Tiziana (non ha usato la mail, o non ce l'ha in scheda)
- **Quando:** turno, telefono in mano
- **Fa:**
  1. Emilio `mostra-qr` su Tiziana.
  2. Lei inquadra → `/attiva?t=`.
  3. Sceglie `entra-con-google`. Email Google si fissa in scheda (non c'era).
  4. Home Tiziana. Nessun evento in Calendar.
  5. Più tardi, da `person-shifts`, può `collega-google` (`03`) se vuole i turni sul calendario.
- **Esito:** attivata senza casella aziendale. Due consensi Google, distinti.
- **AI può / non può:** non c'entra.

### UC-21 Login il giorno dopo
- **Chi:** Anna, già `attiva` con pwd
- **Quando:** landing `/`
- **Fa:**
  1. Inserisce uid/email + password, oppure `entra-con-google` se l'ha collegato.
  2. Arriva sulla home persona. Zero tabellone.
  3. Uno sconosciuto sulla stessa pagina non ottiene indizi su Anna (L9).
- **Esito:** rientro banale. La landing non è il prodotto.
- **AI può / non può:** ancora spento, finché non è in home.

### UC-22 Nessuno si iscrive da solo
- **Chi:** sconosciuto sul web
- **Quando:** conosce l'URL
- **Fa:**
  1. Apre `/`. Vede login, non «Registrati».
  2. Inventa un token in query. Messaggio unico, niente account.
  3. Non trova lista dipendenti.
- **Esito:** L2 vale. Il PV resta chiuso.
- **AI può / non può:** non invita e non «aiuta» a entrare.

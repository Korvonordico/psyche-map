# Psyche Map

Una mappa 3D dei tuoi ricordi che cresce da sola mentre parli con la tua IA.

![Psyche Map](docs/psyche-mappa.png)

*English: [README.md](README.md)*

Psyche Map è un «secondo cervello» fatto per la vita interiore. Ogni ricordo che racconti alla tua IA finisce sulla
mappa: i temi della tua vita sono stelle, i ricordi sono pianeti che girano attorno, e i dettagli di ogni ricordo
sono lune. La tua IA legge la mappa prima di risponderti, così quando parli di qualcosa di personale sa già di
cosa parli.

Non è uno strumento per fare diagnosi e non sostituisce uno psicologo. Se qualcosa continua a farti male, parlane
con un professionista.

## Come funziona la mappa

La struttura segue il **Self-Memory System** di Conway e Pleydell-Pearce (2000), adattato:

| Sulla mappa | Nel modello di Conway | Cosa contiene |
|---|---|---|
| Nucleo | il sé che lavora | chi sei oggi, i tuoi scopi |
| Stelle | periodi della vita / temi | amore, famiglia, paura, lavoro... 24 temi, fissi: non si chiudono mai e possono ricrescere anni dopo |
| Pianeti | eventi generali | un ricordo o una situazione; due date: quando è successo e quando l'hai raccontato |
| Lune | dettagli specifici | un odore, una frase, un'immagine: i dettagli |

Un pianeta gira attorno a una stella; se appartiene anche a un altro tema, un filo sottile lo lega a quella
seconda stella.

**Si votano solo le lune**, perché un dettaglio è l'unica cosa che si può davvero risentire. Ogni luna ha un segno
(negativo, neutro, positivo) e una forza da 1 a 5, *come l'hai vissuta allora* (valenza e attivazione: Russell,
1980; la scala SAM: Bradley e Lang, 1994). Quando torni su un ricordo, l'IA aggiunge un voto *adesso*, così vedi
come è cambiata la sensazione: di solito il negativo sbiadisce più in fretta del positivo (il Fading Affect Bias).
I pianeti mostrano la media delle loro lune e la tendenza dei voti *adesso*, mai un numero solo.

I voti li dà l'IA da sola e ti chiede in chat se vanno bene. Se non rispondi, restano quelli.

Ogni pianeta ha anche un **taccuino dello psicologo**: poche righe in terza persona su cosa è successo e cosa ha
lasciato, e i meccanismi psicologici riconosciuti che tocca (evitamento, rimuginio, perdita di fiducia...), ognuno
con quello che diventa quando è estremo e stabile e la fonte ufficiale (DSM-5-TR, ICD-11). Sono ipotesi per
capirti meglio, mai diagnosi: per un disturbo servono un clinico, più segni insieme, una durata precisa e un danno
vero alla vita di tutti i giorni.

## Come si collega alla tua IA

```
scrivi alla tua IA ──► hook ──► diario (sul tuo PC)
                         │
                         └──► i pianeti più vicini arrivano all'IA prima che risponda

ogni mattina ──► Claude Code legge il diario ──► pianeti, lune, voti, taccuino nuovi
                 controllo: ogni ricordo deve essere con le tue parole, altrimenti si butta
                 le frasi usate vanno in un archivio chiuso; le altre si cancellano
```

- **Basta Claude Code.** Un hook passa i pianeti più vicini prima di ogni risposta e scrive i tuoi messaggi nel
  diario; ogni mattina un'attività di Windows avvia `claude -p` per portare il diario sulla mappa.
- **Hermes Agent è facoltativo**: con lui arrivano sulla mappa anche i messaggi da Telegram e quelli a voce.
- **Niente invenzioni**: il testo di ogni pianeta e di ogni luna deve essere copiato dalle tue parole; il programma
  lo controlla e scarta quello che non lo è.
- **Privacy**: mappa, diario e archivio restano sul tuo PC, in una cartella che scegli tu. L'unica cosa che esce è
  quella che esce già quando usi un'IA: il lavoro del mattino manda il diario a Claude perché lo ordini. Il diario
  si può spegnere quando vuoi.

## Installazione

Servono Windows 10 o 11, Python 3.9 o più recente e Claude Code (con l'accesso fatto).

```
git clone https://github.com/Korvonordico/psyche-map
cd psyche-map
python collegamento/psyche.py installa --lingua it
```

Anche con Hermes: aggiungi `--hermes` (al primo avvio Hermes chiede il permesso per l'hook: rispondi sì).
Altre opzioni: `--cartella DIR` (dove sta la tua mappa, di base `~/Psyche`), `--ora 06:30` (il lavoro del mattino),
`--modello sonnet` (il modello di Claude per il lavoro del mattino; `opus` scrive taccuini migliori e costa di più).

Poi apri `~/Psyche/psyche-it.html` nel browser. Si aggiorna da sola ogni 15 secondi.

Per aggiornare: `git pull`, poi di nuovo il comando di installazione. La tua mappa e il tuo diario restano come sono.

## Come si usa la pagina

- Trascina per girare la vista, usa la rotellina per avvicinarti. Clicca una stella o un pianeta per aprire il suo
  pannello; passa sopra una luna per leggerla e cliccala per aprirla. Esc chiude.
- La casella di ricerca trova una parola nei pianeti e nelle lune.
- Personalizza (tasto G): colori, bagliore e velocità. Le modifiche restano in questo browser.
- Serve internet: la grafica 3D arriva da cdn.jsdelivr.net.

## Comandi

```
python collegamento/psyche.py stato             cosa c'è sulla mappa, cosa aspetta
python collegamento/psyche.py lavora            fa subito il lavoro del mattino
python collegamento/psyche.py cerca "parole"    i pianeti più vicini, con i dettagli
python collegamento/psyche.py voto ID N SEGNO FORZA [adesso]   conferma o corregge il voto di una luna
python collegamento/psyche.py nucleo "chi sei, in poche righe"
python collegamento/psyche.py spegni | accendi  ferma o riavvia la scrittura del diario
python collegamento/psyche.py disinstalla       toglie hook e attività; i tuoi dati restano
```

Vuoi solo guardare? Apri `psyche-it.html` da sola: mostra qualche esempio e tiene i dati nel browser (Importa ed
Esporta in basso a destra).

## Formato dei dati

Per chi scrive la mappa a mano o con un'altra IA. `psyche-dati.js`, accanto alla pagina, è questo JSON scritto come
`window.PSYCHE_FILE = {...};` (uno script e non un file `.json`, perché una pagina aperta dal disco non può leggere
i file JSON). Importa accetta lo stesso JSON.

```json
{
  "core": { "nucleo": { "label": "NUCLEO", "description": "chi sei, in poche righe" } },
  "nodes": {
    "porto-2026-10-21": {
      "word": "PORTO", "theme": "infanzia", "temiAnche": ["famiglia"], "weight": 2,
      "text": "il ricordo, con le tue parole", "accadutoIl": "quando avevo otto anni",
      "createdAt": "2026-10-21T08:00:00+02:00", "linkedTo": [],
      "lune": [
        { "word": "MANO", "text": "un dettaglio", "segno": 1, "forza": 5,
          "adesso": [ { "data": "2026-11-02", "segno": 1, "forza": 4 } ] }
      ],
      "taccuino": ["poche righe in terza persona"],
      "meccanismi": [ { "nome": "evitamento", "testo": "cos'è e come si vede qui",
                        "estremo": "cosa diventa quando è estremo e stabile", "fonte": "DSM-5-TR, APA 2022" } ]
    }
  }
}
```

- `theme` è una delle 24 chiavi: identita, amore, metodo, relazione, creazione, famiglia, conflitto, solitudine,
  sostanza, ia, morte, sessualita, corpo, cura, infanzia, valore, denaro, casa, tempo, desiderio, lavoro, obiettivo,
  paura, ricordo.
- `segno` è -1, 0 o 1; `forza` va da 1 a 5; `adesso` tiene i voti *adesso* dati dopo.
- `accadutoIl` è quando è successo, a parole; `createdAt` è quando è stato scritto. `weight` va da 1 a 3.
- Tutti i campi tranne `word`, `theme` e `text` si possono lasciare fuori.

## Altri sistemi e altre IA

L'ho costruita e provata solo su quello che uso tutti i giorni: **Windows 11, Claude Code e Hermes Agent**. Non ho
esperienza diretta con altri sistemi o strumenti, quindi non posso farla funzionare lì da solo.

Se la vuoi su macOS o Linux, o con un'altra IA (Codex, Gemini CLI, Cursor, un modello locale...), **sei libero di
scaricare il codice, modificarlo e condividere la tua versione** (licenza MIT). Le parti da adattare sono piccole:
l'hook che legge i tuoi messaggi, il comando che fa il lavoro del mattino e l'avvio automatico. La mappa è un solo
file HTML che funziona in qualsiasi browser.

## Fonti

- Conway, M. A., e Pleydell-Pearce, C. W. (2000). The construction of autobiographical memories in the self-memory
  system. *Psychological Review*, 107(2), 261-288. https://pubmed.ncbi.nlm.nih.gov/10789197/
- Conway, M. A. (2005). Memory and the self. *Journal of Memory and Language*, 53(4), 594-628.
  https://doi.org/10.1016/j.jml.2005.08.005
- Russell, J. A. (1980). A circumplex model of affect. *Journal of Personality and Social Psychology*, 39(6),
  1161-1178. https://doi.org/10.1037/h0077714
- Bradley, M. M., e Lang, P. J. (1994). Measuring emotion: the Self-Assessment Manikin and the semantic
  differential. *Journal of Behavior Therapy and Experimental Psychiatry*, 25(1), 49-59.
  https://pubmed.ncbi.nlm.nih.gov/7962581/
- Skowronski, J. J., Walker, W. R., Henderson, D. X., e Bond, G. D. (2014). The Fading Affect Bias: its history,
  its implications, and its future. *Advances in Experimental Social Psychology*, 49, 163-218.
  https://doi.org/10.1016/B978-0-12-800052-6.00003-2
- Nolen-Hoeksema, S., Wisco, B. E., e Lyubomirsky, S. (2008). Rethinking rumination. *Perspectives on
  Psychological Science*, 3(5), 400-424. https://doi.org/10.1111/j.1745-6924.2008.00088.x
- Brown, N. R. (2016). Transition theory: a minimalist perspective on the organization of autobiographical memory.
  *Journal of Applied Research in Memory and Cognition*, 5(2), 128-134. https://doi.org/10.1016/j.jarmac.2016.03.005
  (un punto di vista diverso: i periodi nascono dai grandi cambiamenti della vita).
- American Psychiatric Association (2022). *DSM-5-TR*. https://www.psychiatry.org/psychiatrists/practice/dsm
- Organizzazione Mondiale della Sanità (2019). *ICD-11*. https://www.who.int/standards/classifications/classification-of-diseases

## Licenza

MIT: vedi [LICENSE](LICENSE).

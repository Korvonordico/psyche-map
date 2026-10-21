#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Psyche Map - connector between the map and your AI (Claude Code; Hermes Agent optional).

Collegamento tra la mappa e la tua IA: basta Claude Code; Hermes Agent e' facoltativo (aggiunge Telegram e voce).
Tested only on Windows 11. Other systems and other AIs: you are free to adapt the code (MIT licence).

  python psyche.py installa  [--lingua it|en] [--cartella DIR] [--ora 06:30] [--modello sonnet] [--hermes]
  python psyche.py disinstalla              removes hooks and the morning task (your data stays)
  python psyche.py cerca "parole"           nearest planets, with details (for the AI)
  python psyche.py lavora                   morning job: diary -> map (uses claude -p)
  python psyche.py accendi | spegni | stato diary recording on / off, status
  python psyche.py hook-claude | hook-hermes   used by the hooks (JSON on stdin)
English names work too: install, uninstall, search, work, on, off, status.
Every number on the map is automatic (the morning job and this file compute it): nobody types a vote.
"""
import datetime as dt
import glob
import json
import locale
import math
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
import zlib

QUI = os.path.dirname(os.path.abspath(__file__))
RADICE = os.path.dirname(QUI)
CONF_DIR = os.environ.get('PSYCHE_HOME') or os.path.join(os.path.expanduser('~'), '.psyche')
CONF = os.path.join(CONF_DIR, 'config.json')
WIN = os.name == 'nt'
NO_FINESTRA = 0x08000000 if WIN else 0
TASK = os.environ.get('PSYCHE_TASK_NAME') or 'Psyche Map'
MARCA = re.compile(r'psyche\.py\\?"\s+hook-')   # our hook command (in YAML the quote is escaped: \")
# The 26 stars. The last two, colpa (guilt and shame) and scoperta (leisure and discovery), make sure that every
# kind of self-defining memory found in the studies (Thorne and McLean; Singer and Blagov) has a star of its own.
TEMI = ('identita amore metodo relazione creazione famiglia conflitto solitudine sostanza ia morte sessualita corpo '
        'cura infanzia valore denaro casa tempo desiderio lavoro obiettivo paura ricordo colpa scoperta').split()
ALIAS = {'install': 'installa', 'uninstall': 'disinstalla', 'search': 'cerca', 'work': 'lavora', 'on': 'accendi',
         'off': 'spegni', 'status': 'stato'}
AUTOMATICI = ('<task-notification', '<command-', '<local-command', '<system-reminder', '[SYSTEM', '[CONTEXT',
              '[IMPORTANT', '[Background', '[OUT-OF-BAND', '[Cron', '[cron', 'Caveat:', '/')
PIATTAFORME_NO = {'cron', 'subagent', 'kanban', 'batch', 'webhook', 'oneshot', 'curator'}
MAX_LOTTO = 60000
MAX_TENTATIVI = 3
NUCLEO_MIN = 20     # memories needed before the core guesses who you would like to be (our choice, not a study)
NUCLEO_TEMI = 3     # ... spread over at least this many stars
NUCLEO_BASI = 7     # how many of the most central memories the AI reads for the core
# What kind of memory a planet is. Form: one moment (less than a day), the same moment many times, or something
# that lasted longer than a day: the three answers of the Autobiographical Memory Test (Williams and Broadbent,
# 1986), the same levels as Conway (2000). Role, optional: the four momentous events of Pillemer (2001).
FORME = ('singolo', 'ripetuto', 'periodo')
RUOLI = ('inizio', 'svolta', 'conferma', 'guida')
# The kind of every moon: the five kinds of lived detail of the Autobiographical Interview (Levine and colleagues,
# 2002): event, place, time, perceptions, emotions and thoughts.
CATEGORIE = ('evento', 'luogo', 'tempo', 'sensi', 'emozioni')
# Meaning: a lesson (a rule for how to act) or an insight (something understood about oneself, others or life),
# as McLean and Thorne (2003) coded them; a memory with one of them is «integrative» for Blagov and Singer (2004).
SIGNIFICATI = ('lezione', 'comprensione')
SINONIMI = {'single': 'singolo', 'specific': 'singolo', 'repeated': 'ripetuto', 'categoric': 'ripetuto',
            'extended': 'periodo', 'period': 'periodo', 'beginning': 'inizio', 'originating': 'inizio',
            'turning point': 'svolta', 'turning': 'svolta', 'anchor': 'conferma', 'anchoring': 'conferma',
            'guide': 'guida', 'analogous': 'guida', 'event': 'evento', 'place': 'luogo', 'time': 'tempo',
            'senses': 'sensi', 'perceptual': 'sensi', 'emotion': 'emozioni', 'emotions': 'emozioni',
            'thoughts': 'emozioni', 'lesson': 'lezione', 'insight': 'comprensione'}
# Elaboration (Pennebaker, Mayne e Francis 1997): more words of cause and of insight, as the person writes about a
# memory again and again, go with working it through. Our own short lists, in the spirit of the LIWC categories
# «cause» and «insight» (not the official dictionary). They run on text without accents, in lower case.
CAUSA = re.compile(r"\b(perche|poiche|siccome|quindi|dunque|percio|causa|cause|causato|causata|motivo|motivi|"
                   r"effetto|effetti|conseguenza|conseguenze|because|caused|causes|reason|reasons|why|effect|"
                   r"effects|hence|therefore|thus|consequence|consequences)\b")
CAPIRE = re.compile(r"\b(capire|capito|capisco|capivo|capendo|comprendo|comprendere|(reso|resa|rendo|rendermi|rendersi) "
                    r"conto|accort[oaie]|accorgo|accorgermi|accorgersi|significa|significato|significava|consapevol\w*|"
                    r"riflett\w*|scoperto|scoperta|scopro|imparato|imparata|penso|pensavo|pensato|pensare|sapevo|"
                    r"realize[ds]?|realise[ds]?|realizing|realising|understand|understands|understood|know|knew|"
                    r"think|thinking|thought|meaning|learned|learnt|aware|awareness|figured|insight|recogni[sz]ed?|"
                    r"discovered|concluded)\b")
# Centrality (Centrality of Event Scale, Berntsen e Rubin 2006, adapted): phrases that make a memory a turning
# point or a part of who one is.
IDENTITA = re.compile(r"\b(da allora|da quel (giorno|momento|periodo)|da li in poi|mi ha (cambiat[oa]|segnat[oa]|"
                      r"format[oa]|fatto diventare)|sono diventat[oa]|parte di me|punto di svolta|una svolta|"
                      r"non sono piu (lo stesso|la stessa)|ha cambiato (la mia vita|tutto)|since then|ever since|"
                      r"from (that|then) (day|moment|on)|(changed|shaped|marked|defined) (me|my life|who i am)|"
                      r"made me who i am|part of (me|who i am)|turning point|i became|never (been )?the same|"
                      r"changed everything)\b")
STOP = set('''anche ancora avere aveva avevo come cosa cose dalla dalle degli della delle dello dentro dopo essere
fare fatto fino hanno sono stato stata stati state siamo sempre tutto tutti tutte tanto molto poco pero oppure quindi
allora mentre sulla sulle sugli nella nelle negli adesso questo questa questi queste quello quella quelli quelle
perche quando dove anch cioe proprio ogni altro altra altri altre loro nostro vostro mio mia miei mie tuo tua suoi
sue gli sei ero era erano have that this with from your what when where which would could should about there their
they them then than been were will just like into more most only over some such very also because really thing
things know think make want need does done said says'''.split())

M = {
 'it': {
  'intesta': ("MAPPA PSYCHE (la mappa dei ricordi di chi ti scrive: serve a capire meglio di cosa parla. Usala con "
              "tatto e non citarla se non serve.)"),
  'vicini': "Pianeti piu' vicini a questo messaggio:",
  'cerca': 'Per i dettagli o per cercare altro: %s cerca "parole"',
  'resoconto': "Lavoro del mattino sulla mappa: %s. Se capita, diglielo in una riga.",
  'avvisi': "ATTENZIONE, dal lavoro del mattino (trattalo con delicatezza, senza allarmare):",
  'pos': 'positivo', 'neg': 'negativo', 'allora': 'allora',
  'verd': {'pos': 'prevale il positivo', 'neg': 'prevale il negativo', 'amb': 'ambivalente', 'neu': 'neutro'},
  'misure': "centralita' %d punti (%d° su %d; giorni %d, legami %d, frasi di identita' %d)",
  'elab': "elaborazione %s parole di causa e comprensione ogni 100", 'vivi': "vividezza %d%% dettagli vissuti (%d su %d)",
  'voce': 'voce', 'nucleo_res': 'nucleo aggiornato',
  'forma': {'singolo': 'momento singolo', 'ripetuto': 'momento ripetuto', 'periodo': 'periodo lungo'},
  'ruolo': {'inizio': 'un inizio', 'svolta': 'una svolta', 'conferma': 'una conferma di sé', 'guida': 'una guida per oggi'},
  'cat': {'evento': 'evento', 'luogo': 'luogo', 'tempo': 'tempo', 'sensi': 'sensi', 'emozioni': 'emozioni e pensieri'},
  'sig_t': {'lezione': 'lezione', 'comprensione': 'comprensione'}, 'sign_n': 'significato',
  'sign': 'significato: lezioni %d, comprensioni %d', 'cop': 'tipi di dettaglio nelle lune %d su %d',
  'adesso': 'adesso', 'lune': 'lune', 'vuota': '(vuota)', 'nessuno': 'Nessun pianeta vicino.',
  'non_inst': 'Psyche Map non e\' installata: python psyche.py installa',
  'inst_ok': "Psyche Map installata.",
  'inst_mappa': "  Mappa: %s (aprila nel browser: si aggiorna da sola)",
  'inst_dati': "  Dati: %s  -  diario: %s",
  'inst_cc': "  Claude Code: hook aggiunto in %s (copia di prima: %s)",
  'inst_cc_no': "  Claude Code: NON collegato (%s)",
  'inst_task': "  Lavoro del mattino: ogni giorno alle %s (attivita' di Windows «%s»; parte anche dopo, se il PC era spento)",
  'inst_task_no': "  Lavoro del mattino: da mettere a mano: %s",
  'inst_h': "  Hermes: hook aggiunto in %s (al primo avvio Hermes chiede il permesso: rispondi si')",
  'inst_h_no': "  Hermes: da collegare a mano, aggiungi in config.yaml:\n%s",
  'inst_fine': "Diario spento/acceso: python psyche.py spegni / accendi. Per togliere tutto: python psyche.py disinstalla.",
  'dis_ok': "Hook e attivita' tolti. I tuoi dati restano in %s.",
  'acceso': 'Diario ACCESO: i tuoi messaggi alla IA vengono scritti nel diario.',
  'spento': 'Diario SPENTO: i messaggi non vengono scritti (i pianeti vicini arrivano lo stesso).',
  'stato': ("Pianeti: %d  lune: %d  frasi nel diario: %d  diario: %s\nMappa: %s\n"
            "Ultimo lavoro: %s"),
  'on': 'acceso', 'off': 'spento',
  'niente': 'niente da fare: il diario e\' vuoto',
  'res': 'pianeti nuovi %d, aggiornati %d, lune nuove %d, riletture «adesso» %d, frasi scartate %d',
  'saltati': "saltate %d cose perche' non erano con le parole del diario",
  'claude_no': 'Claude Code non trovato: mettilo in config.json alla voce "claude"',
  'nucleo_label': 'NUCLEO',
 },
 'en': {
  'intesta': ("PSYCHE MAP (the map of memories of the person writing to you: it helps you understand what they mean. "
              "Use it with tact and do not quote it unless it helps.)"),
  'vicini': 'Planets closest to this message:',
  'cerca': 'For details or to look for something else: %s search "words"',
  'resoconto': 'Morning job on the map: %s. If it fits, tell them in one line.',
  'avvisi': 'ATTENTION, from the morning job (handle it gently, without alarming):',
  'pos': 'positive', 'neg': 'negative', 'allora': 'then',
  'verd': {'pos': 'positive prevails', 'neg': 'negative prevails', 'amb': 'ambivalent', 'neu': 'neutral'},
  'misure': 'centrality %d points (%d of %d; days %d, links %d, identity phrases %d)',
  'elab': 'elaboration %s words of cause and insight per 100', 'vivi': 'vividness %d%% lived details (%d of %d)',
  'voce': 'voice', 'nucleo_res': 'core updated',
  'forma': {'singolo': 'single moment', 'ripetuto': 'repeated moment', 'periodo': 'extended period'},
  'ruolo': {'inizio': 'a beginning', 'svolta': 'a turning point', 'conferma': 'an anchor', 'guida': 'a guide for today'},
  'cat': {'evento': 'event', 'luogo': 'place', 'tempo': 'time', 'sensi': 'senses', 'emozioni': 'emotions and thoughts'},
  'sig_t': {'lezione': 'lesson', 'comprensione': 'insight'}, 'sign_n': 'meaning',
  'sign': 'meaning: lessons %d, insights %d', 'cop': 'kinds of detail in the moons %d of %d',
  'adesso': 'now', 'lune': 'moons', 'vuota': '(empty)', 'nessuno': 'No planet nearby.',
  'non_inst': 'Psyche Map is not installed: python psyche.py install',
  'inst_ok': 'Psyche Map installed.',
  'inst_mappa': '  Map: %s (open it in the browser: it updates by itself)',
  'inst_dati': '  Data: %s  -  diary: %s',
  'inst_cc': '  Claude Code: hook added in %s (previous copy: %s)',
  'inst_cc_no': '  Claude Code: NOT connected (%s)',
  'inst_task': '  Morning job: every day at %s (Windows task «%s»; it also runs later if the PC was off)',
  'inst_task_no': '  Morning job: set it by hand: %s',
  'inst_h': '  Hermes: hook added in %s (on first start Hermes asks for permission: answer yes)',
  'inst_h_no': '  Hermes: connect it by hand, add to config.yaml:\n%s',
  'inst_fine': 'Diary off/on: python psyche.py off / on. To remove everything: python psyche.py uninstall.',
  'dis_ok': 'Hooks and task removed. Your data stays in %s.',
  'acceso': 'Diary ON: your messages to the AI are written to the diary.',
  'spento': 'Diary OFF: messages are not written (nearby planets still arrive).',
  'stato': ('Planets: %d  moons: %d  sentences in the diary: %d  diary: %s\nMap: %s\n'
            'Last job: %s'),
  'on': 'on', 'off': 'off',
  'niente': 'nothing to do: the diary is empty',
  'res': 'new planets %d, updated %d, new moons %d, «now» re-readings %d, sentences discarded %d',
  'saltati': 'skipped %d items because they were not in the words of the diary',
  'claude_no': 'Claude Code not found: put its path in config.json under "claude"',
  'nucleo_label': 'CORE',
 }}


# ------------------------------------------------------------------------------------------------ basics

def ora_iso():
    return dt.datetime.now().astimezone().isoformat(timespec='seconds')


def carica_json(p, predef=None):
    try:
        with open(p, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return predef


def salva_json(p, d):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    os.replace(tmp, p)


def cfg_carica():
    c = carica_json(CONF)
    return c if isinstance(c, dict) and c.get('cartella') else None


def lingua_cfg(cfg):
    return M.get((cfg or {}).get('lingua'), M['en'])


def percorso(*p):
    return os.path.join(*p).replace('\\', '/')


def comando_base():
    return '"%s" "%s"' % (sys.executable.replace('\\', '/'), percorso(QUI, 'psyche.py'))


def registro(cartella, riga):
    try:
        with open(os.path.join(cartella, 'registro.txt'), 'a', encoding='utf-8') as f:
            f.write('%s  %s\n' % (dt.datetime.now().strftime('%Y-%m-%d %H:%M'), riga))
    except OSError:
        pass


def leggi_mappa(cartella):
    try:
        t = open(os.path.join(cartella, 'psyche-dati.js'), encoding='utf-8').read()
        d = json.loads(t[t.index('{', t.index('PSYCHE_FILE')):t.rindex('}') + 1])
    except (OSError, ValueError):
        d = {}
    if not isinstance(d.get('nodes'), dict):
        d['nodes'] = {}
    if not isinstance(d.get('core'), dict):
        d['core'] = {}
    return d


def scrivi_mappa(cartella, d):
    p = os.path.join(cartella, 'psyche-dati.js')
    copie = os.path.join(cartella, 'copie')
    os.makedirs(copie, exist_ok=True)
    if os.path.exists(p):
        shutil.copy2(p, os.path.join(copie, 'psyche-dati-%s.js' % dt.datetime.now().strftime('%Y%m%d-%H%M%S')))
        for v in sorted(glob.glob(os.path.join(copie, 'psyche-dati-*.js')))[:-30]:
            os.remove(v)
    tmp = p + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        f.write('/* Psyche Map: data written by psyche.py (the connector). */\n')
        f.write('window.PSYCHE_FILE = ' + json.dumps(d, ensure_ascii=False, indent=1) + ';\n')
    os.replace(tmp, p)


def leggi_jsonl(p):
    out = []
    try:
        with open(p, encoding='utf-8') as f:
            for r in f:
                try:
                    v = json.loads(r)
                    if isinstance(v, dict) and v.get('testo'):
                        out.append(v)
                except ValueError:
                    pass
    except OSError:
        pass
    return out


def aggiungi_jsonl(p, voci):
    if not voci:
        return
    with open(p, 'a', encoding='utf-8', newline='\n') as f:
        for v in voci:
            f.write(json.dumps(v, ensure_ascii=False) + '\n')


def clamp(x, a, b):
    return max(a, min(b, x))


SCALA = 4   # each count goes from 0 (not at all) to 4 (extremely), like the Evaluative Space Grid (Larsen and colleagues, 2009)


def pn(x):
    """The two counts of a moon or of one of its «now» re-readings: (positive, negative), each 0-SCALA, or None.
    Never one number with a sign: positive and negative are kept apart (Cacioppo e Berntson 1994), so a detail
    that is sweet and painful at once stays visible. Old votes become counts (sign +1 strength 5 -> 4, 0)."""
    if not isinstance(x, dict):
        return None
    p, n = x.get('pos'), x.get('neg')
    if isinstance(p, (int, float)) or isinstance(n, (int, float)):
        return (clamp(int(round(abs(p or 0))), 0, SCALA), clamp(int(round(abs(n or 0))), 0, SCALA))
    s = x.get('segno')
    if isinstance(s, (int, float)):
        f = int(round(clamp(x.get('forza') or 3, 1, 5) * SCALA / 5.0))
        return (f, 0) if s > 0 else (0, f) if s < 0 else (0, 0)
    v = x.get('valore')
    if isinstance(v, (int, float)):
        f = int(round(clamp(abs(v), 0, 10) * SCALA / 10.0))
        return (f, 0) if v > 0 else (0, f)
    return None


def pn_adesso(l):
    ad = [a for a in l.get('adesso') or [] if pn(a)] if isinstance(l, dict) else []
    return pn(ad[-1]) if ad else None


def conti(lune, adesso=False):
    """A planet's two counts: the sums of its moons' counts (with adesso=True each moon's latest re-reading)."""
    p = n = k = 0
    for l in lune or []:
        v = (pn_adesso(l) or pn(l)) if adesso else pn(l)
        if v:
            p, n, k = p + v[0], n + v[1], k + 1
    return (p, n) if k else None


def verdetto(p, n):
    """neu when both are about zero; amb when the weaker count is more than a third of the stronger one, that is
    Griffin's ambivalence index (P+N)/2 - |P-N| above zero (Thompson, Zanna e Griffin 1995); else what prevails."""
    if p + n < 0.5:
        return 'neu'
    if min(p, n) * 3 > max(p, n):
        return 'amb'
    return 'pos' if p > n else 'neg'


def fmt_pn(v):
    return '?' if not v else '+%g/-%g' % (v[0], v[1])


def migra(d):
    """Old votes (sign and strength, or the first -10..+10 number) become the two counts: nothing is lost."""
    for n in d['nodes'].values():
        for l in (n.get('lune') or []) if isinstance(n, dict) else []:
            if not isinstance(l, dict):
                continue
            for x in [l] + [a for a in l.get('adesso') or [] if isinstance(a, dict)]:
                v = pn(x)
                if v and 'pos' not in x and 'neg' not in x:
                    x['pos'], x['neg'] = v
                for k in ('segno', 'forza', 'valore', 'provvisorio'):
                    x.pop(k, None)


def conta_parole(t):
    """Counts on the person's own words: words, words of cause and of insight (Pennebaker), identity phrases."""
    a = unicodedata.normalize('NFKD', str(t or '').replace('’', "'")).encode('ascii', 'ignore').decode('ascii')
    a = ' '.join(a.lower().replace("'", ' ').split())
    return {'parole': len(re.findall(r'[a-z0-9]+', a)), 'causa': len(CAUSA.findall(a)),
            'capire': len(CAPIRE.findall(a)), 'identita': len(IDENTITA.findall(a))}


def misure(d):
    """The automatic measures of every memory, written in node['misure'] for the page and recomputed at every job.
    Returns the memories from the most central down."""
    nodi = {i: n for i, n in d['nodes'].items() if isinstance(n, dict)}
    punti = {}
    for i, n in nodi.items():
        men = [m for m in n.get('menzioni') or [] if isinstance(m, dict)]
        giorni = {str(m.get('data'))[:10] for m in men if m.get('data')}
        if n.get('createdAt'):
            giorni.add(str(n['createdAt'])[:10])
        legami = len({x for x in n.get('linkedTo') or [] if x in nodi and x != i}) + len(n.get('temiAnche') or [])
        ident = sum(int(m.get('identita') or 0) for m in men)
        # centrality, adapted: how many days it came back, its links, its identity phrases, added up without
        # weights (the scale itself is a plain sum of its items)
        mi: dict = {'centralita': {'ritorni': len(giorni), 'legami': legami, 'identita': ident,
                                   'punti': len(giorni) + legami + ident}}
        q = [round(100.0 * ((m.get('causa') or 0) + (m.get('capire') or 0)) / m['parole'], 1)
             for m in men if (m.get('parole') or 0) >= 20]   # on fewer words the share means little
        if q:
            t = None if len(q) < 2 else 'su' if q[-1] - q[0] >= 1 else 'giu' if q[0] - q[-1] >= 1 else 'stabile'
            mi['elaborazione'] = {'prima': q[0], 'ultima': q[-1], 'volte': len(q), 'tendenza': t}
        a = sum(int(m.get('interni') or 0) for m in men)
        b = sum(int(m.get('esterni') or 0) for m in men)
        if a + b >= 3:
            mi['vividezza'] = {'interni': a, 'esterni': b, 'quota': int(round(100.0 * a / (a + b)))}
        # meaning: the lessons and insights the person said in words (McLean and Thorne 2003)
        sg = [x.get('tipo') for x in n.get('significati') or [] if isinstance(x, dict) and x.get('tipo') in SIGNIFICATI]
        if sg:
            mi['significato'] = {'lezioni': sg.count('lezione'), 'comprensioni': sg.count('comprensione')}
        # coverage: how many of the five kinds of lived detail (Levine and colleagues 2002) the moons touch
        cat = [l.get('categoria') for l in n.get('lune') or [] if isinstance(l, dict) and l.get('categoria') in CATEGORIE]
        if cat:
            mi['copertura'] = {'tipi': len(set(cat)), 'su': len(CATEGORIE), 'conti': {c: cat.count(c) for c in CATEGORIE}}
        n['misure'] = mi
        punti[i] = mi['centralita']['punti']
    ordine = sorted(punti, key=lambda i: (-punti[i], str(nodi[i].get('createdAt') or '')))
    for k, i in enumerate(ordine):
        nodi[i]['misure']['centralita'].update(posto=k + 1, su=len(ordine))
    return ordine


# ------------------------------------------------------------------------------------------------ nearest planets

def parole(t):
    t = unicodedata.normalize('NFKD', str(t or '')).encode('ascii', 'ignore').decode('ascii').lower()
    return [w[:6] for w in re.findall(r'[a-z0-9]+', t) if len(w) >= 4 and w not in STOP]


def testo_nodo(n):
    pezzi = [n.get('word'), n.get('theme'), n.get('text'), n.get('interpretation'), n.get('accadutoIl')]
    tc = n.get('taccuino')
    pezzi += tc if isinstance(tc, list) else [tc]
    for l in n.get('lune') or []:
        pezzi += [l.get('word'), l.get('text')] if isinstance(l, dict) else [l]
    return ' '.join(str(p) for p in pezzi if p)


def vicini(d, msg, k=5):
    idx = {i: set(parole(testo_nodo(n))) for i, n in (d.get('nodes') or {}).items() if isinstance(n, dict)}
    if not idx:
        return []
    df = {}
    for s in idx.values():
        for w in s:
            df[w] = df.get(w, 0) + 1
    q, n = set(parole(msg)), len(idx)
    punti = sorted(((sum(math.log(1 + n / df[w]) for w in q & s), i) for i, s in idx.items()), reverse=True)
    return [i for p, i in punti[:k] if p > 0]


def corto(t, n):
    t = ' '.join(str(t or '').split())
    return t if len(t) <= n else t[:n - 1] + '…'


def riga_breve(i, n, L):
    s = '%s [%s] (%s%s): «%s»' % (n.get('word') or i, i, n.get('theme') or '?',
                                  ', ' + n['accadutoIl'] if n.get('accadutoIl') else '', corto(n.get('text'), 140))
    lune = [l for l in n.get('lune') or [] if isinstance(l, dict)]
    if lune:
        s += ' %s: %s' % (L['lune'], ', '.join('%s %s' % (l.get('word') or corto(l.get('text'), 20), fmt_pn(pn(l)))
                                              for l in lune[:6]))
    return s


# ------------------------------------------------------------------------------------------------ hooks

def testo_msg(m):
    if isinstance(m, list):
        return ' '.join(p.get('text', '') for p in m if isinstance(p, dict) and p.get('type') == 'text')
    return str(m or '')


def contesto(cfg, msg, fonte):
    c, L = cfg['cartella'], lingua_cfg(cfg)
    st = carica_json(os.path.join(c, 'stato.json'), {}) or {}
    firma = '%s|%d' % (fonte, zlib.crc32(msg.encode('utf-8', 'replace')))
    nuovo = not (st.get('ultimo') == firma and time.time() - st.get('ultimo_t', 0) < 900)
    if nuovo and len(msg) >= 15 and not os.path.exists(os.path.join(c, 'SPENTO')):
        aggiungi_jsonl(os.path.join(c, 'diario.jsonl'),
                       [{'id': 'd%x' % int(time.time() * 1000), 'data': ora_iso(), 'fonte': fonte, 'testo': msg[:6000]}])
    st['ultimo'], st['ultimo_t'] = firma, time.time()
    parti, d = [], leggi_mappa(c)
    if st.get('resoconto'):
        parti.append(L['resoconto'] % st.pop('resoconto'))
    if st.get('avvisi'):
        parti.append(L['avvisi'] + ' ' + ' | '.join(st.pop('avvisi')))
    if len(msg) >= 15 and d['nodes']:
        vic = vicini(d, msg, 5)
        if vic:
            parti.append(L['vicini'] + ' ' + '; '.join(riga_breve(i, d['nodes'][i], L) for i in vic) + '. '
                         + L['cerca'] % comando_base())
    salva_json(os.path.join(c, 'stato.json'), st)
    return L['intesta'] + '\n' + '\n'.join(parti) if parti else ''


def hook(tipo):
    ctx = ''
    try:
        p = json.loads(sys.stdin.buffer.read().decode('utf-8', 'replace') or '{}')
        cfg = cfg_carica()
        if cfg and not os.environ.get('PSYCHE_LAVORO'):
            if tipo == 'claude':
                msg, fonte = str(p.get('prompt') or ''), 'claude-code'
            else:
                ex = p.get('extra') or {}
                piatt = str(ex.get('platform') or p.get('platform') or '').lower()
                ok = (p.get('hook_event_name') or 'pre_llm_call') == 'pre_llm_call' and piatt not in PIATTAFORME_NO
                msg, fonte = (testo_msg(ex.get('user_message')) if ok else ''), 'hermes' + (':' + piatt if piatt else '')
            msg = msg.strip()
            if msg and not msg.startswith(AUTOMATICI):
                ctx = contesto(cfg, msg, fonte)
    except Exception as e:  # a broken hook must never block the chat
        try:
            registro((cfg_carica() or {}).get('cartella') or CONF_DIR, 'hook %s: %s: %s' % (tipo, type(e).__name__, e))
        except Exception:
            pass
    if tipo == 'claude':
        if ctx:
            sys.stdout.write(json.dumps({'hookSpecificOutput': {'hookEventName': 'UserPromptSubmit',
                                                                 'additionalContext': ctx}}, ensure_ascii=True))
    else:
        sys.stdout.write(json.dumps({'context': ctx} if ctx else {}, ensure_ascii=True))
    sys.stdout.flush()


# ------------------------------------------------------------------------------------------------ morning job

def trova_claude(cfg):
    if cfg.get('claude') and os.path.exists(cfg['claude']):
        return cfg['claude']
    w = shutil.which('claude')
    if w:
        return w
    modelli = [os.path.join(os.environ.get('APPDATA', ''), 'Claude', 'claude-code', '*', '*', 'claude.exe'),
               os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Packages', 'Claude_*', 'LocalCache', 'Roaming',
                            'Claude', 'claude-code', '*', '*', 'claude.exe'),
               os.path.join(os.path.expanduser('~'), '.local', 'bin', 'claude*')]

    def versione(p):
        return tuple(int(x) if x.isdigit() else 0 for x in os.path.basename(os.path.dirname(os.path.dirname(p))).split('.'))
    c = sorted((x for m in modelli for x in glob.glob(m)), key=versione)
    return c[-1] if c else None


def norm_testo(t):
    t = unicodedata.normalize('NFKC', str(t or '')).lower()
    t = t.replace('’', "'").replace('‘', "'").replace('“', '"').replace('”', '"').replace('«', '"').replace('»', '"')
    return ' '.join(t.split())


def dentro(t, corpo):
    """True when every piece of t (pieces cut by «…» or «...») is word for word inside corpo."""
    pezzi = [p.strip(' "\'.,;:!?-') for p in re.split(r'\[\.\.\.\]|\.\.\.|…', norm_testo(t))]
    pezzi = [p for p in pezzi if p]
    return bool(pezzi) and all(p in corpo for p in pezzi)


def tema(x):
    x = unicodedata.normalize('NFKD', str(x or '')).encode('ascii', 'ignore').decode('ascii').lower().strip()
    return x if x in TEMI else None


def scelta(x, valori):
    """One of the allowed keys (also given by its English name), or None."""
    x = unicodedata.normalize('NFKD', str(x or '')).encode('ascii', 'ignore').decode('ascii').lower().strip()
    x = SINONIMI.get(x, x)
    return x if x in valori else None


def conto(x):
    try:
        return clamp(abs(int(x or 0)), 0, SCALA)
    except (TypeError, ValueError):
        return None


def luna_ok(l, corpo, ora):
    if not isinstance(l, dict) or ('pos' not in l and 'neg' not in l):
        return None
    t, p, n = str(l.get('text') or '').strip()[:300], conto(l.get('pos')), conto(l.get('neg'))
    if not t or p is None or n is None or not dentro(t, corpo):
        return None
    out = {'text': t, 'pos': p, 'neg': n, 'createdAt': ora}
    w = re.sub(r'\s+', '', str(l.get('word') or '')).upper()[:14]
    if w:
        out['word'] = w
    c = scelta(l.get('categoria'), CATEGORIE)
    if c:
        out['categoria'] = c
    return out


def voce_ok(v):
    """The third level of a memory: an idea of a real author on the same theme, in the AI's words, with the work
    and its year (no year, no voice: it makes the source checkable)."""
    if not isinstance(v, dict):
        return None
    v = {k: ' '.join(str(v.get(k) or '').split())[:420] for k in ('autore', 'opera', 'idea')}
    return v if all(v.values()) and len(v['autore']) <= 80 and re.search(r'\d', v['opera']) else None


def dettagli_ok(x):
    """Details counted by the AI with the categories of the Autobiographical Interview (Levine and colleagues 2002):
    internal = lived (event, place, time, perceptions, feelings then), external = comments, general facts."""
    try:
        return clamp(int(x.get('interni')), 0, 300), clamp(int(x.get('esterni')), 0, 300)
    except (TypeError, ValueError, AttributeError):
        return None


def detto(s):
    """True when the AI gave a meaning with words: if it then fails the check, it counts as skipped."""
    return isinstance(s, dict) and bool(str(s.get('text') or '').strip())


def significato_ok(s, corpo, ora):
    """A lesson or an insight, kept only with the person's own words (checked like the moons)."""
    if not isinstance(s, dict):
        return None
    k, t = scelta(s.get('tipo'), SIGNIFICATI), str(s.get('text') or '').strip()[:300]
    return {'tipo': k, 'text': t, 'data': ora[:10]} if k and t and dentro(t, corpo) else None


def menziona(n, corpo, det, ora):
    """One more day the memory came up in the diary: the counts on the words written about it (a second job on
    the same day adds to that day)."""
    m = dict(conta_parole(corpo), data=ora[:10])
    if det:
        m['interni'], m['esterni'] = det
    men = [x for x in n.get('menzioni') or [] if isinstance(x, dict)]
    if men and men[-1].get('data') == m['data']:
        for k, v in m.items():
            if k != 'data':
                men[-1][k] = int(men[-1].get(k) or 0) + v
    else:
        men = men[-59:] + [m]
    n['menzioni'] = men


def nucleo_ok(x, basi):
    if not isinstance(x, dict):
        return None
    t = ' '.join(str(x.get('ipotesi') or '').split())[:900]
    b = [i for i in x.get('basi') or [] if i in basi]
    return {'ipotesi': t, 'basi': b} if len(t) >= 40 and len(b) >= 2 else None


def mecc_ok(m):
    if not isinstance(m, dict):
        return None
    m = {k: str(m.get(k) or '').strip()[:600] for k in ('nome', 'testo', 'estremo', 'fonte')}
    # the page already writes «When it becomes extreme and lasting:», so a repeated opening is cut
    m['estremo'] = re.sub(r'(?i)^(quando|se|when|if)\b[^,:]{0,40}?(estrem|extreme)\w*(\s+(e|and)\s+(stabile|lasting|stable))?'
                          r'\s*[,:]?\s*', '', m['estremo']).strip()
    m['estremo'] = m['estremo'][:1].lower() + m['estremo'][1:]
    return m if all(m.values()) and re.search(r'DSM|ICD|\b(19|20)\d\d\b', m['fonte']) else None


def applica(d, r, voci, ora):
    """Applies the AI's proposal after checking it; returns a report. voci: label -> diary entry."""
    nodi, rep = d['nodes'], {'nuovi': 0, 'aggiornati': 0, 'lune': 0, 'adesso': 0, 'saltati': 0, 'usate': {}}
    rif = {}

    def corpo_di(fonti):
        ids = [x for x in (fonti or []) if isinstance(x, str) and x in voci]
        return ids, norm_testo(' '.join(voci[x]['testo'] for x in ids))

    def usa(ids, nid):
        for x in ids:
            rep['usate'].setdefault(x, []).append(nid)

    for p in r.get('nuovi') or []:
        if not isinstance(p, dict):
            continue
        ids, corpo = corpo_di(p.get('fonti'))
        word = re.sub(r'\s+', '', str(p.get('word') or '')).upper()[:18]
        th, text = tema(p.get('theme')), str(p.get('text') or '').strip()[:1500]
        if not (ids and word and th and text and dentro(text, corpo)):
            rep['saltati'] += 1
            continue
        lune = [x for x in (luna_ok(l, corpo, ora) for l in p.get('lune') or []) if x]
        rep['saltati'] += len(p.get('lune') or []) - len(lune)
        base = re.sub(r'[^a-z0-9]+', '-', unicodedata.normalize('NFKD', word.lower()).encode('ascii', 'ignore')
                      .decode('ascii')).strip('-') or 'nodo'
        nid, k = '%s-%s' % (base, ora[:10]), 2
        while nid in nodi:
            nid, k = '%s-%s-%d' % (base, ora[:10], k), k + 1
        n = {'word': word, 'theme': th, 'text': text, 'createdAt': ora, 'linkedTo': []}
        try:
            n['weight'] = clamp(int(p.get('weight') or 2), 1, 3)
        except (TypeError, ValueError):
            n['weight'] = 2
        if str(p.get('accadutoIl') or '').strip():
            n['accadutoIl'] = str(p['accadutoIl']).strip()[:60]
        for k, valori in (('forma', FORME), ('ruolo', RUOLI)):
            v = scelta(p.get(k), valori)
            if v:
                n[k] = v
        sg = significato_ok(p.get('significato'), corpo, ora)
        if sg:
            n['significati'] = [sg]
        elif detto(p.get('significato')):
            rep['saltati'] += 1
        ta = [t for t in (tema(x) for x in p.get('temiAnche') or []) if t and t != th][:2]
        if ta:
            n['temiAnche'] = ta
        tc = [str(x).strip()[:1500] for x in p.get('taccuino') or [] if str(x).strip()][:5]
        if tc:
            n['taccuino'] = tc
        mc = [x for x in (mecc_ok(m) for m in p.get('meccanismi') or []) if x][:2]
        if mc:
            n['meccanismi'] = mc
        vo = voce_ok(p.get('voce'))
        if vo:
            n['voce'] = vo
        if lune:
            n['lune'] = lune
        menziona(n, corpo, dettagli_ok(p.get('dettagli')), ora)
        nodi[nid] = n
        rif[str(p.get('rif') or word)] = nid
        rep['nuovi'] += 1
        rep['lune'] += len(lune)
        usa(ids, nid)

    for u in r.get('aggiorna') or []:
        if not isinstance(u, dict) or u.get('id') not in nodi:
            rep['saltati'] += 1
            continue
        ids, corpo = corpo_di(u.get('fonti'))
        if not ids:
            rep['saltati'] += 1
            continue
        n = nodi[u['id']]   # the memory came back: that alone counts (centrality, elaboration)
        menziona(n, corpo, dettagli_ok(u.get('dettagli')), ora)
        lune = [x for x in (luna_ok(l, corpo, ora) for l in u.get('lune') or []) if x]
        rep['saltati'] += len(u.get('lune') or []) - len(lune)
        if lune:
            n['lune'] = [l for l in n.get('lune') or []] + lune
            rep['lune'] += len(lune)
        for a in u.get('adesso') or []:
            try:
                j, p, q = int(a.get('luna')), conto(a.get('pos')), conto(a.get('neg'))
            except (TypeError, ValueError, AttributeError):
                rep['saltati'] += 1
                continue
            ll = n.get('lune') or []
            if not (0 <= j < len(ll)) or p is None or q is None or ('pos' not in a and 'neg' not in a):
                rep['saltati'] += 1
                continue
            if not isinstance(ll[j], dict):
                ll[j] = {'text': str(ll[j])}
            v = {'data': ora, 'pos': p, 'neg': q}
            if str(a.get('nota') or '').strip():
                v['nota'] = str(a['nota']).strip()[:300]
            ll[j].setdefault('adesso', []).append(v)
            rep['adesso'] += 1
        if not n.get('voce'):
            vo = voce_ok(u.get('voce'))
            if vo:
                n['voce'] = vo
        tc = [str(x).strip()[:1500] for x in u.get('taccuino') or [] if str(x).strip()]
        if tc:
            vecchio = n.get('taccuino')
            tutto = (vecchio if isinstance(vecchio, list) else [vecchio] if vecchio else []) + tc
            n['taccuino'] = tutto if len(tutto) <= 6 else tutto[:1] + tutto[-5:]   # the first note and the latest ones
        mc = [x for x in (mecc_ok(m) for m in u.get('meccanismi') or []) if x]
        nomi = {str(m.get('nome', '')).lower() for m in n.get('meccanismi') or [] if isinstance(m, dict)}
        mc = [m for m in mc if m['nome'].lower() not in nomi]
        if mc:
            n['meccanismi'] = (n.get('meccanismi') or []) + mc
        ta = [t for t in (tema(x) for x in u.get('temiAnche') or []) if t and t != n.get('theme')]
        ta = [t for t in ta if t not in (n.get('temiAnche') or [])]
        if ta:
            n['temiAnche'] = ((n.get('temiAnche') or []) + ta)[:3]
        if str(u.get('accadutoIl') or '').strip() and not n.get('accadutoIl'):
            n['accadutoIl'] = str(u['accadutoIl']).strip()[:60]
        for k, valori in (('forma', FORME), ('ruolo', RUOLI)):   # only when the planet has none yet
            v = scelta(u.get(k), valori)
            if v and not n.get(k):
                n[k] = v
        sg = significato_ok(u.get('significato'), corpo, ora)
        if sg:
            vs = [x for x in n.get('significati') or [] if isinstance(x, dict)]
            if norm_testo(sg['text']) not in {norm_testo(x.get('text')) for x in vs}:
                n['significati'] = (vs + [sg])[-6:]
        elif detto(u.get('significato')):
            rep['saltati'] += 1
        rep['aggiornati'] += 1
        usa(ids, u['id'])

    for c in r.get('legami') or []:
        if isinstance(c, (list, tuple)) and len(c) == 2:
            a, b = (rif.get(str(x), str(x)) for x in c)
            if a in nodi and b in nodi and a != b:
                for x, y in ((a, b), (b, a)):
                    lk = nodi[x].setdefault('linkedTo', [])
                    if y not in lk:
                        lk.append(y)
    return rep


def riassunto_mappa(d, testo_lotto, L):
    nodi = d['nodes']
    ids = list(nodi) if len(nodi) <= 80 else vicini(d, testo_lotto, 80)
    righe = []
    for i in ids:
        n = nodi[i]
        lune = [l for l in n.get('lune') or []]
        fr = '/'.join(x for x in (n.get('forma'), n.get('ruolo')) if x)
        s = '- id %s | %s | %s%s%s%s | «%s»' % (i, n.get('word') or '?', n.get('theme') or '?',
                                              ' +' + ','.join(n['temiAnche']) if n.get('temiAnche') else '',
                                              ' | ' + n['accadutoIl'] if n.get('accadutoIl') else '',
                                              ' | ' + fr if fr else '', corto(n.get('text'), 220))
        if lune:
            s += ' | %s: ' % L['lune'] + '; '.join('%d %s%s «%s» %s%s' % (j, (l.get('word') or '') if isinstance(l, dict) else '',
                                                                     '[%s]' % l['categoria'] if isinstance(l, dict) and l.get('categoria') else '',
                                                                     corto(l.get('text') if isinstance(l, dict) else l, 70),
                                                                     fmt_pn(pn(l)), ' %s %s' % (L['adesso'], fmt_pn(pn_adesso(l)))
                                                                     if pn_adesso(l) else '')
                                                 for j, l in enumerate(lune))
        tc = n.get('taccuino')
        tc = tc if isinstance(tc, list) else [tc] if tc else []
        if tc:
            s += ' | taccuino: «%s»' % corto(' '.join(str(x) for x in tc[-2:]), 260)
        mc = [str(m.get('nome')) for m in n.get('meccanismi') or [] if isinstance(m, dict) and m.get('nome')]
        if mc:
            s += ' | meccanismi: ' + ', '.join(mc)
        if isinstance(n.get('voce'), dict):
            s += ' | %s: %s' % (L['voce'], n['voce'].get('autore'))
        sg = [str(x.get('tipo')) for x in n.get('significati') or [] if isinstance(x, dict)]
        if sg:
            s += ' | %s: %s' % (L['sign_n'], ', '.join(sg))
        righe.append(s)
    return '\n'.join(righe) or L['vuota']


def per_nucleo(d, ordine, L):
    """The prompt section for the core: the most central memories, or why it is not time yet."""
    nodi, nu = d['nodes'], d['core'].get('nucleo') if isinstance(d['core'].get('nucleo'), dict) else {}
    temi = {n.get('theme') for n in nodi.values() if isinstance(n, dict) and n.get('theme')}
    if len(nodi) < NUCLEO_MIN or len(temi) < NUCLEO_TEMI:
        return [], 'NO (%d/%d, %d/%d)' % (len(nodi), NUCLEO_MIN, len(temi), NUCLEO_TEMI)
    basi = ordine[:NUCLEO_BASI]
    righe = []
    for i in basi:
        n = nodi[i]
        tc = n.get('taccuino')
        tc = tc if isinstance(tc, list) else [tc] if tc else []
        ce = n['misure']['centralita']
        sg = ''.join(' | %s: «%s»' % (L['sign_n'], corto(x.get('text'), 160))
                     for x in (n.get('significati') or [])[-2:] if isinstance(x, dict))
        righe.append('- id %s | %s | %s | %s | «%s»%s%s' % (
            i, n.get('word') or '?', n.get('theme') or '?',
            L['misure'] % tuple(ce[k] for k in ('punti', 'posto', 'su', 'ritorni', 'legami', 'identita')),
            corto(n.get('text'), 300), ' | taccuino: «%s»' % corto(tc[-1], 200) if tc else '', sg))
    prima = (nu or {}).get('ipotesi')
    return basi, ('SI / YES\n' + ('(%s) %s\n' % ('ipotesi attuale / current hypothesis', prima) if prima else '')
                  + '\n'.join(righe))


def estrai_json(t):
    t = str(t or '')
    i, j = t.find('{'), t.rfind('}')
    if i < 0 or j <= i:
        raise ValueError('no JSON in the answer')
    return json.loads(t[i:j + 1])


def lavora(cfg):
    c, L, lingua = cfg['cartella'], lingua_cfg(cfg), cfg.get('lingua', 'en')
    lock = os.path.join(c, 'lavoro.lock')
    if os.path.exists(lock) and time.time() - os.path.getmtime(lock) < 7200:
        print('busy'); return 0
    open(lock, 'w').close()
    dia, inl = os.path.join(c, 'diario.jsonl'), os.path.join(c, 'diario-in-lavoro.jsonl')
    try:
        if os.path.exists(dia):
            if os.path.exists(inl):
                aggiungi_jsonl(inl, leggi_jsonl(dia)); os.remove(dia)
            else:
                os.replace(dia, inl)
        voci = leggi_jsonl(inl)
        if not voci:
            registro(c, L['niente']); print(L['niente'])
            if os.path.exists(inl):
                os.remove(inl)
            return 0
        lotto, tot = [], 0
        for v in voci:
            if lotto and tot + len(v['testo']) > MAX_LOTTO:
                break
            lotto.append(v); tot += len(v['testo'])
        resto = voci[len(lotto):]
        etichette = {'d%d' % (k + 1): v for k, v in enumerate(lotto)}
        d = leggi_mappa(c)
        migra(d)
        ordine = misure(d)
        istr = open(os.path.join(QUI, 'istruzioni-it.md' if lingua == 'it' else 'instructions-en.md'), encoding='utf-8').read()
        basi, nucleo = per_nucleo(d, ordine, L)
        testo_lotto = ' '.join(v['testo'] for v in lotto)
        prompt = '%s\n\n## NUCLEO / CORE\n%s\n\n## MAPPA ATTUALE / CURRENT MAP\n%s\n\n## DIARIO / DIARY\n%s\n' % (
            istr, nucleo, riassunto_mappa(d, testo_lotto, L),
            '\n'.join('[%s] %s (%s): %s' % (k, v.get('data', '')[:16].replace('T', ' '), v.get('fonte', ''), v['testo'])
                      for k, v in etichette.items()))
        exe = trova_claude(cfg)
        if not exe:
            raise RuntimeError(L['claude_no'])
        cmd = [exe, '-p', 'Follow the instructions in the input and answer only with the JSON.', '--model',
               cfg.get('modello') or 'sonnet', '--output-format', 'json', '--tools', '', '--max-turns', '1',
               '--no-session-persistence'] + list(cfg.get('claude_extra') or [])
        r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding='utf-8', errors='replace',
                           cwd=c, env=dict(os.environ, PSYCHE_LAVORO='1'), timeout=1800, creationflags=NO_FINESTRA)
        try:
            esito = json.loads(r.stdout)
        except ValueError:
            raise RuntimeError('claude: %s' % ((r.stdout or '') + (r.stderr or ''))[-500:])
        if esito.get('is_error'):
            raise RuntimeError('claude: %s' % str(esito.get('result'))[:500])
        proposta = estrai_json(esito.get('result'))
        ora = ora_iso()
        rep = applica(d, proposta, etichette, ora)
        nu = nucleo_ok(proposta.get('nucleo'), basi)
        if nu:
            core = d['core'].setdefault('nucleo', {})
            core.update(nu, label=core.get('label') or L['nucleo_label'], updatedAt=ora)
            core.pop('description', None)
        misure(d)
        scartate = {x for x in proposta.get('scartate') or [] if x in etichette} - set(rep['usate'])
        scrivi_mappa(c, d)
        mese = os.path.join(c, 'archivio', 'diario-%s.jsonl' % ora[:7])
        os.makedirs(os.path.dirname(mese), exist_ok=True)
        aggiungi_jsonl(mese, [dict(etichette[x], usataIl=ora, nodi=rep['usate'][x]) for x in etichette if x in rep['usate']])
        rimaste = []
        for x, v in etichette.items():
            if x in rep['usate'] or x in scartate:
                continue
            v = dict(v, tentativi=v.get('tentativi', 0) + 1)
            if v['tentativi'] < MAX_TENTATIVI:
                rimaste.append(v)
        aggiungi_jsonl(dia, rimaste + resto)
        os.remove(inl)
        riga = L['res'] % (rep['nuovi'], rep['aggiornati'], rep['lune'], rep['adesso'], len(scartate))
        if nu:
            riga += '; ' + L['nucleo_res']
        if rep['saltati']:
            riga += '; ' + L['saltati'] % rep['saltati']
        st = carica_json(os.path.join(c, 'stato.json'), {}) or {}
        st['resoconto'] = riga
        av = [corto(a, 300) for a in proposta.get('avvisi') or [] if str(a).strip()][:3]
        if av:
            st['avvisi'] = (st.get('avvisi') or []) + av
        st['ultimo_lavoro'] = ora + '  ' + riga
        salva_json(os.path.join(c, 'stato.json'), st)
        u = esito.get('usage') or {}
        registro(c, '%s  (token: in %s, out %s)' % (riga, u.get('input_tokens'), u.get('output_tokens')))
        print(riga)
        return 0
    except Exception as e:
        if os.path.exists(inl):  # nothing is lost: the entries go back to the diary
            aggiungi_jsonl(dia, leggi_jsonl(inl)); os.remove(inl)
        registro(c, 'ERR %s: %s' % (type(e).__name__, e))
        print('ERR %s: %s' % (type(e).__name__, e))
        return 1
    finally:
        if os.path.exists(lock):
            os.remove(lock)


# ------------------------------------------------------------------------------------------------ install

def cc_settings():
    return os.path.join(os.environ.get('CLAUDE_CONFIG_DIR') or os.path.join(os.path.expanduser('~'), '.claude'),
                        'settings.json')


def hook_claude(aggiungi):
    p = cc_settings()
    s = carica_json(p, None) if os.path.exists(p) else {}
    if not isinstance(s, dict):
        raise RuntimeError('settings.json non leggibile / not readable: ' + p)
    copia = p + '.prima-di-psyche'
    if aggiungi and os.path.exists(p) and not os.path.exists(copia):
        shutil.copy2(p, copia)
    h = s.setdefault('hooks', {})
    lst = [m for m in h.get('UserPromptSubmit') or []
           if not any(MARCA.search(str(x.get('command', ''))) for x in (m.get('hooks') or []) if isinstance(x, dict))]
    if aggiungi:
        lst.append({'hooks': [{'type': 'command', 'command': comando_base() + ' hook-claude', 'timeout': 15}]})
    if lst:
        h['UserPromptSubmit'] = lst
    else:
        h.pop('UserPromptSubmit', None)
    if not h:
        s.pop('hooks', None)
    salva_json(p, s)
    return p, copia


def hermes_config():
    if os.environ.get('HERMES_HOME'):
        p = os.path.join(os.environ['HERMES_HOME'], 'config.yaml')
        return p if os.path.exists(p) else None
    for b in ([os.path.join(os.environ.get('LOCALAPPDATA', ''), 'hermes')] if WIN else []) + \
             [os.path.join(os.path.expanduser('~'), '.hermes')]:
        if os.path.exists(os.path.join(b, 'config.yaml')):
            return os.path.join(b, 'config.yaml')
    return None


def hook_hermes(aggiungi):
    """Adds or removes our pre_llm_call hook in Hermes' config.yaml by editing lines (comments stay)."""
    voce = ['    - command: ' + json.dumps(comando_base() + ' hook-hermes'), '      timeout: 15']
    p = hermes_config()
    if not p:
        return None, '\n'.join(['hooks:', '  pre_llm_call:'] + voce)
    raw = open(p, encoding='utf-8', newline='').read()   # newline='' keeps Windows line endings as they are
    nl = '\r\n' if '\r\n' in raw else '\n'
    righe = raw.split(nl)
    k = 0   # drop our old entry (the command line plus its indented options)
    while k < len(righe):
        if MARCA.search(righe[k]) and righe[k].lstrip().startswith('- command:'):
            ind = len(righe[k]) - len(righe[k].lstrip())
            fine = k + 1
            while fine < len(righe) and righe[fine].strip() and len(righe[fine]) - len(righe[fine].lstrip()) > ind \
                    and not righe[fine].lstrip().startswith('- '):
                fine += 1
            del righe[k:fine]
        else:
            k += 1
    if aggiungi:
        top = [i for i, r in enumerate(righe) if re.match(r'^hooks:\s*(#.*)?$', r)]
        if any(re.match(r'^hooks:\s*\S', r) and not re.match(r'^hooks:\s*#', r) for r in righe):
            return None, '\n'.join(['hooks:', '  pre_llm_call:'] + voce)
        if not top:
            while righe and not righe[-1].strip():
                righe.pop()
            righe += ['hooks:', '  pre_llm_call:'] + voce + ['']
        else:
            i = top[0] + 1
            fine = i
            while fine < len(righe) and (not righe[fine].strip() or righe[fine].startswith((' ', '\t', '#'))):
                fine += 1
            sub = [j for j in range(i, fine) if re.match(r'^  pre_llm_call:\s*(#.*)?$', righe[j])]
            if sub:
                j = sub[0] + 1
                while j < fine and (not righe[j].strip() or len(righe[j]) - len(righe[j].lstrip()) > 2):
                    j += 1
                while j - 1 > sub[0] and not righe[j - 1].strip():
                    j -= 1
                righe[j:j] = voce
            else:
                righe[i:i] = ['  pre_llm_call:'] + voce
    copia = p + '.prima-di-psyche'
    if aggiungi and not os.path.exists(copia):
        shutil.copy2(p, copia)
    with open(p + '.tmp', 'w', encoding='utf-8', newline='') as f:
        f.write(nl.join(righe))
    os.replace(p + '.tmp', p)
    return p, None


def attivita(aggiungi, ora='06:30'):
    if not WIN:
        return None, '%s %s * * *  "%s" "%s" lavora' % (ora[3:5], ora[:2], sys.executable, os.path.join(QUI, 'psyche.py'))
    if aggiungi:
        pyw = os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
        pyw = pyw if os.path.exists(pyw) else sys.executable
        q = lambda s: "'" + s.replace("'", "''") + "'"
        ps = ("$a = New-ScheduledTaskAction -Execute %s -Argument %s; "
              "$t = New-ScheduledTaskTrigger -Daily -At %s; "
              "$s = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries "
              "-ExecutionTimeLimit (New-TimeSpan -Hours 2); "
              "Register-ScheduledTask -TaskName %s -Action $a -Trigger $t -Settings $s -Force | Out-Null") % (
            q(pyw), q('"%s" lavora' % os.path.join(QUI, 'psyche.py')), q(ora), q(TASK))
    else:
        ps = "Unregister-ScheduledTask -TaskName '%s' -Confirm:$false -ErrorAction SilentlyContinue" % TASK.replace("'", "''")
    r = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', ps],
                       capture_output=True, text=True, creationflags=NO_FINESTRA)
    return (TASK, None) if r.returncode == 0 else (None, (r.stderr or r.stdout).strip()[:300])


def opzione(args, nome, predef=None):
    return args[args.index(nome) + 1] if nome in args and args.index(nome) + 1 < len(args) else predef


def installa(args):
    lingua = opzione(args, '--lingua') or opzione(args, '--language')
    if lingua not in ('it', 'en'):
        loc = (locale.getlocale()[0] or os.environ.get('LANG') or '').lower()
        lingua = 'it' if loc.startswith(('it', 'ital')) else 'en'
    L = M[lingua]
    cartella = os.path.abspath(opzione(args, '--cartella') or opzione(args, '--folder') or
                               os.path.join(os.path.expanduser('~'), 'Psyche'))
    ora = opzione(args, '--ora') or opzione(args, '--time') or '06:30'
    os.makedirs(cartella, exist_ok=True)
    pagina = os.path.join(cartella, 'psyche-%s.html' % lingua)
    sorgente = os.path.join(RADICE, 'psyche-%s.html' % lingua)
    if os.path.normcase(os.path.abspath(pagina)) != os.path.normcase(os.path.abspath(sorgente)):
        shutil.copy2(sorgente, pagina)
    if not os.path.exists(os.path.join(cartella, 'psyche-dati.js')):
        scrivi_mappa(cartella, {'core': {'nucleo': {'label': L['nucleo_label'], 'updatedAt': ora_iso()}},
                                'nodes': {}})
    vecchio = cfg_carica() or {}
    cfg = dict(vecchio, lingua=lingua, cartella=cartella, ora=ora, modello=opzione(args, '--modello') or
               opzione(args, '--model') or vecchio.get('modello') or 'sonnet', hermes='--hermes' in args)
    salva_json(CONF, cfg)
    print(L['inst_ok'])
    print(L['inst_mappa'] % pagina)
    print(L['inst_dati'] % (os.path.join(cartella, 'psyche-dati.js'), os.path.join(cartella, 'diario.jsonl')))
    try:
        p, copia = hook_claude(True)
        print(L['inst_cc'] % (p, copia if os.path.exists(copia) else '-'))
    except Exception as e:
        print(L['inst_cc_no'] % e)
    t, err = attivita(True, ora)
    print(L['inst_task'] % (ora, t) if t else L['inst_task_no'] % err)
    if '--hermes' in args:
        p, snippet = hook_hermes(True)
        print(L['inst_h'] % p if p else L['inst_h_no'] % snippet)
    print(L['inst_fine'])
    return 0


def disinstalla(cfg):
    L = lingua_cfg(cfg)
    try:
        hook_claude(False)
    except Exception as e:
        print('Claude Code: %s' % e)
    try:
        if hermes_config():
            hook_hermes(False)
    except Exception as e:   # uninstall goes on: the task must go away anyway
        print('Hermes: %s' % e)
    attivita(False)
    print(L['dis_ok'] % cfg['cartella'])
    return 0


# ------------------------------------------------------------------------------------------------ small commands

def misure_riga(n, L):
    """One line with a memory's automatic numbers, for «cerca»."""
    out = [x for x in (L['forma'].get(n.get('forma')), L['ruolo'].get(n.get('ruolo'))) if x]
    out = [', '.join(out)] if out else []
    cp = conti(n.get('lune'))
    if cp:
        ca = conti(n.get('lune'), True) or cp
        out.append('%s %s (%s)' % (L['allora'], fmt_pn(cp), L['verd'][verdetto(*cp)])
                   + ('' if ca == cp else ', %s %s (%s)' % (L['adesso'], fmt_pn(ca), L['verd'][verdetto(*ca)])))
    mi = n.get('misure') or {}
    if mi.get('centralita'):
        out.append(L['misure'] % tuple(mi['centralita'].get(k, 0) for k in
                                       ('punti', 'posto', 'su', 'ritorni', 'legami', 'identita')))
    if mi.get('elaborazione'):
        out.append(L['elab'] % mi['elaborazione'].get('ultima'))
    if mi.get('vividezza'):
        v = mi['vividezza']
        out.append(L['vivi'] % (v['quota'], v['interni'], v['interni'] + v['esterni']))
    if mi.get('copertura'):
        out.append(L['cop'] % (mi['copertura'].get('tipi', 0), mi['copertura'].get('su', len(CATEGORIE))))
    if mi.get('significato'):
        out.append(L['sign'] % (mi['significato'].get('lezioni', 0), mi['significato'].get('comprensioni', 0)))
    return ' | '.join(out)


def cerca(cfg, testo):
    L, d = lingua_cfg(cfg), leggi_mappa(cfg['cartella'])
    migra(d)
    misure(d)
    vic = vicini(d, testo, 5)
    if not vic:
        print(L['nessuno']); return 0
    for i in vic:
        n = d['nodes'][i]
        print('== %s [%s]  %s%s  %s%s' % (n.get('word'), i, n.get('theme'), ' +' + ','.join(n['temiAnche'])
                                          if n.get('temiAnche') else '', n.get('createdAt', '')[:10],
                                          '  (' + n['accadutoIl'] + ')' if n.get('accadutoIl') else ''))
        print('   ' + ' '.join(str(n.get('text') or '').split()))
        tc = n.get('taccuino')
        for t in (tc if isinstance(tc, list) else [tc] if tc else []):
            print('   ~ ' + t)
        for m in n.get('meccanismi') or []:
            if isinstance(m, dict):
                print('   * %s: %s (%s)' % (m.get('nome'), m.get('estremo'), m.get('fonte')))
        vo = n.get('voce')
        if isinstance(vo, dict):
            print('   » %s, %s: %s' % (vo.get('autore'), vo.get('opera'), vo.get('idea')))
        for x in n.get('significati') or []:
            if isinstance(x, dict):
                print('   ! %s: «%s»' % (L['sig_t'].get(x.get('tipo'), x.get('tipo')), x.get('text')))
        mr = misure_riga(n, L)
        if mr:
            print('   # ' + mr)
        for j, l in enumerate(n.get('lune') or []):
            if not isinstance(l, dict):
                print('   %d. %s' % (j, l)); continue
            ad = ['%s %s' % (str(a.get('data', ''))[:10], fmt_pn(pn(a)))
                  for a in l.get('adesso') or [] if isinstance(a, dict)]
            print('   %d. %s%s «%s» %s: %s%s' % (j, l.get('word') or '', ' [%s]' % L['cat'].get(l['categoria'], l['categoria'])
                                            if l.get('categoria') else '', l.get('text'), L['allora'], fmt_pn(pn(l)),
                                          ('  ' + L['adesso'] + ': ' + '; '.join(ad)) if ad else ''))
    return 0


def stato(cfg):
    L, c = lingua_cfg(cfg), cfg['cartella']
    d = leggi_mappa(c)
    lune = sum(len(n.get('lune') or []) for n in d['nodes'].values() if isinstance(n, dict))
    st = carica_json(os.path.join(c, 'stato.json'), {}) or {}
    print(L['stato'] % (len(d['nodes']), lune, len(leggi_jsonl(os.path.join(c, 'diario.jsonl'))),
                        L['off'] if os.path.exists(os.path.join(c, 'SPENTO')) else L['on'],
                        os.path.join(c, 'psyche-%s.html' % cfg.get('lingua', 'en')), st.get('ultimo_lavoro') or '-'))
    return 0


def main(argv):
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, ValueError):
            pass
    if not argv or argv[0] in ('-h', '--help', 'aiuto', 'help'):
        print(__doc__); return 0
    cmd, args = ALIAS.get(argv[0], argv[0]), argv[1:]
    if cmd in ('hook-claude', 'hook-hermes'):
        hook(cmd[5:]); return 0
    if cmd == 'installa':
        return installa(args)
    cfg = cfg_carica()
    if not cfg:
        print(M['it']['non_inst'] + '\n' + M['en']['non_inst']); return 1
    L, c = lingua_cfg(cfg), cfg['cartella']
    if cmd == 'disinstalla':
        return disinstalla(cfg)
    if cmd == 'lavora':
        return lavora(cfg)
    if cmd == 'cerca':
        return cerca(cfg, ' '.join(args))
    if cmd == 'stato':
        return stato(cfg)
    if cmd in ('accendi', 'spegni'):
        p = os.path.join(c, 'SPENTO')
        if cmd == 'spegni':
            open(p, 'w').close()
        elif os.path.exists(p):
            os.remove(p)
        print(L['acceso'] if cmd == 'accendi' else L['spento']); return 0
    print(__doc__); return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))

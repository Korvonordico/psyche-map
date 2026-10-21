#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Psyche Map - connector between the map and your AI (Claude Code; Hermes Agent optional).

Collegamento tra la mappa e la tua IA: basta Claude Code; Hermes Agent e' facoltativo (aggiunge Telegram e voce).
Tested only on Windows 11. Other systems and other AIs: you are free to adapt the code (MIT licence).

  python psyche.py installa  [--lingua it|en] [--cartella DIR] [--ora 06:30] [--modello sonnet] [--hermes]
  python psyche.py disinstalla              removes hooks and the morning task (your data stays)
  python psyche.py cerca "parole"           nearest planets, with details (for the AI)
  python psyche.py lavora                   morning job: diary -> map (uses claude -p)
  python psyche.py voto ID N SEGNO FORZA [adesso]   confirm or fix a moon's vote
  python psyche.py nucleo "chi sei"         the centre of the map, in a few lines
  python psyche.py accendi | spegni | stato diary recording on / off, status
  python psyche.py hook-claude | hook-hermes   used by the hooks (JSON on stdin)
English names work too: install, uninstall, search, work, vote, core, on, off, status.
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
TEMI = ('identita amore metodo relazione creazione famiglia conflitto solitudine sostanza ia morte sessualita corpo '
        'cura infanzia valore denaro casa tempo desiderio lavoro obiettivo paura ricordo').split()
ALIAS = {'install': 'installa', 'uninstall': 'disinstalla', 'search': 'cerca', 'work': 'lavora', 'vote': 'voto',
         'core': 'nucleo', 'on': 'accendi', 'off': 'spegni', 'status': 'stato'}
AUTOMATICI = ('<task-notification', '<command-', '<local-command', '<system-reminder', '[SYSTEM', '[CONTEXT',
              '[IMPORTANT', '[Background', '[OUT-OF-BAND', '[Cron', '[cron', 'Caveat:', '/')
PIATTAFORME_NO = {'cron', 'subagent', 'kanban', 'batch', 'webhook', 'oneshot', 'curator'}
MAX_LOTTO = 60000
MAX_TENTATIVI = 3
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
  'voti': ("VOTI DA CONFERMARE: l'IA ha dato un voto a questi dettagli dei ricordi (lune). Quando il momento e' "
           "giusto, non nel mezzo di un lavoro, chiedi in breve se vanno bene; per i voti «adesso» non dire il voto "
           "di prima. Se conferma o corregge: %s voto ID N SEGNO FORZA [adesso] (SEGNO -1, 0 o 1; FORZA da 1 a 5). "
           "Se non risponde, lasciali cosi'. Voti: %s"),
  'pos': 'positivo', 'neg': 'negativo', 'neu': 'neutro', 'forza': 'forza %d su 5', 'allora': 'allora',
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
  'stato': ("Pianeti: %d  lune: %d  voti da confermare: %d  frasi nel diario: %d  diario: %s\nMappa: %s\n"
            "Ultimo lavoro: %s"),
  'on': 'acceso', 'off': 'spento',
  'niente': 'niente da fare: il diario e\' vuoto',
  'voto_ok': 'Voto salvato: %s', 'voto_err': 'Voto non salvato: %s',
  'nucleo_ok': 'Nucleo aggiornato.',
  'res': 'pianeti nuovi %d, aggiornati %d, lune nuove %d, voti «adesso» %d, frasi scartate %d',
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
  'voti': ("VOTES TO CONFIRM: the AI rated these details of memories (moons). When the moment is right, not in the "
           "middle of a task, briefly ask whether they are right; for «now» votes do not say the previous vote. If "
           "they confirm or correct: %s vote ID N SIGN STRENGTH [now] (SIGN -1, 0 or 1; STRENGTH 1 to 5). If they "
           "do not answer, leave them as they are. Votes: %s"),
  'pos': 'positive', 'neg': 'negative', 'neu': 'neutral', 'forza': 'strength %d of 5', 'allora': 'then',
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
  'stato': ('Planets: %d  moons: %d  votes to confirm: %d  sentences in the diary: %d  diary: %s\nMap: %s\n'
            'Last job: %s'),
  'on': 'on', 'off': 'off',
  'niente': 'nothing to do: the diary is empty',
  'voto_ok': 'Vote saved: %s', 'voto_err': 'Vote not saved: %s',
  'nucleo_ok': 'Core updated.',
  'res': 'new planets %d, updated %d, new moons %d, «now» votes %d, sentences discarded %d',
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


def val_luna(l):
    if not isinstance(l, dict):
        return None
    s = l.get('segno')
    if isinstance(s, (int, float)):
        s = 1 if s > 0 else -1 if s < 0 else 0
        return 0 if s == 0 else s * clamp(int(round(l.get('forza') or 3)), 1, 5) * 2
    v = l.get('valore')
    return clamp(v, -10, 10) if isinstance(v, (int, float)) else None


def fmt_val(v):
    return '?' if v is None else ('+%g' % v if v > 0 else '%g' % v)


def descrivi_voto(L, s, f):
    if s is None:
        return '?'
    return (L['pos'] if s > 0 else L['neg'] if s < 0 else L['neu']) + ('' if not s else ', ' + L['forza'] % clamp(int(f or 3), 1, 5))


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
        s += ' %s: %s' % (L['lune'], ', '.join('%s %s' % (l.get('word') or corto(l.get('text'), 20), fmt_val(val_luna(l)))
                                              for l in lune[:6]))
    return s


# ------------------------------------------------------------------------------------------------ hooks

def testo_msg(m):
    if isinstance(m, list):
        return ' '.join(p.get('text', '') for p in m if isinstance(p, dict) and p.get('type') == 'text')
    return str(m or '')


def provvisori(d):
    out = []
    for i, n in (d.get('nodes') or {}).items():
        for j, l in enumerate(n.get('lune') or [] if isinstance(n, dict) else []):
            if not isinstance(l, dict):
                continue
            if l.get('provvisorio'):
                out.append(('%s|%d|p' % (i, j), i, j, False, n, l, l.get('segno'), l.get('forza')))
            ad = [a for a in l.get('adesso') or [] if isinstance(a, dict)]
            if ad and ad[-1].get('provvisorio'):
                out.append(('%s|%d|a|%s' % (i, j, ad[-1].get('data')), i, j, True, n, l, ad[-1].get('segno'),
                            ad[-1].get('forza')))
    return out


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
    oggi = dt.date.today().isoformat()
    if st.get('voti_giorno') != oggi:
        chiesti = st.get('chiesti') or []
        pv = [p for p in provvisori(d) if p[0] not in chiesti][:6]
        if pv:
            voci = ['%s › %s (%s, %s): %s [%s %d]' % (n.get('word') or i, l.get('word') or corto(l.get('text'), 24),
                                                     L['adesso'] if ad else L['allora'], corto(l.get('text'), 60),
                                                     descrivi_voto(L, s, f), i, j)
                    for k, i, j, ad, n, l, s, f in pv]
            parti.append(L['voti'] % (comando_base(), '; '.join(voci)))
            st['chiesti'] = (chiesti + [p[0] for p in pv])[-500:]
            st['voti_giorno'] = oggi
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


def luna_ok(l, corpo, ora):
    if not isinstance(l, dict):
        return None
    t, s = str(l.get('text') or '').strip()[:300], l.get('segno')
    if not t or s not in (-1, 0, 1) or not dentro(t, corpo):
        return None
    try:
        f = clamp(int(l.get('forza') or 3), 1, 5)
    except (TypeError, ValueError):
        f = 3
    out = {'text': t, 'segno': s, 'forza': f, 'provvisorio': True, 'createdAt': ora}
    w = re.sub(r'\s+', '', str(l.get('word') or '')).upper()[:14]
    if w:
        out['word'] = w
    return out


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
        ta = [t for t in (tema(x) for x in p.get('temiAnche') or []) if t and t != th][:2]
        if ta:
            n['temiAnche'] = ta
        tc = [str(x).strip()[:1500] for x in p.get('taccuino') or [] if str(x).strip()][:5]
        if tc:
            n['taccuino'] = tc
        mc = [x for x in (mecc_ok(m) for m in p.get('meccanismi') or []) if x][:2]
        if mc:
            n['meccanismi'] = mc
        if lune:
            n['lune'] = lune
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
        n, fatto = nodi[u['id']], False
        lune = [x for x in (luna_ok(l, corpo, ora) for l in u.get('lune') or []) if x]
        rep['saltati'] += len(u.get('lune') or []) - len(lune)
        if lune:
            n['lune'] = [l for l in n.get('lune') or []] + lune
            rep['lune'] += len(lune)
            fatto = True
        for a in u.get('adesso') or []:
            try:
                j, s, f = int(a.get('luna')), a.get('segno'), clamp(int(a.get('forza') or 3), 1, 5)
            except (TypeError, ValueError, AttributeError):
                rep['saltati'] += 1
                continue
            ll = n.get('lune') or []
            if not (0 <= j < len(ll)) or s not in (-1, 0, 1):
                rep['saltati'] += 1
                continue
            if not isinstance(ll[j], dict):
                ll[j] = {'text': str(ll[j])}
            v = {'data': ora, 'segno': s, 'forza': f, 'provvisorio': True}
            if str(a.get('nota') or '').strip():
                v['nota'] = str(a['nota']).strip()[:300]
            ll[j].setdefault('adesso', []).append(v)
            rep['adesso'] += 1
            fatto = True
        tc = [str(x).strip()[:1500] for x in u.get('taccuino') or [] if str(x).strip()]
        if tc:
            vecchio = n.get('taccuino')
            tutto = (vecchio if isinstance(vecchio, list) else [vecchio] if vecchio else []) + tc
            n['taccuino'] = tutto if len(tutto) <= 6 else tutto[:1] + tutto[-5:]   # the first note and the latest ones
            fatto = True
        mc = [x for x in (mecc_ok(m) for m in u.get('meccanismi') or []) if x]
        nomi = {str(m.get('nome', '')).lower() for m in n.get('meccanismi') or [] if isinstance(m, dict)}
        mc = [m for m in mc if m['nome'].lower() not in nomi]
        if mc:
            n['meccanismi'] = (n.get('meccanismi') or []) + mc
            fatto = True
        ta = [t for t in (tema(x) for x in u.get('temiAnche') or []) if t and t != n.get('theme')]
        ta = [t for t in ta if t not in (n.get('temiAnche') or [])]
        if ta:
            n['temiAnche'] = ((n.get('temiAnche') or []) + ta)[:3]
            fatto = True
        if str(u.get('accadutoIl') or '').strip() and not n.get('accadutoIl'):
            n['accadutoIl'] = str(u['accadutoIl']).strip()[:60]
            fatto = True
        if fatto:
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
        s = '- id %s | %s | %s%s%s | «%s»' % (i, n.get('word') or '?', n.get('theme') or '?',
                                            ' +' + ','.join(n['temiAnche']) if n.get('temiAnche') else '',
                                            ' | ' + n['accadutoIl'] if n.get('accadutoIl') else '', corto(n.get('text'), 220))
        if lune:
            s += ' | %s: ' % L['lune'] + '; '.join('%d %s «%s» %s' % (j, (l.get('word') or '') if isinstance(l, dict) else '',
                                                                   corto(l.get('text') if isinstance(l, dict) else l, 70),
                                                                   fmt_val(val_luna(l)))
                                                 for j, l in enumerate(lune))
        tc = n.get('taccuino')
        tc = tc if isinstance(tc, list) else [tc] if tc else []
        if tc:
            s += ' | taccuino: «%s»' % corto(' '.join(str(x) for x in tc[-2:]), 260)
        mc = [str(m.get('nome')) for m in n.get('meccanismi') or [] if isinstance(m, dict) and m.get('nome')]
        if mc:
            s += ' | meccanismi: ' + ', '.join(mc)
        righe.append(s)
    return '\n'.join(righe) or L['vuota']


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
        istr = open(os.path.join(QUI, 'istruzioni-it.md' if lingua == 'it' else 'instructions-en.md'), encoding='utf-8').read()
        nucleo = ' '.join('%s: %s' % (v.get('label', k), v.get('description', '')) for k, v in d['core'].items()
                          if isinstance(v, dict)) or L['vuota']
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
        scrivi_mappa(cartella, {'core': {'nucleo': {'label': L['nucleo_label'], 'description': '', 'updatedAt': ora_iso()}},
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

def cerca(cfg, testo):
    L, d = lingua_cfg(cfg), leggi_mappa(cfg['cartella'])
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
        for j, l in enumerate(n.get('lune') or []):
            if not isinstance(l, dict):
                print('   %d. %s' % (j, l)); continue
            ad = ['%s %s' % (str(a.get('data', ''))[:10], descrivi_voto(L, a.get('segno'), a.get('forza')))
                  for a in l.get('adesso') or [] if isinstance(a, dict)]
            print('   %d. %s «%s» %s: %s%s%s' % (j, l.get('word') or '', l.get('text'), L['allora'],
                                              descrivi_voto(L, l.get('segno'), l.get('forza')) if l.get('segno') is not None
                                              else fmt_val(val_luna(l)), ' *' if l.get('provvisorio') else '',
                                              ('  ' + L['adesso'] + ': ' + '; '.join(ad)) if ad else ''))
    return 0


def voto(cfg, a):
    L, c = lingua_cfg(cfg), cfg['cartella']
    d = leggi_mappa(c)
    try:
        nid, j = a[0], int(a[1])
        s = {'+': 1, '-': -1, '+1': 1, '1': 1, '-1': -1, '0': 0}[a[2]]
        f = int(a[3])
        if not 1 <= f <= 5:
            raise ValueError('forza 1-5')
        l = d['nodes'][nid]['lune'][j]
        if not isinstance(l, dict):
            l = d['nodes'][nid]['lune'][j] = {'text': str(l)}
    except (IndexError, KeyError, ValueError, TypeError) as e:
        print(L['voto_err'] % ('%s %s' % (type(e).__name__, e))); return 1
    if len(a) > 4 and a[4] in ('adesso', 'now'):
        ad = [x for x in l.get('adesso') or [] if isinstance(x, dict)]
        if not ad:
            print(L['voto_err'] % 'no «adesso»'); return 1
        ad[-1].update(segno=s, forza=f, provvisorio=False)
    else:
        l.update(segno=s, forza=f, provvisorio=False)
        l.pop('valore', None)
    scrivi_mappa(c, d)
    print(L['voto_ok'] % ('%s › %s: %s' % (d['nodes'][nid].get('word'), l.get('word') or corto(l.get('text'), 30),
                                          descrivi_voto(L, s, f))))
    return 0


def stato(cfg):
    L, c = lingua_cfg(cfg), cfg['cartella']
    d = leggi_mappa(c)
    lune = sum(len(n.get('lune') or []) for n in d['nodes'].values() if isinstance(n, dict))
    st = carica_json(os.path.join(c, 'stato.json'), {}) or {}
    print(L['stato'] % (len(d['nodes']), lune, len(provvisori(d)), len(leggi_jsonl(os.path.join(c, 'diario.jsonl'))),
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
    if cmd == 'voto':
        return voto(cfg, args)
    if cmd == 'stato':
        return stato(cfg)
    if cmd in ('accendi', 'spegni'):
        p = os.path.join(c, 'SPENTO')
        if cmd == 'spegni':
            open(p, 'w').close()
        elif os.path.exists(p):
            os.remove(p)
        print(L['acceso'] if cmd == 'accendi' else L['spento']); return 0
    if cmd == 'nucleo':
        d = leggi_mappa(c)
        n = d['core'].setdefault('nucleo', {'label': L['nucleo_label']})
        n.update(description=' '.join(args)[:2000], updatedAt=ora_iso())
        scrivi_mappa(c, d)
        print(L['nucleo_ok']); return 0
    print(__doc__); return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))

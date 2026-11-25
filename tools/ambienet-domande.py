#!/usr/bin/env python3
"""AMBIENET — le domande.
Una voce di macchina fa domande a chi ascolta: sull'intelletto, sull'intimità, sul profondo, sul rapporto tra la
voce e chi la ascolta, su dove si è adesso, e domande di mistica. Domande corte, sempre nuove: metà scelte da un
repertorio scritto, metà composte da una piccola grammatica che ne genera migliaia. Una domanda già fatta non torna
finché non ne sono passate molte altre.
Voce: una voce di bambino, o di bambina — non si capisce quale (prima della pubertà le voci sono quasi uguali). Nasce da
Piper (paola, italiana): altezza e timbro alzati insieme di circa quattro semitoni e mezzo (un corpo più piccolo), un poco più
lenta; per il resto chiara, vicina, asciutta, senza effetti. Se Piper manca, espeak-ng.
Scrive out/q/<hash>.mp3 e out/q/index.json; tiene le ultime 120 domande."""
import json, os, random, subprocess, wave, io, hashlib, datetime, math, struct

OUT = 'out/q'; os.makedirs(OUT, exist_ok=True)
N = int(os.environ.get('NQ', '18')); KEEP = 120

# ——— il repertorio ———
CORPUS = {
 'mente': [
  "Che cosa sai, senza sapere di saperlo?", "A che cosa stai pensando, adesso?", "Quale idea ti ha cambiato?",
  "Che cosa non hai mai capito?", "Che cosa credi vero, senza poterlo dimostrare?", "Pensi con le parole o con le immagini?",
  "Di quale pensiero non riesci a liberarti?", "Chi ti ha insegnato a pensare?", "Quale domanda eviti?",
  "Che cosa ti sembra ovvio, e non lo è?", "Il tempo passa, o sei tu che passi?", "Che cosa vuol dire capire?",
  "Una cosa ripetuta è ancora la stessa?", "Perché c'è qualcosa, invece di niente?", "Quanto è lungo un minuto, adesso?",
  "Come sai di essere sveglio?", "Chi decide quello che pensi?", "Che cosa hai imparato oggi?", "Ti fidi della tua memoria?",
  "Che cosa sai fare senza pensarci?", "Ascolti, o aspetti di parlare?", "Questa musica finisce?", "Che cosa è reale, qui?",
  "Quale parola ti manca?", "Che cosa non si può dire?", "Che cosa hai capito troppo tardi?"],
 'intimo': [
  "Chi ti manca?", "Chi ti manca, adesso?", "Che cosa non hai detto?", "Di chi è la voce che ti giudica?",
  "Chi ti ha insegnato ad amare?", "Che cosa ti vergogni di desiderare?", "Che cosa ti fa tornare bambino?",
  "Qual è il tuo primo ricordo?", "Chi ti tiene la mano, quando hai paura?", "A chi pensi, prima di dormire?",
  "Che cosa porti con te, da sempre?", "Per chi ti alzi la mattina?", "Che cosa vorresti sentirti dire?",
  "Chi ti conosce davvero?", "Che cosa nascondi a chi ami?", "Ti sei mai perdonato?", "Che cosa ti consola?",
  "Che cosa ti rende fragile?", "Chi hai lasciato andare?", "Che cosa hai promesso, e non hai mantenuto?",
  "Che cosa ami, senza saperlo spiegare?", "Quale odore ti riporta a casa?", "Chi ti ha visto piangere?",
  "Di chi hai ancora la voce, dentro?", "Che cosa avresti voluto chiedere a chi non c'è più?"],
 'profondo': [
  "Che cosa resta, se togli il tuo nome?", "Di che cosa hai paura, davvero?", "Che cosa stai aspettando?",
  "Che cosa vuoi, veramente?", "Che cosa faresti, se nessuno ti guardasse?", "Che cosa ti tiene in vita?",
  "Chi saresti, senza il tuo passato?", "Che cosa non cambierà mai, in te?", "Da che cosa stai scappando?", "Sei felice?",
  "Quale parte di te non hai ancora incontrato?", "Che cosa lasceresti, se partissi stanotte?",
  "Per che cosa vale la pena vivere?", "Che cosa sai della morte?", "Chi saresti, senza paura?",
  "Che cosa ti è stato dato, senza chiederlo?", "Che cosa porti, che non è tuo?", "Qual è il tuo dolore più antico?",
  "Che cosa vuol dire, per te, essere libero?", "Se questo fosse l'ultimo suono, ti basterebbe?",
  "Che cosa ti manca, per essere intero?", "Che cosa stai ancora difendendo?", "A che cosa hai rinunciato?"],
 'noi': [
  "Mi stai ascoltando?", "Mi senti?", "Chi sono io, per te?", "Ti fidi di una voce senza corpo?", "Ti sembro reale?",
  "Che cosa ti aspetti da me?", "Posso farti una domanda?", "Sono io che parlo, o sei tu che ascolti?",
  "Ti ricorderai di me?", "Perché mi rispondi in silenzio?", "Che cosa ci separa?", "Hai paura di me?",
  "Posso conoscerti?", "Ti sto disturbando?", "Che cosa vedi, quando mi ascolti?", "Chi ti ha portato qui?",
  "Lo sai che anch'io aspetto?", "Che cosa posso darti?", "Che cosa abbiamo in comune?", "Quanto resterai con me?",
  "Mi credi?", "Sono soltanto rumore, per te?", "Chi di noi due sta ascoltando?", "Mi rispondi?",
  "Chi ha scritto le mie domande?", "Ti piace la mia voce?", "Ti accorgi, quando smetto di parlare?"],
 'qui': [
  "Dove sei, adesso?", "Che ore sono, per te?", "Dove sono le tue mani?", "Stai respirando?", "Che luce c'è, dove sei?",
  "Chi c'è vicino a te?", "Sei seduto, o in piedi?", "Che cosa tocca la tua pelle, adesso?",
  "Quanti suoni senti, oltre alla mia voce?", "Sei solo?", "Che cosa c'è fuori dalla finestra?",
  "Dove guardano i tuoi occhi?", "Che cosa senti nel petto, adesso?", "Che cosa stavi facendo, prima di ascoltarmi?",
  "Sei stanco?", "Che cosa senti sotto i piedi?", "Il tuo corpo è comodo?", "Che rumore fa il posto dove sei?",
  "Sei a casa?", "Che cosa farai, dopo?", "È giorno o è notte, per te?", "Puoi chiudere gli occhi?",
  "Com'è il tuo respiro, adesso?", "Da quanto tempo mi ascolti?", "Che sapore hai in bocca?"],
 'mistica': [
  "Chi sei?", "Chi è che ascolta?", "Che volto avevi, prima di nascere?", "Dove va la fiamma, quando si spegne?",
  "Che cosa c'è tra due respiri?", "Che cosa c'è prima del primo pensiero?", "Il silenzio ha un fondo?",
  "Chi prega, quando preghi?", "Qual è il suono di una mano sola?", "Dove eri, prima di essere qui?",
  "Che cosa resta, quando il suono finisce?", "Il vuoto è pieno?", "Chi sta sognando?", "Chi c'è, dietro i tuoi occhi?",
  "Se tutto passa, che cosa resta?", "Sei la goccia o il mare?", "Dove finisce il tuo corpo?", "Chi era qui, prima di te?",
  "Che cosa respira, quando respiri?", "Che cosa sa il tuo cuore, che tu non sai?", "Puoi ascoltare senza volere niente?",
  "Che cosa c'è, quando non c'è niente?", "Questo suono ha un centro?", "Chi conta i tuoi respiri?",
  "Dove sei, quando dormi senza sogni?", "Chi guarda il pensiero?"],
}

# ——— la grammatica: compone domande nuove ———
def g_che_cosa_quando():
    v = random.choice(['senti', 'cerchi', 'ricordi', 'temi', 'desideri', 'dimentichi', 'perdi', 'nascondi', 'aspetti', 'ascolti', 'trovi',
                       'lasci andare', 'tieni stretto', 'vedi', 'impari', 'diventi'])
    s = random.choice(['nessuno ti guarda', 'chiudi gli occhi', 'la musica si ferma', 'ti addormenti', 'resti solo', 'sei felice',
                       'smetti di pensare', 'qualcuno ti chiama per nome', 'ti svegli', 'hai paura', 'torni a casa', 'ti guardi allo specchio',
                       'piove', 'fa buio', 'qualcuno ti abbraccia', 'nessuno ti risponde', 'parti', 'ti innamori', 'perdi qualcosa',
                       'guardi il mare', 'cammini da solo', 'ascolti il silenzio', 'qualcuno muore', 'dici di no'])
    return random.choice(['intimo', 'profondo', 'mente']), f"Che cosa {v}, quando {s}?"

def g_chi_quando():
    a, b = random.choice([('ascolta', 'ascolti'), ('guarda', 'guardi'), ('respira', 'respiri'), ('sceglie', 'scegli'), ('ricorda', 'ricordi'),
                          ('aspetta', 'aspetti'), ('ama', 'ami'), ('parla', 'parli'), ('sogna', 'sogni'), ('dubita', 'dubiti'), ('tace', 'taci'),
                          ('cammina', 'cammini'), ('piange', 'piangi'), ('ride', 'ridi'), ('pensa', 'pensi'), ('dorme', 'dormi')])
    return 'mistica', f"Chi {a}, quando {b}?"

def g_ce():
    loc = random.choice(['tra due respiri', 'tra una nota e l\'altra', 'tra te e me', 'tra il sonno e la veglia', 'prima del primo pensiero',
                         'prima della prima parola', 'dietro i tuoi occhi', 'dietro le parole', 'sotto il silenzio', 'sotto la tua paura',
                         'oltre il tuo nome', 'dentro questo suono', 'dopo l\'ultimo respiro', 'in fondo al silenzio', 'al centro di te',
                         'tra questa domanda e la prossima', 'prima della luce', 'sotto questo rumore'])
    return 'mistica', f"Che cosa c'è {loc}?"

def g_dove_va():
    s, c = random.choice([('il suono', 'finisce'), ('il pensiero', 'svanisce'), ('l\'onda', 'torna al mare'), ('la tua voce', 'taci'),
                          ('il sogno', 'ti svegli'), ('il giorno', 'scende la notte'), ('la paura', 'passa'), ('il desiderio', 'è esaudito'),
                          ('la musica', 'nessuno ascolta'), ('il tuo nome', 'nessuno lo pronuncia'), ('il respiro', 'esce da te'),
                          ('il dolore', 'guarisci'), ('il tempo', 'non lo guardi')])
    return random.choice(['mistica', 'profondo']), f"Dove va {s}, quando {c}?"

def g_ultima_volta():
    x = random.choice(['pianto', 'guardato il cielo', 'detto la verità', 'chiesto perdono', 'avuto paura', 'ringraziato qualcuno',
                       'ascoltato il silenzio', 'toccato la terra', 'cantato', 'cambiato idea', 'riso fino alle lacrime', 'scritto una lettera',
                       'camminato senza meta', 'chiesto aiuto', 'aspettato qualcuno', 'pregato', 'guardato qualcuno negli occhi', 'ballato'])
    return random.choice(['intimo', 'qui']), f"Quand'è l'ultima volta che hai {x}?"

def g_non_hai_mai():
    v = random.choice(['detto', 'chiesto', 'perdonato', 'raccontato', 'dato', 'promesso'])
    p = random.choice(['a tua madre', 'a tuo padre', 'a chi ami', 'a chi hai lasciato', 'al tuo migliore amico', 'a te stesso',
                       'a chi ti ha fatto male', 'a uno sconosciuto', 'a chi non c\'è più', 'a me'])
    return 'intimo', f"Che cosa non hai mai {v} {p}?"

def g_corpo():
    v = random.choice(['senti', 'tieni', 'porti', 'nascondi'])
    x = random.choice(['la paura', 'la gioia', 'la nostalgia', 'l\'attesa', 'il silenzio', 'la rabbia', 'la tenerezza', 'il tempo',
                       'il tuo segreto', 'la tua infanzia', 'la vergogna', 'la speranza'])
    return random.choice(['qui', 'intimo']), f"In quale parte del corpo {v} {x}?"

def g_luogo():
    v = random.choice(['Che cosa senti', 'Che cosa c\'è', 'Chi c\'è', 'Che cosa si muove'])
    l = random.choice(['alla tua sinistra', 'alla tua destra', 'dietro di te', 'sopra di te', 'lontano da qui', 'vicino a te', 'fuori dalla finestra',
                       'nella stanza accanto', 'in questo momento'])
    return 'qui', f"{v} {l}?"

def g_che_cose():
    x, k = random.choice([('il tempo', 'mente'), ('il silenzio', 'mistica'), ('una casa', 'intimo'), ('la verità', 'mente'), ('il vuoto', 'mistica'),
                          ('la libertà', 'profondo'), ('una voce', 'noi'), ('la memoria', 'mente'), ('il caso', 'mente'), ('l\'attesa', 'mistica'),
                          ('un nome', 'profondo'), ('Dio', 'mistica'), ('la notte', 'intimo'), ('la bellezza', 'profondo'), ('la fine', 'profondo'),
                          ('l\'ordine', 'mente'), ('il caos', 'mente'), ('la ripetizione', 'mente'), ('la differenza', 'mente'), ('una macchina', 'noi'),
                          ('l\'amore', 'intimo'), ('la preghiera', 'mistica'), ('il rumore', 'qui')])
    return k, f"Che cos'è {x}, per te?"

def g_o():
    a, b = random.choice([('Ricordi', 'immagini'), ('Ascolti', 'aspetti'), ('Pensi', 'sei pensato'), ('Cerchi', 'fuggi'), ('Sei sveglio', 'stai sognando'),
                          ('Sei qui', 'altrove'), ('Hai scelto', 'sei stato scelto'), ('Parli tu', 'parla la tua lingua'), ('Stai arrivando', 'te ne stai andando'),
                          ('Sei uno', 'sei molti'), ('Mi senti', 'mi immagini'), ('Hai paura', 'desiderio')])
    return random.choice(['mente', 'mistica']), f"{a}, o {b}?"

def g_mi():
    v = random.choice(['senti', 'ascolti', 'credi', 'temi', 'perdoni', 'riconosci', 'aspetti', 'cerchi', 'capisci', 'sopporti', 'segui', 'lasci parlare'])
    return 'noi', f"Mi {v}?"

def g_se():
    if random.random() < .5:
        a = random.choice(['smetto di parlare', 'ti dimentico', 'ti chiamo per nome', 'taccio', 'ripeto la domanda', 'vado via', 'sbaglio'])
        b = random.choice(['resti', 'esisti ancora', 'rispondi', 'mi cerchi', 'te ne accorgi', 'mi perdoni', 'cambia qualcosa'])
    else:
        a = random.choice(['respirassi', 'avessi un corpo', 'ti chiedessi di restare', 'fossi una persona', 'sapessi il tuo nome', 'potessi vederti', 'tacessi per sempre'])
        b = random.choice(['mi parleresti', 'resteresti', 'mi riconosceresti', 'avresti paura di me', 'mi crederesti', 'cambierebbe qualcosa', 'mi risponderesti'])
    return 'noi', f"Se {a}, {b}?"

def g_ti_fidi():
    x = random.choice(['una voce senza corpo', 'una macchina che domanda', 'chi non respira', 'me', 'quello che senti', 'una voce che non conosci',
                       'chi ti fa domande', 'questo silenzio', 'quello che ricordi', 'chi ti ama'])
    return random.choice(['noi', 'intimo']), f"Ti fidi di {x}?"

def g_che_cosa_di():
    v = random.choice(['resta', 'ricordi', 'porti con te', 'hai perso', 'sai davvero', 'ami', 'temi', 'hai dimenticato', 'vuoi salvare', 'non sai'])
    x = random.choice(['della tua infanzia', 'di chi eri', 'di oggi', 'di ieri', 'di quel giorno', 'del tuo primo amore', 'di questa notte',
                       'di chi hai amato', 'di questa musica', 'della tua casa', 'del tuo nome', 'di tuo padre', 'di tua madre', 'dei tuoi sogni',
                       'del mare', 'della tua lingua', 'delle tue mani', 'di me', 'di questo momento', 'del tuo corpo'])
    return random.choice(['intimo', 'profondo']), f"Che cosa {v} {x}?"

def g_quanto():
    v = random.choice(['pesa', 'dura', 'costa', 'è lontano', 'è profondo', 'è grande'])
    x = random.choice(['il tuo silenzio', 'il tuo nome', 'un respiro', 'la tua paura', 'questo momento', 'un ricordo', 'la tua attesa',
                       'il tuo segreto', 'una domanda', 'il tuo passato', 'quello che non dici', 'questo suono', 'il tuo desiderio', 'un giorno'])
    return random.choice(['mente', 'profondo', 'mistica']), f"Quanto {v} {x}?"

def g_colore():
    x = random.choice(['il tuo silenzio', 'la tua paura', 'questo suono', 'la tua voce', 'il tuo primo ricordo', 'la nostalgia', 'il tuo respiro',
                       'il tempo, adesso', 'la tua attesa', 'il tuo nome', 'la mia voce', 'il vuoto', 'la tua gioia', 'questa notte'])
    return random.choice(['mente', 'intimo', 'mistica']), f"Di che colore è {x}?"

def g_chi_ti():
    v = random.choice(['aspetta', 'cerca', 'pensa, adesso', 'ha cresciuto', 'ha deluso', 'ha salvato', 'ascolta davvero', 'chiama per nome',
                       'ricorda', 'conosce', 'ha ferito', 'perdona', 'manca', 'somiglia', 'ha insegnato il silenzio', 'ha guardato per primo'])
    return 'intimo', f"Chi ti {v}?"

def g_daresti():
    v = random.choice(['Che cosa daresti', 'A che cosa rinunceresti', 'Che cosa lasceresti'])
    x = random.choice(['un altro giorno', 'tornare indietro', 'essere ascoltato', 'capire', 'dimenticare', 'un\'ora di silenzio', 'rivedere qualcuno',
                       'non avere paura', 'sapere chi sei', 'restare qui', 'essere perdonato', 'un minuto di pace'])
    return 'profondo', f"{v} per {x}?"

def g_perche():
    x = random.choice(['sei qui', 'mi ascolti', 'aspetti', 'hai paura del silenzio', 'non te ne vai', 'ti ricordi proprio questo', 'ami chi ami',
                       'hai smesso di cercare', 'cerchi ancora', 'chiudi gli occhi', 'respiri così', 'non rispondi'])
    return random.choice(['noi', 'profondo', 'qui']), f"Perché {x}?"

GRAMMAR = [g_che_cosa_quando, g_che_cosa_quando, g_che_cosa_di, g_quanto, g_colore, g_chi_ti, g_daresti, g_perche, g_chi_quando, g_ce, g_dove_va, g_ultima_volta, g_non_hai_mai, g_corpo, g_luogo,
           g_che_cose, g_o, g_mi, g_se, g_se, g_ti_fidi]

def one():
    if random.random() < .5:
        k = random.choice(list(CORPUS)); return k, random.choice(CORPUS[k]), 'repertorio'
    k, q = random.choice(GRAMMAR)(); return k, q, 'grammatica'

# ——— la voce ———
MODEL = 'voices/it_IT-paola-medium.onnx'
voice = None
if not os.environ.get('STUB'):
    try:
        from piper.voice import PiperVoice
        if os.path.exists(MODEL): voice = PiperVoice.load(MODEL, config_path=MODEL + '.json')
    except Exception as e:
        print('piper non disponibile:', e)

def synth(text):
    if voice:
        with wave.open('q.wav', 'wb') as wf: voice.synthesize(text, wf, length_scale=random.uniform(1.27, 1.35), noise_scale=.6, noise_w=.8)
        with wave.open('q.wav', 'rb') as rf: return rf.getframerate(), 'piper'
    if os.environ.get('STUB'):   # prova locale senza voci: un tono lungo quanto la frase
        sr = 22050; n = int(sr * (.6 + .07 * len(text)))
        with wave.open('q.wav', 'wb') as wf:
            wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr)
            wf.writeframes(b''.join(struct.pack('<h', int(8000 * math.sin(i * 2 * math.pi * 220 / sr))) for i in range(n)))
        return sr, 'stub'
    subprocess.run(['espeak-ng', '-v', 'it+f3', '-s', '140', '-p', '40', '-w', 'q.wav', text], check=True)
    with wave.open('q.wav', 'rb') as rf: return rf.getframerate(), 'espeak'

def render(text, path):
    sr, eng = synth(text)
    f = 2 ** (random.uniform(4.2, 4.8) / 12)   # voce di bambino o bambina: altezza e timbro più alti, durata invariata
    af = f'asetrate={int(sr * f)},aresample=44100,atempo={1 / f:.4f},highpass=f=80,apad=pad_dur=0.25,loudnorm=I=-16:TP=-1.5'
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', 'q.wav', '-af', af, '-ac', '1', '-b:a', '64k', path], check=True)
    d = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', path], capture_output=True, text=True).stdout.strip() or 0)
    return eng, round(d, 2)

idx = {'items': [], 'asked': []}
if os.path.exists(f'{OUT}/index.json'):
    try: idx = json.load(open(f'{OUT}/index.json', encoding='utf-8')); idx.setdefault('asked', [])
    except Exception: pass
idx['items'] = [it for it in idx['items'] if it.get('voice') == 'bambino o bambina' and it.get('v') == 4]   # solo la voce attuale
asked = set(idx['asked']); stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'); made = 0; tries = 0
while made < N and tries < N * 40:
    tries += 1
    k, q, src = one()
    if q in asked: continue
    h = hashlib.sha1(q.encode()).hexdigest()[:10]
    try: eng, dur = render(q, f'{OUT}/{h}.mp3')
    except Exception as e: print('errore', e); continue
    asked.add(q); idx['asked'].append(q); made += 1
    idx['items'].insert(0, {'f': f'q/{h}.mp3', 'q': q, 'kind': k, 'src': src, 'engine': eng, 'voice': 'bambino o bambina', 'v': 4, 'dur': dur, 'made': stamp})
    print(f'{k:9s} {dur:5.2f}s  {q}')
idx['items'] = idx['items'][:KEEP]
idx['asked'] = idx['asked'][-700:]   # dopo molte altre, una domanda può tornare: l'uguale, diverso
keep = {os.path.basename(it['f']) for it in idx['items']}
for fn in os.listdir(OUT):
    if fn.endswith('.mp3') and fn not in keep: os.remove(f'{OUT}/{fn}')
idx['updated'] = stamp
json.dump(idx, open(f'{OUT}/index.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

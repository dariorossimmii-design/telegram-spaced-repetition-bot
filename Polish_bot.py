import telebot
import json
import os
import random
import unicodedata
from telebot.types import ReplyKeyboardMarkup, ReplyKeyboardRemove

# INSERISCI QUI IL TUO TOKEN
TOKEN = 'INSERT_TOKEN_HERE'
bot = telebot.TeleBot(TOKEN)

CSV_FILE = "vocaboli_pl.csv"
PROGRESS_FILE = "progress.json"

sessions = {}

def load_data():
    vocab_db = {}
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip(): continue
                parts = line.strip().split(",")
                if len(parts) >= 3:
                    pl, lezione = parts[0].strip(), parts[-1].strip()
                    it = ",".join(parts[1:-1]).strip()
                    vocab_db[pl] = {"it": it, "level": 0, "lezione": lezione}

    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            progress_data = json.load(f)
            for pl, data in progress_data.items():
                if pl in vocab_db:
                    vocab_db[pl]["level"] = data.get("level", 0)
    return vocab_db

def save_progress(vocab_db):
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(vocab_db, f, indent=4, ensure_ascii=False)

def remove_diacritics(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')

def check_answer_strict(user_input, correct_answer):
    user_input, correct_answer = user_input.lower().strip(), correct_answer.lower().strip()
    if user_input == correct_answer: return True, "corretto"
    if remove_diacritics(user_input) == remove_diacritics(correct_answer): return False, "diacritici"
    return False, "errato"

@bot.message_handler(commands=['start', 'quiz'])
def start_quiz(message):
    db = load_data()
    if not db:
        bot.send_message(message.chat.id, "Nessun database trovato.")
        return

    lezioni_uniche = list(set(v["lezione"] for v in db.values()))
    lezioni_disp = sorted(lezioni_uniche, key=lambda x: (0, int(x)) if x.isdigit() else (1, x))

    msg = bot.send_message(
        message.chat.id,
        f"Lezioni disponibili: {', '.join(lezioni_disp)}\n\nQuali vuoi ripassare? (es. 1, 1,3 oppure tutte)",
        reply_markup=ReplyKeyboardRemove()
    )
    bot.register_next_step_handler(msg, process_lesson, db)

def process_lesson(message, db):
    scelta = message.text.strip().lower()

    if not scelta or scelta == 'tutte':
        selected = list(db.keys())
    else:
        scelte = [s.strip() for s in scelta.split(',')]
        selected = [pl for pl, data in db.items() if data["lezione"] in scelte]

    if not selected:
        bot.send_message(message.chat.id, "Lezione non trovata. Scrivi /quiz per riprovare.")
        return

    markup = ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    markup.add("Sì", "No")
    msg = bot.send_message(message.chat.id, "Vuoi includere la scelta multipla per i termini nuovi?", reply_markup=markup)
    bot.register_next_step_handler(msg, setup_session, db, selected)

def setup_session(message, db, selected):
    skip_mcq = (message.text.strip().lower() == 'no')

    sessions[message.chat.id] = {
        "db": db, "selected": selected, "skip_mcq": skip_mcq
    }

    start_new_round(message.chat.id)

def start_new_round(chat_id):
    session = sessions[chat_id]
    db = session["db"]
    selected = session["selected"]

    to_study = {k: db[k] for k in selected if db[k]["level"] < 3}

    if not to_study:
        bot.send_message(chat_id, "Obiettivo raggiunto per questa selezione! 🎉\nScrivi /quiz per ripassare altre lezioni.", reply_markup=ReplyKeyboardRemove())
        return

    batch = list(to_study.items())
    random.shuffle(batch)
    batch = batch[:15]

    session["batch"] = batch
    session["current_idx"] = 0
    session["last_pl"] = None

    bot.send_message(chat_id, f"--- Inizio round ({len(batch)} vocaboli) ---\nScrivi 'q' per uscire.", reply_markup=ReplyKeyboardRemove())
    ask_next_word(chat_id)

def ask_next_word(chat_id):
    session = sessions.get(chat_id)
    if not session or session["current_idx"] >= len(session["batch"]):
        if session: save_progress(session["db"])

        # Invece di fermarsi, chiede se vuoi continuare con le stesse lezioni
        markup = ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
        markup.add("Sì", "No")
        msg = bot.send_message(chat_id, "Round completato! Dati salvati.\nVuoi fare un altro round con queste lezioni?", reply_markup=markup)
        bot.register_next_step_handler(msg, handle_next_round)
        return

    pl, data = session["batch"][session["current_idx"]]
    session["last_pl"] = pl

    if data["level"] == 0 and not session["skip_mcq"]:
        options = random.sample([k for k in session["db"].keys() if k != pl], min(3, len(session["db"])-1)) + [pl]
        random.shuffle(options)

        markup = ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
        for opt in options: markup.add(opt)

        msg = bot.send_message(chat_id, f"Traduci (Liv. 0/3): {data['it']}", reply_markup=markup)
        bot.register_next_step_handler(msg, check_mcq)
    else:
        msg = bot.send_message(chat_id, f"Traduci in polacco (Liv. {data['level']}/3): {data['it']}", reply_markup=ReplyKeyboardRemove())
        bot.register_next_step_handler(msg, check_typing)

def handle_next_round(message):
    chat_id = message.chat.id
    if message.text.strip().lower() == 'sì':
        start_new_round(chat_id)
    else:
        bot.send_message(chat_id, "Sessione terminata. Ottimo lavoro!\nScrivi /quiz quando vorrai ricominciare.", reply_markup=ReplyKeyboardRemove())

def check_mcq(message):
    chat_id = message.chat.id
    if message.text.lower() == 'q':
        save_progress(sessions[chat_id]["db"])
        bot.send_message(chat_id, "Sessione interrotta e salvata.", reply_markup=ReplyKeyboardRemove())
        return

    session = sessions[chat_id]
    pl = session["last_pl"]

    if message.text.strip() == pl:
        bot.send_message(chat_id, "🟢 Corretto.")
        session["db"][pl]["level"] += 1
    else:
        bot.send_message(chat_id, f"🔴 Errato. La risposta era: {pl}")

    session["current_idx"] += 1
    ask_next_word(chat_id)

def check_typing(message):
    chat_id = message.chat.id
    if message.text.lower() == 'q':
        save_progress(sessions[chat_id]["db"])
        bot.send_message(chat_id, "Sessione interrotta e salvata.")
        return

    session = sessions[chat_id]
    pl = session["last_pl"]

    is_exact, status = check_answer_strict(message.text, pl)
    if is_exact:
        bot.send_message(chat_id, "🟢 Corretto.")
        session["db"][pl]["level"] += 1
        session["current_idx"] += 1
        ask_next_word(chat_id)
    else:
        if status == "diacritici":
            bot.send_message(chat_id, f"🟠 Errore sui diacritici! Scritto: '{message.text}', Esatto: '{pl}'")
        else:
            bot.send_message(chat_id, f"🔴 Errato. Esatto: {pl}")

        session["db"][pl]["level"] = 0

        markup = ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
        markup.add("S", "No")
        msg = bot.send_message(chat_id, "Premi 'S' se era un typo per forzare la correttezza, altrimenti 'No'.", reply_markup=markup)
        bot.register_next_step_handler(msg, check_override)

def check_override(message):
    chat_id = message.chat.id
    session = sessions[chat_id]
    pl = session["last_pl"]

    if message.text.strip().lower() == 's':
        session["db"][pl]["level"] += 1
        bot.send_message(chat_id, "✅ Forzatura applicata.")

    session["current_idx"] += 1
    ask_next_word(chat_id)
# --- NUOVA SEZIONE: AGGIUNTA VOCABOLI A CICLO CONTINUO ---

@bot.message_handler(commands=['aggiungi', 'add'])
def start_add_vocab(message):
    """Avvia la procedura per inserire più vocaboli in una singola lezione."""
    msg = bot.send_message(
        message.chat.id,
        "📝 **Inserimento nuovi vocaboli**\n\nA quale **lezione** vuoi aggiungerli? (es. 20, 21, extra):",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )
    bot.register_next_step_handler(msg, process_add_lesson)

def process_add_lesson(message):
    chat_id = message.chat.id
    lezione = message.text.strip()

    if lezione.lower() == 'q':
        bot.send_message(chat_id, "Operazione annullata.")
        return

    sessions[chat_id] = {"add_lesson": lezione}

    msg = bot.send_message(
        chat_id,
        f"Perfetto, aggiungiamo alla lezione **{lezione}**.\n\nScrivi il termine in **polacco**:\n*(Oppure digita 'q' in qualsiasi momento per terminare l'inserimento)*",
        parse_mode="Markdown"
    )
    bot.register_next_step_handler(msg, process_add_pl)

def process_add_pl(message):
    chat_id = message.chat.id
    pl = message.text.strip()

    # Condizione di uscita dal loop
    if pl.lower() == 'q':
        bot.send_message(chat_id, "Inserimento terminato. Usa /quiz per studiare.")
        return

    # --- CONTROLLO DUPLICATI ---
    db = load_data()
    duplicato = None

    # Cerca la parola nel database ignorando le maiuscole/minuscole
    for parola_esistente in db.keys():
        if parola_esistente.lower() == pl.lower():
            duplicato = parola_esistente
            break

    if duplicato:
        dati = db[duplicato]
        msg = bot.send_message(
            chat_id,
            f"⚠️ **Attenzione!**\nIl termine **{duplicato}** esiste già nella **Lezione {dati['lezione']}** (Traduzione: *{dati['it']}*).\n\nScrivi un **altro termine in polacco** (oppure 'q' per chiudere):",
            parse_mode="Markdown"
        )
        # Rimanda l'utente a inserire una nuova parola polacca
        bot.register_next_step_handler(msg, process_add_pl)
        return
    # ---------------------------

    sessions[chat_id]["new_pl"] = pl

    msg = bot.send_message(chat_id, f"Scrivi la traduzione in **italiano** per '{pl}':", parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_add_it)

def process_add_it(message):
    chat_id = message.chat.id
    it = message.text.strip()

    if it.lower() == 'q':
        bot.send_message(chat_id, "Inserimento terminato. Usa /quiz per studiare.")
        return

    pl = sessions[chat_id].get("new_pl")
    lezione = sessions[chat_id].get("add_lesson")

    try:
        # Salvataggio nel file CSV
        with open(CSV_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n{pl},{it},{lezione}")

        # Messaggio di conferma e riavvio del loop per il termine successivo
        msg = bot.send_message(
            chat_id,
            f"✅ Salvato: **{pl}** = **{it}**\n\nScrivi il **prossimo termine in polacco** (oppure 'q' per chiudere):",
            parse_mode="Markdown"
        )

        # Qui avviene la magia del loop: rimandiamo la funzione a process_add_pl
        bot.register_next_step_handler(msg, process_add_pl)

    except Exception as e:
        bot.send_message(chat_id, f"Errore durante il salvataggio: {e}")
# --- NUOVA SEZIONE: RESET DEI PROGRESSI ---

@bot.message_handler(commands=['reset'])
def confirm_reset(message):
    """Chiede conferma prima di azzerare il file dei progressi."""
    markup = ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    markup.add("Sì, azzera tutto", "Annulla")

    msg = bot.send_message(
        message.chat.id,
        "⚠️ **ATTENZIONE** ⚠️\nVuoi davvero azzerare tutti i tuoi progressi? Tutti i vocaboli torneranno al Livello 0.\n\nQuesta azione non è reversibile.",
        reply_markup=markup,
        parse_mode="Markdown"
    )
    bot.register_next_step_handler(msg, execute_reset)

def execute_reset(message):
    chat_id = message.chat.id
    risposta = message.text.strip()

    if risposta == "Sì, azzera tutto":
        try:
            if os.path.exists(PROGRESS_FILE):
                os.remove(PROGRESS_FILE)
            bot.send_message(
                chat_id,
                "🗑️ **Progressi azzerati con successo.**\nTutti i vocaboli sono tornati al Livello 0. Scrivi /quiz per ricominciare.",
                reply_markup=ReplyKeyboardRemove(),
                parse_mode="Markdown"
            )
        except Exception as e:
            bot.send_message(chat_id, f"Errore durante l'eliminazione: {e}", reply_markup=ReplyKeyboardRemove())
    else:
        bot.send_message(
            chat_id,
            "Operazione annullata. I tuoi progressi sono salvi.",
            reply_markup=ReplyKeyboardRemove()
        )
if __name__ == "__main__":
    print("Bot in ascolto... Premi Ctrl+C nel terminale per spegnerlo.")
    bot.infinity_polling()
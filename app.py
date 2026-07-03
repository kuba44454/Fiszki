import streamlit as st
import streamlit.components.v1 as components
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import io
import random

# Konfiguracja strony
st.set_page_config(page_title="Fiszki Navigator", layout="centered")

# Inicjalizacja połączenia z Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    try:
        return conn.read(ttl=0)
    except Exception:
        return pd.DataFrame(columns=["Jezyk", "Kategoria", "Front", "Back", "Przyklad"])

df = load_data()

# Inicjalizacja bazy błędnych słówek w pamięci sesji
if "failed_cards" not in st.session_state:
    st.session_state.failed_cards = set()

# --- PANEL BOCZNY (SIDEBAR) ---
st.sidebar.header("🧭 Nawigacja")
mode = st.sidebar.radio("Wybierz moduł:", ["Nauka", "Quiz (Wybór)", "🔍 Słownik", "Import masowy CSV"])

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Ustawienia Globalne")
swap_sides = st.sidebar.checkbox(
    "🔄 Zamień Front ↔ Rewers", 
    value=False, 
    help="Wyświetla polskie tłumaczenie jako pytanie."
)

# --- FUNKCJA GENERUJĄCA WYMOWĘ OFFLINE (HTML5 TTS) ---
def render_tts_button(text_to_speak, language_name):
    lang_code = "nl-NL"
    if "niem" in str(language_name).lower():
        lang_code = "de-DE"
    
    # Bezpieczne parsowanie apostrofów do JavaScript
    safe_text = text_to_speak.replace("'", "\\'")
    
    tts_html = f"""
    <button onclick="talk()" style="width:100%; background-color:#262730; color:#FAFAFA; border:1px solid #46464d; border-radius:4px; padding:0.5rem; font-size:1rem; cursor:pointer; margin-bottom:15px;">🔊 Odsłuchaj wymowę</button>
    <script>
    function talk() {{
        if ('speechSynthesis' in window) {{
            var msg = new SpeechSynthesisUtterance('{safe_text}');
            msg.lang = '{lang_code}';
            window.speechSynthesis.speak(msg);
        }} else {{
            alert('Twoja przeglądarka nie obsługuje wymowy offline.');
        }}
    }}
    </script>
    """
    components.html(tts_html, height=55)

# --- MODUŁ: IMPORT MASOWY CSV ---
if mode == "Import masowy CSV":
    st.header("📥 Masowy import fiszek z CSV")
    st.write("Wklej tekst CSV. Wymagany format: `Jezyk,Kategoria,Front,Back,Przyklad` z nagłówkiem.")
    
    demo_csv = "Jezyk,Kategoria,Front,Back,Przyklad\nNiemiecki,Nawigacja,Der Pegel,Stan wody,Der Pegel ist heute sehr niedrig.\nNiderlandzki,Sluzy,De Sluis,Śluza,We varen de sluis binnen."
    csv_input = st.text_area("Dane CSV:", value=demo_csv, height=250)
    
    if st.button("Zapisz do Google Sheets", type="primary"):
        try:
            new_data = pd.read_csv(io.StringIO(csv_input.strip()))
            required_cols = ["Jezyk", "Kategoria", "Front", "Back", "Przyklad"]
            if not all(col in new_data.columns for col in required_cols):
                st.error("Błąd: CSV musi zawierać kolumny: Jezyk, Kategoria, Front, Back, Przyklad")
            else:
                if df.empty or df.dropna(how='all').empty:
                    updated_df = new_data
                else:
                    updated_df = pd.concat([df, new_data], ignore_index=True)
                conn.update(data=updated_df)
                st.success(f"Pomyślnie zaimportowano {len(new_data)} nowych fiszek!")
                st.rerun()
        except Exception as e:
            st.error(f"Błąd parsowania pliku: {e}")

# --- MODUŁ: SŁOWNIK (WYSZUKIWARKA) ---
elif mode == "🔍 Słownik":
    st.header("🔍 Uniwersalny Mini-Słownik")
    st.write("Przeszukuj całą swoją bazę słówek natychmiastowo.")
    
    search_query = st.text_input("Wpisz szukane słowo, kategorię lub frazę ze zdania:")
    
    if search_query:
        # Filtrowanie po wszystkich kolumnach tekstowych (case insensitive)
        results = df[
            df['Front'].str.contains(search_query, case=False, na=False) |
            df['Back'].str.contains(search_query, case=False, na=False) |
            df['Przyklad'].str.contains(search_query, case=False, na=False) |
            df['Kategoria'].str.contains(search_query, case=False, na=False)
        ]
        
        if not results.empty:
            st.success(f"Znaleziono {len(results)} dopasowań:")
            for _, row in results.iterrows():
                with st.expander(f"🌐 {row['Jezyk']} | 🗂️ {row['Kategoria']} | **{row['Front']}** — {row['Back']}"):
                    st.markdown(f"**Zdanie przykładowe:** *{row['Przyklad']}*")
                    # Przycisk wymowy bezpośrednio w wyszukiwarce słownika
                    render_tts_button(row['Front'], row['Jezyk'])
        else:
            st.info("Brak wyników w bazie danych dla podanej frazy.")

# --- MODUŁ: QUIZ (WYBÓR WIELOKROTNY) ---
elif mode == "Quiz (Wybór)":
    st.header("🧠 Quiz wielokrotnego wyboru")
    
    if df.empty or df.dropna(how='all').empty:
        st.warning("Baza fiszek jest pusta.")
    else:
        languages = df["Jezyk"].dropna().unique().tolist()
        selected_lang = st.sidebar.selectbox("Quiz - Język:", languages, key="quiz_lang")
        lang_filtered_df = df[df["Jezyk"] == selected_lang]
        
        categories = lang_filtered_df["Kategoria"].dropna().unique().tolist()
        selected_category = st.selectbox("Quiz - Kategoria:", categories, key="quiz_cat")
        
        final_df = lang_filtered_df[lang_filtered_df["Kategoria"] == selected_category].reset_index(drop=True)
        
        if len(final_df) < 2:
            st.info("Dodaj więcej słówek do tej kategorii, aby móc uruchomić quiz.")
        else:
            state_key = f"quiz_{selected_lang}_{selected_category}_{swap_sides}"
            
            # Inicjalizacja stanu quizu
            if "quiz_index" not in st.session_state or st.session_state.get("quiz_state_key") != state_key:
                st.session_state.quiz_index = 0
                st.session_state.quiz_score = 0
                st.session_state.quiz_state_key = state_key
                st.session_state.quiz_answered = False
                st.session_state.quiz_options = []

            q_idx = st.session_state.quiz_index
            if q_idx >= len(final_df):
                st.balloons()
                st.success(f"🏆 Koniec quizu! Twój wynik to: {st.session_state.quiz_score} / {len(final_df)}")
                if st.button("Zacznij od nowa"):
                    st.session_state.quiz_index = 0
                    st.session_state.quiz_score = 0
                    st.session_state.quiz_answered = False
                    st.session_state.quiz_options = []
                    st.rerun()
            else:
                current_card = final_df.iloc[q_idx]
                
                # Ustalenie pytania i poprawnej odpowiedzi na podstawie flagi swap
                question_word = current_card['Back'] if swap_sides else current_card['Front']
                correct_answer = current_card['Front'] if swap_sides else current_card['Back']
                
                # Generowanie opcji wielokrotnego wyboru (tylko raz dla pytania)
                if not st.session_state.quiz_answered and not st.session_state.quiz_options:
                    pool = final_df['Front' if swap_sides else 'Back'].dropna().unique().tolist()
                    if len(pool) < 4: # Jeśli w kategorii mało słówek, dobieramy z całego języka
                        pool = lang_filtered_df['Front' if swap_sides else 'Back'].dropna().unique().tolist()
                    
                    pool = [ans for ans in pool if ans != correct_answer]
                    wrong_answers = random.sample(pool, min(3, len(pool)))
                    
                    options = wrong_answers + [correct_answer]
                    random.shuffle(options)
                    st.session_state.quiz_options = options

                # Wyświetlenie pytania
                st.subheader(f"Pytanie {q_idx + 1} z {len(final_df)} (Wynik: {st.session_state.quiz_score})")
                st.markdown(f"""
                <div style="background-color: #1E1E1E; padding: 30px; border-radius: 10px; border: 1px solid #444; text-align: center; margin-bottom: 20px;">
                    <span style="color: #888; font-size: 13px;">JAK TO PRZETŁUMACZYSZ?</span>
                    <h2 style="color: #FFF; margin-top: 10px;">{question_word}</h2>
                </div>
                """, unsafe_allow_html=True)
                
                # Wyświetlanie opcji jako przyciski pionowe
                for option in st.session_state.quiz_options:
                    if not st.session_state.quiz_answered:
                        if st.button(option, use_container_width=True):
                            st.session_state.quiz_answered = True
                            st.session_state.quiz_user_choice = option
                            if option == correct_answer:
                                st.session_state.quiz_score += 1
                            st.rerun()
                    else:
                        # Po udzieleniu odpowiedzi pokazujemy rezultaty kolorami tekstu
                        if option == correct_answer:
                            st.write(f"🍏 **{option}** (Poprawna odpowiedź)")
                        elif option == st.session_state.quiz_user_choice:
                            st.write(f"🍎 **{option}** (Twoja błędna odpowiedź)")
                        else:
                            st.write(f"⚪ {option}")
                
                if st.session_state.quiz_answered:
                    st.markdown("---")
                    if st.session_state.quiz_user_choice == correct_answer:
                        st.success("Dobrze! Dodatkowy punkt.")
                    else:
                        st.error(f"Pudło! Poprawna odpowiedź to: {correct_answer}")
                        
                    # Pokazujemy kontekst zdania na koniec pytania
                    st.info(f"Kontekst: {current_card['Przyklad']}")
                    
                    if st.button("Dalej ➡️", type="primary", use_container_width=True):
                        st.session_state.quiz_index += 1
                        st.session_state.quiz_answered = False
                        st.session_state.quiz_options = []
                        st.rerun()

# --- MODUŁ: NAUKA ---
else:
    st.header("🗂️ Panel Nauki")
    only_errors = st.sidebar.checkbox("❌ Ucz się tylko błędów", value=False)
    
    if df.empty or df.dropna(how='all').empty:
        st.warning("Baza fiszek jest pusta.")
    else:
        languages = df["Jezyk"].dropna().unique().tolist()
        selected_lang = st.sidebar.selectbox("Wybierz język:", languages)
        lang_filtered_df = df[df["Jezyk"] == selected_lang]
        
        categories = lang_filtered_df["Kategoria"].dropna().unique().tolist()
        selected_category = st.selectbox("Wybierz kategorię do nauki:", categories)
        
        final_df = lang_filtered_df[lang_filtered_df["Kategoria"] == selected_category].reset_index(drop=True)
        if only_errors:
            final_df = final_df[final_df["Front"].isin(st.session_state.failed_cards)].reset_index(drop=True)
        
        st.sidebar.info(f"Wszystkich błędów w pamięci: {len(st.session_state.failed_cards)}")

        if final_df.empty:
            if only_errors:
                st.success("🎉 Brak błędów do powtórzenia w tej sekcji!")
            else:
                st.info("Brak fiszek spełniających kryteria.")
        else:
            state_key = f"state_{selected_lang}_{selected_category}_{only_errors}"
            if "current_state_key" not in st.session_state or st.session_state.current_state_key != state_key:
                st.session_state.flashcard_index = 0
                st.session_state.current_state_key = state_key
                st.session_state.show_back = False

            idx = st.session_state.flashcard_index
            if idx >= len(final_df):
                idx = 0
                st.session_state.flashcard_index = 0

            # Spis treści
            word_options = [f"{i+1}. {row['Back'] if swap_sides else row['Front']}" for i, row in final_df.iterrows()]
            chosen_word_str = st.selectbox("📋 Skocz do słówka z listy:", word_options, index=idx)
            
            chosen_idx = word_options.index(chosen_word_str)
            if chosen_idx != idx:
                st.session_state.flashcard_index = chosen_idx
                st.session_state.show_back = False
                st.rerun()

            current_card = final_df.iloc[st.session_state.flashcard_index]
            card_id = current_card['Front']
            
            card_front = current_card['Back'] if swap_sides else current_card['Front']
            card_back = current_card['Front'] if swap_sides else current_card['Back']
            
            # INTERFEJS TTS DLA MODUŁU NAUKI (Wymowa obcojęzycznego wyrazu)
            render_tts_button(current_card['Front'], selected_lang)

            example_sentence = current_card['Przyklad'] if pd.notna(current_card['Przyklad']) else "Brak zdania."
            example_html = f"""
            <div style="border-top: 1px dashed #444; padding-top: 20px; margin-top: 20px;">
                <p style="color: #CCC; font-style: italic; font-size: 16px;">"{example_sentence}"</p>
            </div>
            """
            front_extra_html = example_html if not swap_sides else ""
            back_extra_html = example_html if swap_sides else ""
            is_failed = "⚠️ Pula błędów" if card_id in st.session_state.failed_cards else ""

            # Renderowanie frontu
            st.markdown(f"""
            <div style="background-color: #1E1E1E; padding: 40px; border-radius: 10px; border: 1px solid #444; text-align: center; margin-bottom: 20px;">
                <span style="color: #FF6B6B; font-size: 11px; font-weight: bold; float: right;">{is_failed}</span>
                <span style="color: #888; font-size: 13px;">FRONT</span>
                <h2 style="color: #FFF; margin-top: 15px; font-size: 32px;">{card_front}</h2>
                {front_extra_html}
            </div>
            """, unsafe_allow_html=True)
            
            # Rewers
            if st.session_state.show_back:
                st.markdown(f"""
                <div style="background-color: #2D3748; padding: 40px; border-radius: 10px; border: 1px solid #4A5568; text-align: center; margin-bottom: 20px;">
                    <span style="color: #CBD5E0; font-size: 13px;">REWERS</span>
                    <h2 style="color: #63B3ED; margin-top: 15px; font-size: 30px;">{card_back}</h2>
                    {back_extra_html}
                </div>
                """, unsafe_allow_html=True)
            
            # System oceniania
            col_bad, col_good = st.columns(2)
            with col_bad:
                if st.button("❌ Nie umiem", use_container_width=True):
                    st.session_state.failed_cards.add(card_id)
                    st.session_state.flashcard_index = (st.session_state.flashcard_index + 1) % len(final_df)
                    st.session_state.show_back = False
                    st.rerun()
            with col_good:
                if st.button("✅ Umiem", use_container_width=True, type="primary"):
                    if card_id in st.session_state.failed_cards:
                        st.session_state.failed_cards.remove(card_id)
                    st.session_state.flashcard_index = (st.session_state.flashcard_index + 1) % len(final_df)
                    st.session_state.show_back = False
                    st.rerun()

            st.markdown("---")
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("👁️ Pokaż/Ukryj", use_container_width=True):
                    st.session_state.show_back = not st.session_state.show_back
                    st.rerun()
            with col2:
                if st.button("➡️ Następna", use_container_width=True):
                    st.session_state.flashcard_index = (st.session_state.flashcard_index + 1) % len(final_df)
                    st.session_state.show_back = False
                    st.rerun()
            with col3:
                if st.button("🎲 Losuj", use_container_width=True):
                    st.session_state.flashcard_index = random.randint(0, len(final_df) - 1)
                    st.session_state.show_back = False
                    st.rerun()

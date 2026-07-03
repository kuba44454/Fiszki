import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import io
import random

# Konfiguracja strony
st.set_page_config(page_title="Fiszki Navigator", layout="centered")

# Inicjalizacja połączenia z Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

# Funkcja do bezpiecznego pobierania danych
def load_data():
    try:
        # ttl=0 wymusza pobranie świeżych danych przy każdym przeładowaniu
        return conn.read(ttl=0)
    except Exception:
        # Jeśli arkusz jest pusty, tworzymy domyślny DataFrame
        return pd.DataFrame(columns=["Kategoria", "Front", "Back"])

df = load_data()

# Menu nawigacyjne w sidebarze
mode = st.sidebar.radio("Nawigacja", ["Nauka", "Import masowy CSV"])

# --- MODUŁ: IMPORT MASOWY CSV ---
if mode == "Import masowy CSV":
    st.header("📥 Masowy import fiszek z CSV")
    st.write("Wklej poniżej wygenerowany przez LLM tekst CSV. Wymagany format: `Kategoria,Front,Back` z nagłówkiem.")
    
    # Przykładowy szablon dla użytkownika
    demo_csv = "Kategoria,Front,Back\nNawigacja,Der Pegel,Poziom wody\nNawigacja,Die Schleuse,Śluza"
    csv_input = st.text_area("Dane CSV:", value=demo_csv, height=250)
    
    if st.button("Zapisz do Google Sheets", type="primary"):
        try:
            # Parsowanie tekstu do DataFrame
            new_data = pd.read_csv(io.StringIO(csv_input.strip()))
            
            # Walidacja kolumn
            required_cols = ["Kategoria", "Front", "Back"]
            if not all(col in new_data.columns for col in required_cols):
                st.error("Błąd: CSV musi zawierać kolumny: Kategoria, Front, Back")
            else:
                # Łączenie starych danych z nowymi
                if df.empty or df.dropna(how='all').empty:
                    updated_df = new_data
                else:
                    updated_df = pd.concat([df, new_data], ignore_index=True)
                
                # Aktualizacja bazy w chmurze Google
                conn.update(data=updated_df)
                st.success(f"Pomyślnie zaimportowano {len(new_data)} nowych fiszek!")
                st.rerun()
        except Exception as e:
            st.error(f"Błąd parsowania pliku: {e}")

# --- MODUŁ: NAUKA ---
else:
    st.header("🗂️ Panel Nauki")
    
    if df.empty or df.dropna(how='all').empty:
        st.warning("Baza fiszek jest pusta. Przejdź do zakładki 'Import masowy CSV', aby dodać pierwsze pozycje.")
    else:
        # Filtrowanie unikalnych kategorii
        categories = df["Kategoria"].dropna().unique().tolist()
        selected_category = st.selectbox("Wybierz kategorię do nauki:", categories)
        
        # Filtrowanie fiszek z wybranej kategorii
        filtered_df = df[df["Kategoria"] == selected_category].reset_index(drop=True)
        
        if filtered_df.empty:
            st.info("Brak fiszek w tej kategorii.")
        else:
            st.write(f"Dostępnych fiszek w kategorii: {len(filtered_df)}")
            
            # Zarządzanie indeksem aktywnej fiszki w stanie sesji Streamlit
            if "flashcard_index" not in st.session_state or st.session_state.get("prev_category") != selected_category:
                st.session_state.flashcard_index = 0
                st.session_state.prev_category = selected_category
                st.session_state.show_back = False

            idx = st.session_state.flashcard_index
            
            # Zabezpieczenie przed wyjściem poza indeks po usunięciu danych
            if idx >= len(filtered_df):
                idx = 0
                st.session_state.flashcard_index = 0

            # Renderowanie karty (Front)
            current_card = filtered_df.iloc[idx]
            
            st.markdown(f"""
            <div style="background-color: #1E1E1E; padding: 40px; border-radius: 10px; border: 1px solid #444; text-align: center; margin-bottom: 20px;">
                <span style="color: #888; font-size: 14px;">FRONT</span>
                <h2 style="color: #FFF; margin-top: 10px;">{current_card['Front']}</h2>
            </div>
            """, unsafe_allow_html=True)
            
            # Renderowanie rewersu (Back) po kliknięciu
            if st.session_state.show_back:
                st.markdown(f"""
                <div style="background-color: #2D3748; padding: 40px; border-radius: 10px; border: 1px solid #4A5568; text-align: center; margin-bottom: 20px;">
                    <span style="color: #CBD5E0; font-size: 14px;">REWERS (TŁUMACZENIE)</span>
                    <h2 style="color: #63B3ED; margin-top: 10px;">{current_card['Back']}</h2>
                </div>
                """, unsafe_allow_html=True)
            
            # Przyciski sterujące
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("👁️ Pokaż / Ukryj odpowiedź", use_container_width=True):
                    st.session_state.show_back = not st.session_state.show_back
                    st.rerun()
                    
            with col2:
                if st.button("➡️ Następna fiszka", use_container_width=True):
                    st.session_state.flashcard_index = (idx + 1) % len(filtered_df)
                    st.session_state.show_back = False
                    st.rerun()
                    
            with col3:
                if st.button("🎲 Losuj fiszkę", use_container_width=True):
                    st.session_state.flashcard_index = random.randint(0, len(filtered_df) - 1)
                    st.session_state.show_back = False
                    st.rerun()

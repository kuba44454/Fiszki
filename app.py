import streamlit as st
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

# Menu nawigacyjne w sidebarze
mode = st.sidebar.radio("Nawigacja", ["Nauka", "Import masowy CSV"])

# --- MODUŁ: IMPORT MASOWY CSV ---
if mode == "Import masowy CSV":
    st.header("📥 Masowy import fiszek z CSV")
    st.write("Wklej tekst CSV. Wymagany format: `Jezyk,Kategoria,Front,Back,Przyklad` z nagłówkiem.")
    
    # Przykładowy szablon dla użytkownika
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

# --- MODUŁ: NAUKA ---
else:
    st.header("🗂️ Panel Nauki")
    
    if df.empty or df.dropna(how='all').empty:
        st.warning("Baza fiszek jest pusta. Przejdź do zakładki 'Import masowy CSV'.")
    else:
        # 1. Filtrowanie Języka w Sidebarze
        languages = df["Jezyk"].dropna().unique().tolist()
        selected_lang = st.sidebar.selectbox("Wybierz język:", languages)
        
        # Odfiltrowanie danych tylko dla wybranego języka
        lang_filtered_df = df[df["Jezyk"] == selected_lang]
        
        # 2. Dynamiczne wyciąganie kategorii dla wybranego języka
        categories = lang_filtered_df["Kategoria"].dropna().unique().tolist()
        selected_category = st.selectbox("Wybierz kategorię do nauki:", categories)
        
        # Ostateczne odfiltrowanie danych (Język + Kategoria)
        final_df = lang_filtered_df[lang_filtered_df["Kategoria"] == selected_category].reset_index(drop=True)
        
        if final_df.empty:
            st.info("Brak fiszek spełniających kryteria.")
        else:
            st.write(f"Dostępnych fiszek: {len(final_df)}")
            
            # Reset indeksu przy zmianie języka lub kategorii
            state_key = f"prev_state_{selected_lang}_{selected_category}"
            if "current_state_key" not in st.session_state or st.session_state.current_state_key != state_key:
                st.session_state.flashcard_index = 0
                st.session_state.current_state_key = state_key
                st.session_state.show_back = False

            idx = st.session_state.flashcard_index
            
            if idx >= len(final_df):
                idx = 0
                st.session_state.flashcard_index = 0

            current_card = final_df.iloc[idx]
            
            # Wyświetlanie przykładu (obsługa pustych komórek w pandas)
            example_sentence = current_card['Przyklad'] if pd.notna(current_card['Przyklad']) else "Brak zdania przykładowego."
            
            # Renderowanie FRONTU wraz ze zdaniem przykładowym
            st.markdown(f"""
            <div style="background-color: #1E1E1E; padding: 40px; border-radius: 10px; border: 1px solid #444; text-align: center; margin-bottom: 20px;">
                <span style="color: #888; font-size: 13px; tracking-spacing: 1px;">FRONT • {selected_lang.upper()}</span>
                <h2 style="color: #FFF; margin-top: 15px; margin-bottom: 25px; font-size: 32px;">{current_card['Front']}</h2>
                <div style="border-top: 1px dashed #444; padding-top: 20px; margin-top: 20px;">
                    <span style="color: #666; font-size: 12px; display: block; margin-bottom: 5px;">Zastosowanie w zdaniu:</span>
                    <p style="color: #CCC; font-style: italic; font-size: 16px; line-height: 1.5;">"{example_sentence}"</p>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Renderowanie REWERSU
            if st.session_state.show_back:
                st.markdown(f"""
                <div style="background-color: #2D3748; padding: 40px; border-radius: 10px; border: 1px solid #4A5568; text-align: center; margin-bottom: 20px;">
                    <span style="color: #CBD5E0; font-size: 13px;">REWERS (TŁUMACZENIE)</span>
                    <h2 style="color: #63B3ED; margin-top: 15px; font-size: 30px;">{current_card['Back']}</h2>
                </div>
                """, unsafe_allow_html=True)
            
            # Kontrolery
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("👁️ Pokaż / Ukryj", use_container_width=True):
                    st.session_state.show_back = not st.session_state.show_back
                    st.rerun()
                    
            with col2:
                if st.button("➡️ Następna", use_container_width=True):
                    st.session_state.flashcard_index = (idx + 1) % len(final_df)
                    st.session_state.show_back = False
                    st.rerun()
                    
            with col3:
                if st.button("🎲 Losuj", use_container_width=True):
                    st.session_state.flashcard_index = random.randint(0, len(final_df) - 1)
                    st.session_state.show_back = False
                    st.rerun()

import streamlit as st
import base64
import os
from openai import OpenAI
import anthropic
from supabase import create_client, Client

# Saugus API raktų užkrovimas
os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]
os.environ["ANTHROPIC_API_KEY"] = st.secrets["ANTHROPIC_API_KEY"]

# Prisijungimas prie Supabase duomenų bazės
supabase_url: str = st.secrets["SUPABASE_URL"]
supabase_key: str = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(supabase_url, supabase_key)

st.set_page_config(page_title="ParentAI", layout="wide")

# Inicijuojame kintamuosius būsenos valdymui
if 'step' not in st.session_state:
    st.session_state.step = 1
if 'transcription' not in st.session_state:
    st.session_state.transcription = ""
if 'current_advice' not in st.session_state:
    st.session_state.current_advice = ""
if 'task_image_bytes' not in st.session_state:
    st.session_state.task_image_bytes = None
if 'solution_image_bytes' not in st.session_state:
    st.session_state.solution_image_bytes = None

# ==========================================
# ŠONINĖ JUOSTA: ISTORIJA (Iš duomenų bazės)
# ==========================================
with st.sidebar:
    st.header("🕰️ Jūsų sesijos istorija")
    
    try:
        db_response = supabase.table("History").select("*").order("created_at", desc=True).execute()
        history_data = db_response.data
    except Exception as e:
        history_data = []
        st.error(f"Nepavyko užkrauti istorijos: {e}")

    if not history_data:
        st.info("Čia atsiras jūsų nuskenuoti namų darbai.")
    else:
        for i, item in enumerate(history_data):
            with st.expander(f"Užduotis #{len(history_data) - i}"):
                st.markdown("**Nuskaitytas tekstas:**")
                st.text(item['task_text'])
                st.markdown("**Patarimas:**")
                st.markdown(item['ai_advice'], unsafe_allow_html=True)

# ==========================================
# PAGRINDINIS EKRANAS
# ==========================================
st.title("📚 ParentAI Asistentas")
st.write("Padėkite vaikui su namų darbais be streso ir konfliktų.")
st.divider()

def encode_image_from_bytes(image_bytes):
    return base64.b64encode(image_bytes).decode('utf-8')

if st.session_state.step == 1:
    col1, col2 = st.columns(2)
    with col1:
        task_image = st.file_uploader("1. Užduoties lapas", type=["jpg", "jpeg", "png"])
    with col2:
        solution_image = st.file_uploader("2. Vaiko sprendimas", type=["jpg", "jpeg", "png"])

    if st.button("🔍 Nuskaityti tekstą", use_container_width=True):
        if not task_image or not solution_image:
            st.warning("Prašome įkelti abi nuotraukas: ir užduoties, ir vaiko sprendimo.")
        else:
            with st.spinner('AI skaito nuotraukas...'):
                try:
                    st.session_state.task_image_bytes = task_image.getvalue()
                    st.session_state.solution_image_bytes = solution_image.getvalue()
                    
                    client = OpenAI()
                    base64_task = encode_image_from_bytes(st.session_state.task_image_bytes)
                    base64_solution = encode_image_from_bytes(st.session_state.solution_image_bytes)

                    transcription_prompt = """Atidžiai perskaityk, kas parašyta nuotraukose. 
Pateik tik tekstą formatu:
SĄLYGA: [perrašyta sąlyga iš pirmos nuotraukos]
VAIKO SPRENDIMAS: [perrašytas vaiko sprendimas iš antros nuotraukos]

YPATINGAI SVARBI TAISYKLĖ: Privalai perrašyti KIEKVIENĄ vaiko sprendimo eilutę ir žingsnį tiksliai taip, kaip parašyta lape. Jokiu būdu netrumpink, nepraleisk tarpinių veiksmų (net jei jie klaidingi) ir nerašyk tik galutinio atsakymo. Turi matytis pilna sprendimo eiga eilutė po eilutės!

SVARBI TAISYKLĖ 2: Griežtai draudžiama naudoti LaTeX formatavimą (jokių \cdot, \div, \[, \], \(, \)). Matematinius simbolius rašyk paprastai: daugybai naudok · arba *, dalybai naudok : arba /. Lygtis rašyk paprasto, žmogui suprantamo teksto formatu. Nerašyk jokių savo sprendimų ar analizių, tik perrašyk tai, ką matai."""

                    response = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {"role": "system", "content": transcription_prompt},
                            {"role": "user", "content": [
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_task}"}},
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_solution}"}}
                            ]}
                        ],
                        max_tokens=600
                    )
                    
                    raw_text = response.choices[0].message.content
                    clean_text = raw_text.replace(r"\cdot", "·").replace(r"\div", ":").replace(r"\[", "").replace(r"\]", "").replace(r"\(", "").replace(r"\)", "").replace("$", "").replace(r"\times", "x").strip()
                    
                    st.session_state.transcription = clean_text
                    st.session_state.step = 2
                    st.rerun()

                except Exception as e:
                    st.error(f"Įvyko klaida skaitant nuotraukas: {e}")

elif st.session_state.step == 2:
    st.info("✏️ Patikrinkite, ar AI teisingai perskaitė vaiko raštą. Palyginkite su nuotraukomis ir ištaisykite klaidas šiame laukelyje.")
    
    with st.expander("📷 Paspauskite, kad peržiūrėtumėte originalias nuotraukas"):
        img_col1, img_col2 = st.columns(2)
        with img_col1:
            if st.session_state.task_image_bytes:
                st.image(st.session_state.task_image_bytes, caption="Užduoties lapas", use_container_width=True)
        with img_col2:
            if st.session_state.solution_image_bytes:
                st.image(st.session_state.solution_image_bytes, caption="Vaiko sprendimas", use_container_width=True)
                
    edited_text = st.text_area("Atpažintas tekstas (Redaguojamas):", value=st.session_state.transcription, height=300)
    
    col3, col4 = st.columns(2)
    with col3:
        if st.button("⬅️ Bandyti nuskaityti iš naujo"):
            st.session_state.step = 1
            st.rerun()
            
    with col4:
        if st.button("🧠 Gauti pedagoginį patarimą", type="primary", use_container_width=True):
            
            # NAUJA DALIS: Tikriname, ar toks tekstas jau buvo analizuotas duomenų bazėje
            is_duplicate = False
            with st.spinner("Tikrinama, ar ši užduotis jau buvo spręsta anksčiau..."):
                try:
                    existing_task = supabase.table("History").select("ai_advice").eq("task_text", edited_text).execute()
                    if existing_task.data and len(existing_task.data) > 0:
                        # Radome išsaugotą analizę!
                        st.session_state.current_advice = existing_task.data[0]['ai_advice']
                        is_duplicate = True
                except Exception as db_err:
                    st.warning("Nepavyko susisiekti su duomenų baze patikrinimui, tęsiame analizę...")
            
            if is_duplicate:
                st.toast("Naudojamas ankstesnis išsaugotas sprendimas (sutaupyta AI užklausa!)", icon="✅")
                st.session_state.step = 3
                st.rerun()
            else:
                # Jei teksto neradome, kreipiamės į Claude Sonnet 5
                with st.spinner("Claude Sonnet 5 vertina logiką ir ruošia patarimą... (Tai gali užtrukti kelias sekundes)"):
                    try:
                        client_anthropic = anthropic.Anthropic()
                        
                        system_prompt = """Tu esi pedagoginis asistentas tėvams.
SVARBI TAISYKLĖ FORMATAVIMUI: Nenaudok jokių LaTeX formatų. Daugybai naudok ·, padalinimui :, lygybei =. Rodykles rašyk paprastai: ->.
SVARBI TAISYKLĖ ANALIZEI: 
1. Prieš vertindamas, visada pats žingsnis po žingsnio išspręsk uždavinį.
2. Privalai patikrinti KIEKVIENĄ vaiko sprendimą atskirai.
3. Vertink ne tik galutinį atsakymą, bet ir logiką bei matematinį užrašymą. GRIEŽTAI atkreipk dėmesį į "ilgų lygybių" (chained equalities) klaidas (pvz., "18 : 2 = 9 = 9 - 5 = 4").
4. Prie kiekvieno uždavinio aiškiai parašyk vertinimą: "✅ GERAI" arba "❌ KLAIDA".

Pateik atsakymą GRIEŽTAI šia struktūra:

**1. UŽDUOČIŲ ANALIZĖ IR TEISINGI SPRENDIMAI:**
(Eik per kiekvieną uždavinį. Parašyk vertinimą ir paaiškink klaidas. Tada IŠKART po analizės parašyk teisingą sprendimą naudodamas šį tikslų HTML kodą):
<details>
<summary>👉 Paspauskite, kad pamatytumėte teisingą atsakymą ir sprendimo eigą</summary>
<br>
(1 žingsnis)<br>
(2 žingsnis)<br>
(3 žingsnis)<br>
</details>
GRIEŽTAI naudok <br> žymą po KIEKVIENO matematinio žingsnio, kad jie garantuotai būtų atskirose eilutėse! Niekada nerašyk lygties žingsnių vienoje eilutėje.

**2. KĄ SAKYTI VAIKUI:** 
(1-2 trumpi patarimai tėvams)"""

                        response = client_anthropic.messages.create(
                            model="claude-sonnet-5",
                            max_tokens=4000,
                            system=system_prompt,
                            messages=[
                                {"role": "user", "content": f"TEKSTAS ANALIZEI:\n{edited_text}"}
                            ]
                        )
                        
                        ai_response = ""
                        for block in response.content:
                            if hasattr(block, 'text') and block.text:
                                ai_response += block.text
                                
                        ai_response = ai_response.replace(r"\cdot", "·").replace("$", "").replace(r"\times", "x").replace(r"\[", "").replace(r"\]", "").replace(r"\Rightarrow", "->").replace(r"\(", "").replace(r"\)", "")
                        
                        try:
                            supabase.table("History").insert({"task_text": edited_text, "ai_advice": ai_response}).execute()
                        except Exception as db_e:
                            st.error(f"Nepavyko išsaugoti į duomenų bazę: {db_e}")

                        st.session_state.current_advice = ai_response
                        st.session_state.step = 3
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"Įvyko API klaida: {e}")

elif st.session_state.step == 3:
    st.success("Analizė baigta! Rezultatas sėkmingai išsaugotas istorijoje kairėje.")
    
    with st.expander("📷 Paspauskite, kad peržiūrėtumėte įkeltas nuotraukas"):
        img_col1, img_col2 = st.columns(2)
        with img_col1:
            if st.session_state.task_image_bytes:
                st.image(st.session_state.task_image_bytes, caption="Užduoties lapas", use_container_width=True)
        with img_col2:
            if st.session_state.solution_image_bytes:
                st.image(st.session_state.solution_image_bytes, caption="Vaiko sprendimas", use_container_width=True)
                
    st.divider()
    
    st.markdown("### 🧠 AI Patarimas Tėvams:")
    st.markdown(f'<div style="background-color: #f0f2f6; padding: 20px; border-radius: 10px;">{st.session_state.current_advice}</div>', unsafe_allow_html=True)
    
    st.write("") 
    if st.button("➕ Nuskaityti naują užduotį", type="primary"):
        st.session_state.step = 1
        st.session_state.transcription = ""
        st.session_state.current_advice = ""
        st.session_state.task_image_bytes = None
        st.session_state.solution_image_bytes = None
        st.rerun()

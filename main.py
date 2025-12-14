import io
from datetime import datetime, date

import streamlit as st

# PDF (ReportLab)
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib.utils import simpleSplit, ImageReader

# Merge PDFs
from PyPDF2 import PdfMerger

# Pillow (para imágenes)
from PIL import Image


# ----------------------------
# Helpers PDF
# ----------------------------
def _draw_wrapped(c, text, x, y, max_width, font_name="Helvetica", font_size=10, leading=12):
    c.setFont(font_name, font_size)
    lines = simpleSplit(text or "", font_name, font_size, max_width)
    for line in lines:
        c.drawString(x, y, line)
        y -= leading
    return y


def build_base_pdf(data: dict) -> bytes:
    """Construye PDF base (solo ficha + listado de anexos) y regresa bytes."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=LETTER)
    width, height = LETTER

    left = 0.75 * inch
    right = 0.75 * inch
    top = height - 0.75 * inch
    bottom = 0.75 * inch
    max_w = width - left - right
    y = top

    # Header
    c.setFont("Helvetica-Bold", 14)
    c.drawString(left, y, "Ficha rápida para personal de salud (Adulto mayor)")
    y -= 18

    c.setFont("Helvetica", 9)
    gen_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    c.drawString(left, y, f"Generado: {gen_time}")
    y -= 18

    def section(title):
        nonlocal y
        y -= 6
        c.setFont("Helvetica-Bold", 12)
        c.drawString(left, y, title)
        y -= 14
        c.setLineWidth(0.7)
        c.line(left, y, left + max_w, y)
        y -= 12

    def field(label, value):
        nonlocal y
        text = f"{label}: {value if value not in (None, '') else '—'}"
        y_new = _draw_wrapped(c, text, left, y, max_w, font_name="Helvetica", font_size=10)
        y = y_new - 2

    def ensure_space(min_space=120):
        nonlocal y
        if y < bottom + min_space:
            c.showPage()
            y = top

    # 0) Registro
    section("0) Registro de la información")
    ensure_space()
    for k in ["Fecha de elaboración", "Registró (nombre)"]:
        field(k, data.get(k))

    # 1) Identificación
    ensure_space()
    section("1) Identificación")
    ensure_space()
    for k in [
        "Nombre completo", "Edad", "Sexo", "CURP", "Domicilio",
        "Teléfono del paciente", "Contacto de emergencia", "Parentesco", "Teléfono de contacto",
        "Médico tratante", "Teléfono médico", "Clínica/Hospital habitual"
    ]:
        field(k, data.get(k))

    # Obstétrico (solo si aplica)
    if (data.get("Sexo") or "").lower().startswith("fem"):
        ensure_space()
        section("1B) Antecedentes gineco-obstétricos (si aplica)")
        for k in [
            "Embarazos (G)", "Partos (P)", "Cesáreas (C)", "Abortos (A)",
            "Complicaciones en embarazos/partos", "Menopausia (edad aprox.)", "Cirugías ginecológicas relevantes"
        ]:
            field(k, data.get(k))

    # 2) Datos básicos
    ensure_space()
    section("2) Datos básicos")
    for k in ["Peso (kg)", "Estatura (m)", "Presión usual", "Diabetes", "Última glucosa conocida"]:
        field(k, data.get(k))

    # 3) Evento actual
    ensure_space()
    section("3) Evento actual / Motivo de atención")
    for k in [
        "Motivo principal", "Fecha y hora de inicio", "Fue presenciado", "Quién lo vio",
        "Duración aproximada (min)", "Descripción del evento",
        "Pérdida de conciencia", "Mordida de lengua", "Pérdida de orina/evacuación",
        "Después del evento", "Lesiones por caída/golpe", "Fiebre o malestar previo",
        "Factores previos (alcohol/desvelo/ayuno/estrés/deshidratación)", "Eventos similares previos"
    ]:
        field(k, data.get(k))

    # 4) Antecedentes
    ensure_space()
    section("4) Antecedentes médicos")
    field("Enfermedades diagnosticadas", ", ".join(data.get("Enfermedades", [])) or "—")
    field("Otros relevantes", data.get("Otros relevantes"))
    field("Cirugías / hospitalizaciones importantes", data.get("Cirugías/hospitalizaciones"))

    # 4B) Historial de infancia
    ensure_space()
    section("4B) Historial de infancia (clínicamente útil)")
    field("Nacimiento (prematuro/complicaciones)", data.get("Infancia - nacimiento"))
    field("Infecciones graves SNC (meningitis/encefalitis)", data.get("Infancia - SNC"))
    field("Convulsiones febriles en infancia", data.get("Infancia - convulsiones febriles"))
    field("Traumatismo craneal importante en infancia", data.get("Infancia - TCE"))
    field("Enfermedades crónicas/congénitas desde infancia", data.get("Infancia - crónicas"))
    field("Desarrollo/Aprendizaje (retrasos significativos)", data.get("Infancia - desarrollo"))
    field("Otros antecedentes de infancia", data.get("Infancia - otros"))

    # 5) Medicamentos
    ensure_space()
    section("5) Medicamentos actuales")
    meds = data.get("Medicamentos", [])
    if meds:
        for i, m in enumerate(meds, start=1):
            ensure_space(90)
            field(
                f"Medicamento {i}",
                f"{m.get('nombre','—')} | {m.get('dosis','—')} | {m.get('frecuencia','—')} | {m.get('para_que','—')}"
            )
    else:
        field("Medicamentos", "—")

    field("Medicamentos de riesgo (marcados)", ", ".join(data.get("Riesgo meds", [])) or "—")
    field("Última dosis conocida", data.get("Última dosis conocida"))

    # 6) Alergias
    ensure_space()
    section("6) Alergias y reacciones")
    for k in ["Alergia a medicamentos", "Cuáles y reacción", "Alergias alimentos/otras", "Alergia a yodo/contraste", "Látex"]:
        field(k, data.get(k))

    # 7) Hábitos
    ensure_space()
    section("7) Sustancias y hábitos")
    for k in ["Tabaco", "Alcohol", "Otras sustancias", "Café/energizantes"]:
        field(k, data.get(k))

    # 8) Estado funcional basal
    ensure_space()
    section("8) Estado funcional y basal")
    for k in ["Estado habitual previo", "Movilidad", "ABVD (baño/vestido/comer)", "Memoria/orientación habitual"]:
        field(k, data.get(k))

    # 8B) Barthel
    ensure_space()
    section("8B) Índice de Barthel (resumen)")
    field("Barthel total (0-100)", data.get("Barthel total"))
    field("Detalle Barthel", data.get("Barthel detalle"))

    # 8C) SARC-F
    ensure_space()
    section("8C) SARC-F (resumen)")
    field("SARC-F total (0-10)", data.get("SARC-F total"))
    field("Detalle SARC-F", data.get("SARC-F detalle"))

    # 9) Síntomas neuro-cognitivos 15 días
    ensure_space()
    section("9) Últimos 15 días (neuro-cognitivo / equilibrio)")
    field("Cambios en agudeza visual", data.get("15d - visión"))
    field("Cefalea / dolor de cabeza", data.get("15d - cefalea"))
    field("Migraña", data.get("15d - migraña"))
    field("Mareo / vértigo", data.get("15d - mareo"))
    field("Problemas de equilibrio", data.get("15d - equilibrio"))
    field("Caídas en 15 días", data.get("15d - caídas"))
    field("Desorientación/confusión", data.get("15d - confusión"))
    field("Cambios de memoria/atención", data.get("15d - memoria"))
    field("Debilidad/adormecimiento (focal)", data.get("15d - focalidad"))
    field("Lenguaje/habla (dificultad)", data.get("15d - habla"))
    field("Sueño (cambios marcados)", data.get("15d - sueño"))
    field("Otros síntomas 15 días", data.get("15d - otros"))

    # 10) Salud bucal / prótesis
    ensure_space()
    section("10) Salud bucal / prótesis dentales")
    field("Uso de prótesis dental", data.get("Prótesis - uso"))
    field("Tipo (parcial/total)", data.get("Prótesis - tipo"))
    field("Ubicación (superior/inferior)", data.get("Prótesis - ubicación"))
    field("Molestias/úlceras/ajuste", data.get("Prótesis - molestias"))
    field("Dificultad para masticar/deglutir", data.get("Prótesis - masticación"))
    field("Última valoración dental", data.get("Prótesis - última revisión"))

    # 11) Urgencias
    ensure_space()
    section("11) Datos útiles en urgencias")
    for k in [
        "Caídas recientes", "Marcapasos/implantes", "Vacunas/infecciones recientes",
        "Directiva anticipada", "Tipo de sangre", "Seguro/afiliación"
    ]:
        field(k, data.get(k))

    # Anexos: listado
    ensure_space()
    section("Anexos (análisis previos) - listado")
    anexos = data.get("Anexos", [])
    if anexos:
        for a in anexos:
            ensure_space(70)
            field("Archivo", a)
    else:
        field("Anexos", "—")

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.read()


def image_to_pdf_page(image_bytes: bytes, title: str) -> bytes:
    """Convierte una imagen a un PDF (1 página) y regresa bytes."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=LETTER)
    width, height = LETTER

    left = 0.75 * inch
    right = 0.75 * inch
    top = height - 0.75 * inch
    bottom = 0.75 * inch

    c.setFont("Helvetica-Bold", 12)
    c.drawString(left, top, f"Anexo (Imagen): {title}")
    y = top - 18

    img = Image.open(io.BytesIO(image_bytes))
    img_w, img_h = img.size

    box_w = width - left - right
    box_h = (y - bottom)

    scale = min(box_w / img_w, box_h / img_h)
    draw_w = img_w * scale
    draw_h = img_h * scale

    x = left + (box_w - draw_w) / 2
    y_img = bottom + (box_h - draw_h) / 2

    c.drawImage(ImageReader(img), x, y_img, width=draw_w, height=draw_h, preserveAspectRatio=True, mask="auto")
    c.showPage()
    c.save()
    buf.seek(0)
    return buf.read()


def merge_pdfs(pdf_bytes_list: list[bytes]) -> bytes:
    merger = PdfMerger()
    streams = []
    try:
        for b in pdf_bytes_list:
            s = io.BytesIO(b)
            streams.append(s)
            merger.append(s)
        out = io.BytesIO()
        merger.write(out)
        merger.close()
        out.seek(0)
        return out.read()
    finally:
        for s in streams:
            try:
                s.close()
            except Exception:
                pass


def build_pdf_with_attachments(data: dict, uploads) -> bytes:
    """PDF final = ficha + anexos como páginas."""
    base = build_base_pdf(data)
    parts = [base]

    if uploads:
        for uf in uploads:
            name = uf.name
            b = uf.getvalue()
            if name.lower().endswith(".pdf"):
                parts.append(b)
            elif name.lower().endswith((".png", ".jpg", ".jpeg")):
                parts.append(image_to_pdf_page(b, name))
            else:
                pass

    return merge_pdfs(parts)


# ----------------------------
# UI Streamlit
# ----------------------------
st.set_page_config(page_title="Ficha médica (Adulto mayor)", layout="wide")
st.title("🩺 Ficha médica rápida (Adulto mayor) → PDF")
st.caption("Llena el formulario y al final descarga un PDF (incluye anexos al final).")

if "meds" not in st.session_state:
    st.session_state.meds = []

with st.form("form_ficha", clear_on_submit=False):

    # 0) Registro
    st.subheader("0) Registro de la información")
    reg_col1, reg_col2 = st.columns(2)
    with reg_col1:
        fecha_elab = st.date_input("Fecha de elaboración", value=date.today())
    with reg_col2:
        registro_por = st.text_input("¿Quién realizó el registro? (nombre)")

    st.divider()

    # Adjuntos
    st.subheader("📎 Análisis previos (se anexan al MISMO PDF)")
    uploads = st.file_uploader(
        "Sube análisis previos en PDF o imágenes (JPG/PNG).",
        type=["pdf", "png", "jpg", "jpeg"],
        accept_multiple_files=True
    )
    st.caption("Los PDFs se agregan al final tal cual. Las imágenes se convierten a páginas y se anexan.")

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("1) Identificación")
        nombre = st.text_input("Nombre completo")
        edad = st.number_input("Edad", min_value=0, max_value=120, step=1)
        sexo = st.selectbox("Sexo", ["", "Masculino", "Femenino", "Otro/Prefiero no decir"])
        curp = st.text_input("CURP (opcional)")
        domicilio = st.text_area("Domicilio (opcional)", height=68)
        tel_paciente = st.text_input("Teléfono del paciente (opcional)")

        st.subheader("Contacto de emergencia")
        contacto = st.text_input("Nombre contacto de emergencia")
        parentesco = st.text_input("Parentesco (hijo/a, esposa, etc.)")
        tel_contacto = st.text_input("Teléfono de contacto")

        st.subheader("Médico/Clínica habitual")
        medico = st.text_input("Médico tratante (opcional)")
        tel_medico = st.text_input("Teléfono médico (opcional)")
        clinica = st.text_input("Clínica/Hospital habitual (opcional)")

    with col2:
        st.subheader("2) Datos básicos")
        peso = st.number_input("Peso (kg)", min_value=0.0, max_value=300.0, step=0.5)
        estatura = st.number_input("Estatura (m)", min_value=0.0, max_value=2.50, step=0.01)
        presion = st.text_input("Presión arterial usual (si se sabe)")

        diabetes = st.selectbox("¿Diabetes?", ["", "No", "Sí", "No sabe"])
        glucosa = st.text_input("Última glucosa conocida (si se sabe)")

        st.subheader("3) Evento actual / motivo")
        motivo = st.text_input("Motivo principal (en una frase)")
        inicio = st.text_input("Fecha y hora de inicio (ej. 2025-12-14 03:10)")
        presenciado = st.selectbox("¿Fue presenciado?", ["", "Sí", "No", "No sabe"])
        quien_vio = st.text_input("¿Quién lo vio? (si aplica)")
        duracion = st.number_input("Duración aproximada (min)", min_value=0, max_value=600, step=1)
        descripcion = st.text_area("Descripción breve de lo que pasó", height=92)

        perdida_conciencia = st.selectbox("¿Pérdida de conciencia?", ["", "Sí", "No", "No sabe"])
        mordida = st.selectbox("¿Mordida de lengua?", ["", "Sí", "No", "No sabe"])
        perdida_orina = st.selectbox("¿Pérdida de orina/evacuación?", ["", "Sí", "No", "No sabe"])

        despues = st.multiselect(
            "Después del evento (selecciona lo que aplique)",
            ["Confusión", "Somnolencia", "Dolor muscular", "Dolor de cabeza", "Se recuperó normal", "Otro"]
        )
        lesiones = st.text_input("Lesiones por caída/golpe (si hubo, dónde)")
        fiebre = st.selectbox("Fiebre/infección/malestar previo (últimos 7 días)", ["", "No", "Sí", "No sabe"])
        factores = st.text_input("Factores previos (alcohol/desvelo/ayuno/estrés/deshidratación)")
        similares = st.text_input("¿Eventos similares previos? (cuándo)")

    # Antecedentes gineco-obstétricos si sexo femenino
    if sexo == "Femenino":
        st.divider()
        st.subheader("1B) Antecedentes gineco-obstétricos (si aplica)")
        g1, g2, g3, g4 = st.columns(4)
        with g1:
            emb_g = st.number_input("Embarazos (G)", min_value=0, max_value=30, step=1)
        with g2:
            part_p = st.number_input("Partos (P)", min_value=0, max_value=30, step=1)
        with g3:
            ces_c = st.number_input("Cesáreas (C)", min_value=0, max_value=30, step=1)
        with g4:
            abo_a = st.number_input("Abortos (A)", min_value=0, max_value=30, step=1)

        comp_ob = st.text_area("Complicaciones (preeclampsia, hemorragia, diabetes gestacional, parto prolongado, etc.)", height=60)
        meno_edad = st.text_input("Menopausia (edad aprox., si aplica)")
        cir_gine = st.text_input("Cirugías ginecológicas relevantes (si aplica)")
    else:
        emb_g = part_p = ces_c = abo_a = 0
        comp_ob = meno_edad = cir_gine = ""

    st.divider()

    st.subheader("4) Antecedentes médicos")
    enfermedades = st.multiselect(
        "Enfermedades diagnosticadas",
        [
            "Hipertensión", "Diabetes", "Colesterol alto",
            "Infarto/cardiopatía", "Arritmias", "Insuficiencia cardiaca",
            "EVC/derrame cerebral", "AIT (evento isquémico transitorio)",
            "Convulsiones previas/epilepsia",
            "Enfermedad renal crónica", "Enfermedad hepática",
            "EPOC/asma", "Apnea del sueño",
            "Demencia/deterioro cognitivo", "Depresión/ansiedad",
            "Tiroides", "Cáncer", "Otra"
        ]
    )
    otros = st.text_input("Otros relevantes (si marcaste 'Otra' o para ampliar)")
    cirugias = st.text_area("Cirugías / hospitalizaciones importantes (año y motivo)", height=70)

    st.divider()

    st.subheader("4B) Historial de infancia (clínicamente útil)")
    inf_col1, inf_col2 = st.columns(2)
    with inf_col1:
        inf_nac = st.selectbox("Nacimiento", ["", "A término sin complicaciones", "Prematuro", "Complicaciones al nacer", "No sabe"])
        inf_snc = st.selectbox("Infecciones graves SNC (meningitis/encefalitis)", ["", "No", "Sí", "No sabe"])
        inf_febr = st.selectbox("Convulsiones febriles en infancia", ["", "No", "Sí", "No sabe"])
    with inf_col2:
        inf_tce = st.selectbox("Traumatismo craneal importante en infancia", ["", "No", "Sí", "No sabe"])
        inf_cron = st.text_input("Enfermedades crónicas/congénitas desde infancia (si aplica)")
        inf_des = st.selectbox("Desarrollo/Aprendizaje (retrasos importantes)", ["", "No", "Sí", "No sabe"])
    inf_otros = st.text_area("Otros antecedentes de infancia relevantes", height=60)

    st.divider()

    st.subheader("5) Medicamentos actuales")
    st.caption("Puedes agregar varios medicamentos. Si no sabes la dosis exacta, escribe lo que recuerdes o “no sabe”.")
    med_col1, med_col2, med_col3, med_col4, med_col5 = st.columns([2, 1, 1, 2, 1])

    with med_col1:
        m_nombre = st.text_input("Nombre del medicamento", key="m_nombre")
    with med_col2:
        m_dosis = st.text_input("Dosis", key="m_dosis")
    with med_col3:
        m_frec = st.text_input("Frecuencia", key="m_frec")
    with med_col4:
        m_para = st.text_input("¿Para qué?", key="m_para")
    with med_col5:
        add = st.form_submit_button("➕ Agregar")

    if add:
        if m_nombre.strip():
            st.session_state.meds.append(
                {"nombre": m_nombre.strip(), "dosis": m_dosis.strip(), "frecuencia": m_frec.strip(), "para_que": m_para.strip()}
            )
        else:
            st.warning("Escribe al menos el nombre del medicamento antes de agregar.")

    if st.session_state.meds:
        st.write("**Medicamentos agregados:**")
        for idx, m in enumerate(st.session_state.meds, start=1):
            st.write(f"{idx}. {m['nombre']} | {m['dosis']} | {m['frecuencia']} | {m['para_que']}")

    riesgo = st.multiselect(
        "Medicamentos de riesgo (marca si aplica)",
        ["Anticoagulantes", "Antiagregantes (aspirina/clopidogrel)", "Insulina/hipoglucemiantes", "Benzodiacepinas/sedantes",
         "Antidepresivos/antipsicóticos", "Anticonvulsivos"]
    )
    ultima_dosis = st.text_input("Última dosis conocida (si se sabe)")

    st.divider()

    st.subheader("6) Alergias")
    alergia_meds = st.selectbox("¿Alergia a medicamentos?", ["", "No", "Sí", "No sabe"])
    cuales_reaccion = st.text_area("¿Cuáles y qué reacción?", height=60)
    alergias_otras = st.text_input("Alergias a alimentos/otras (si aplica)")
    yodo = st.selectbox("Alergia a yodo/contraste", ["", "No", "Sí", "No sabe"])
    latex = st.selectbox("Látex", ["", "No", "Sí", "No sabe"])

    st.divider()

    st.subheader("7) Sustancias y hábitos")
    tabaco = st.text_input("Tabaco (ej. no / 3 al día por 20 años)")
    alcohol = st.text_input("Alcohol (ej. no / ocasional / diario)")
    otras_subs = st.text_input("Otras sustancias (si aplica)")
    cafe = st.text_input("Café/energizantes (si aplica)")

    st.divider()

    st.subheader("8) Estado funcional (basal)")
    estado_previo = st.selectbox("Antes del evento, su estado era", ["", "Normal", "Algo limitado", "Muy limitado"])
    movilidad = st.selectbox("Movilidad", ["", "Camina solo", "Con bastón", "Con andadera", "Silla de ruedas", "No deambula"])
    abvd = st.selectbox("Actividades básicas (baño/vestido/comer)", ["", "Independiente", "Requiere ayuda", "No sabe"])
    memoria = st.selectbox("Memoria/orientación habitual", ["", "Conservada", "Olvidos leves", "Deterioro importante", "No sabe"])

    # Barthel
    st.subheader("8B) Índice de Barthel (0-100)")
    st.caption("Selección rápida tipo valoración geriátrica. (Es para orientar, no sustituye evaluación clínica).")

    def opt(label_points):
        # label_points: list of tuples (label, points)
        labels = [f"{lab} ({pts})" for lab, pts in label_points]
        return labels, {labels[i]: label_points[i][1] for i in range(len(labels))}

    b_cols = st.columns(2)

    labels, map_pts = opt([("Independiente", 10), ("Necesita ayuda", 5), ("Dependiente", 0)])
    with b_cols[0]:
        b_alim = st.selectbox("Alimentación", [""] + labels)
    labels_b, map_pts_b = opt([("Independiente", 5), ("Dependiente", 0)])
    with b_cols[1]:
        b_bano = st.selectbox("Baño", [""] + labels_b)

    labels, map_pts = opt([("Independiente", 5), ("Dependiente", 0)])
    with b_cols[0]:
        b_aseo = st.selectbox("Aseo personal", [""] + labels)
    labels, map_pts = opt([("Independiente", 10), ("Necesita ayuda", 5), ("Dependiente", 0)])
    with b_cols[1]:
        b_vest = st.selectbox("Vestido", [""] + labels)

    labels, map_pts = opt([("Continente", 10), ("Accidentes ocasionales", 5), ("Incontinente", 0)])
    with b_cols[0]:
        b_hec = st.selectbox("Heces", [""] + labels)
    with b_cols[1]:
        b_ori = st.selectbox("Orina", [""] + labels)

    labels, map_pts = opt([("Independiente", 10), ("Necesita ayuda", 5), ("Dependiente", 0)])
    with b_cols[0]:
        b_wc = st.selectbox("Uso de WC", [""] + labels)

    labels, map_pts = opt([("Independiente", 15), ("Ayuda mayor", 10), ("Ayuda menor", 5), ("Dependiente", 0)])
    with b_cols[1]:
        b_trans = st.selectbox("Traslado cama-silla", [""] + labels)

    labels, map_pts = opt([("Independiente", 15), ("Con ayuda", 10), ("Silla de ruedas independiente", 5), ("Dependiente", 0)])
    with b_cols[0]:
        b_mov = st.selectbox("Deambulación/movilidad", [""] + labels)

    labels, map_pts = opt([("Independiente", 10), ("Con ayuda", 5), ("Dependiente", 0)])
    with b_cols[1]:
        b_esc = st.selectbox("Escaleras", [""] + labels)

    # Calcular Barthel
    def pts_from(sel):
        if not sel:
            return 0
        # extraer puntos del final "(X)"
        try:
            return int(sel.split("(")[-1].replace(")", "").strip())
        except Exception:
            return 0

    barthel_items = {
        "Alimentación": pts_from(b_alim),
        "Baño": pts_from(b_bano),
        "Aseo personal": pts_from(b_aseo),
        "Vestido": pts_from(b_vest),
        "Heces": pts_from(b_hec),
        "Orina": pts_from(b_ori),
        "Uso de WC": pts_from(b_wc),
        "Traslado cama-silla": pts_from(b_trans),
        "Movilidad": pts_from(b_mov),
        "Escaleras": pts_from(b_esc),
    }
    barthel_total = sum(barthel_items.values())
    barthel_detalle = ", ".join([f"{k}={v}" for k, v in barthel_items.items()])

    st.write(f"**Barthel total:** {barthel_total} / 100")

    # SARC-F
    st.subheader("8C) SARC-F (0-10)")
    st.caption("0=sin dificultad, 1=algo, 2=mucha/no puede (caídas: 0, 1–3, ≥4).")

    sarc_opts = ["", "0 - Sin dificultad", "1 - Algo de dificultad", "2 - Mucha dificultad / no puede"]
    sarc_falls = ["", "0 - 0 caídas", "1 - 1 a 3 caídas", "2 - 4 o más caídas"]

    s_cols = st.columns(2)
    with s_cols[0]:
        sarc_fuerza = st.selectbox("Fuerza (levantar/cargar 4.5 kg)", sarc_opts)
        sarc_caminar = st.selectbox("Caminar (asistencia)", sarc_opts)
        sarc_silla = st.selectbox("Levantarse de silla", sarc_opts)
    with s_cols[1]:
        sarc_escal = st.selectbox("Subir escaleras", sarc_opts)
        sarc_caidas = st.selectbox("Caídas (último año)", sarc_falls)

    def sarc_pts(sel):
        if not sel:
            return 0
        try:
            return int(sel.split("-")[0].strip())
        except Exception:
            return 0

    sarc_items = {
        "Fuerza": sarc_pts(sarc_fuerza),
        "Caminar": sarc_pts(sarc_caminar),
        "Silla": sarc_pts(sarc_silla),
        "Escaleras": sarc_pts(sarc_escal),
        "Caídas": sarc_pts(sarc_caidas),
    }
    sarc_total = sum(sarc_items.values())
    sarc_detalle = ", ".join([f"{k}={v}" for k, v in sarc_items.items()])
    st.write(f"**SARC-F total:** {sarc_total} / 10")

    st.divider()

    st.subheader("9) Últimos 15 días (neuro-cognitivo / equilibrio)")
    n1, n2 = st.columns(2)
    with n1:
        d_vision = st.selectbox("Cambios en agudeza visual", ["", "No", "Sí", "No sabe"])
        d_cef = st.selectbox("Dolor de cabeza (cefalea)", ["", "No", "Sí", "No sabe"])
        d_mig = st.selectbox("Migraña", ["", "No", "Sí", "No sabe"])
        d_mareo = st.selectbox("Mareo / vértigo", ["", "No", "Sí", "No sabe"])
        d_equ = st.selectbox("Problemas de equilibrio", ["", "No", "Sí", "No sabe"])
    with n2:
        d_caidas = st.selectbox("Caídas en los últimos 15 días", ["", "No", "Sí", "No sabe"])
        d_conf = st.selectbox("Confusión / desorientación", ["", "No", "Sí", "No sabe"])
        d_mem = st.selectbox("Cambios en memoria/atención", ["", "No", "Sí", "No sabe"])
        d_foc = st.selectbox("Debilidad/adormecimiento focal (cara/brazo/pierna)", ["", "No", "Sí", "No sabe"])
        d_hab = st.selectbox("Dificultad para hablar/entender", ["", "No", "Sí", "No sabe"])
    d_sueno = st.selectbox("Cambios marcados en sueño", ["", "No", "Sí", "No sabe"])
    d_otros = st.text_area("Otros síntomas relevantes (últimos 15 días)", height=60)

    st.divider()

    st.subheader("10) Salud bucal / prótesis dentales")
    pro_uso = st.selectbox("¿Usa prótesis dental?", ["", "No", "Sí", "No sabe"])
    pro_tipo = st.selectbox("Tipo", ["", "Parcial", "Total", "Mixta (parcial y total)", "No aplica"])
    pro_ubi = st.selectbox("Ubicación", ["", "Superior", "Inferior", "Ambas", "No aplica"])
    pro_mol = st.selectbox("Molestias/úlceras/ajuste inadecuado", ["", "No", "Sí", "No sabe"])
    pro_mast = st.selectbox("Dificultad para masticar/deglutir", ["", "No", "Sí", "No sabe"])
    pro_rev = st.text_input("Última valoración dental (aprox.)")

    st.divider()

    st.subheader("11) Datos útiles en urgencias")
    caidas = st.selectbox("Caídas recientes (últimos 30 días)", ["", "No", "Sí", "No sabe"])
    implantes = st.text_input("Marcapasos/implantes/metal (si aplica)")
    vacunas_inf = st.text_input("Vacunas/infecciones recientes (si aplica)")
    directiva = st.text_input("Directiva anticipada / voluntad (si existe)")
    sangre = st.text_input("Tipo de sangre (si se sabe)")
    seguro = st.text_input("Seguro/afiliación (IMSS/ISSSTE/privado/etc.)")

    submitted = st.form_submit_button("📄 Generar PDF (con anexos)")


if submitted:
    anexos_listado = []
    if uploads:
        anexos_listado = [uf.name for uf in uploads]

    # Consolidar datos
    data = {
        # Registro
        "Fecha de elaboración": fecha_elab.strftime("%Y-%m-%d") if fecha_elab else "",
        "Registró (nombre)": registro_por,

        # Identificación
        "Nombre completo": nombre,
        "Edad": str(edad) if edad else "",
        "Sexo": sexo,
        "CURP": curp,
        "Domicilio": domicilio,
        "Teléfono del paciente": tel_paciente,
        "Contacto de emergencia": contacto,
        "Parentesco": parentesco,
        "Teléfono de contacto": tel_contacto,
        "Médico tratante": medico,
        "Teléfono médico": tel_medico,
        "Clínica/Hospital habitual": clinica,

        # Obstétrico si aplica
        "Embarazos (G)": str(emb_g) if sexo == "Femenino" else "",
        "Partos (P)": str(part_p) if sexo == "Femenino" else "",
        "Cesáreas (C)": str(ces_c) if sexo == "Femenino" else "",
        "Abortos (A)": str(abo_a) if sexo == "Femenino" else "",
        "Complicaciones en embarazos/partos": comp_ob if sexo == "Femenino" else "",
        "Menopausia (edad aprox.)": meno_edad if sexo == "Femenino" else "",
        "Cirugías ginecológicas relevantes": cir_gine if sexo == "Femenino" else "",

        # Básicos
        "Peso (kg)": f"{peso:.1f}" if peso else "",
        "Estatura (m)": f"{estatura:.2f}" if estatura else "",
        "Presión usual": presion,
        "Diabetes": diabetes,
        "Última glucosa conocida": glucosa,

        # Evento
        "Motivo principal": motivo,
        "Fecha y hora de inicio": inicio,
        "Fue presenciado": presenciado,
        "Quién lo vio": quien_vio,
        "Duración aproximada (min)": str(duracion) if duracion else "",
        "Descripción del evento": descripcion,
        "Pérdida de conciencia": perdida_conciencia,
        "Mordida de lengua": mordida,
        "Pérdida de orina/evacuación": perdida_orina,
        "Después del evento": ", ".join(despues) if despues else "",
        "Lesiones por caída/golpe": lesiones,
        "Fiebre o malestar previo": fiebre,
        "Factores previos (alcohol/desvelo/ayuno/estrés/deshidratación)": factores,
        "Eventos similares previos": similares,

        # Antecedentes
        "Enfermedades": enfermedades,
        "Otros relevantes": otros,
        "Cirugías/hospitalizaciones": cirugias,

        # Infancia
        "Infancia - nacimiento": inf_nac,
        "Infancia - SNC": inf_snc,
        "Infancia - convulsiones febriles": inf_febr,
        "Infancia - TCE": inf_tce,
        "Infancia - crónicas": inf_cron,
        "Infancia - desarrollo": inf_des,
        "Infancia - otros": inf_otros,

        # Medicamentos
        "Medicamentos": st.session_state.meds,
        "Riesgo meds": riesgo,
        "Última dosis conocida": ultima_dosis,

        # Alergias
        "Alergia a medicamentos": alergia_meds,
        "Cuáles y reacción": cuales_reaccion,
        "Alergias alimentos/otras": alergias_otras,
        "Alergia a yodo/contraste": yodo,
        "Látex": latex,

        # Hábitos
        "Tabaco": tabaco,
        "Alcohol": alcohol,
        "Otras sustancias": otras_subs,
        "Café/energizantes": cafe,

        # Funcional
        "Estado habitual previo": estado_previo,
        "Movilidad": movilidad,
        "ABVD (baño/vestido/comer)": abvd,
        "Memoria/orientación habitual": memoria,

        # Barthel/SARC-F
        "Barthel total": str(barthel_total),
        "Barthel detalle": barthel_detalle,
        "SARC-F total": str(sarc_total),
        "SARC-F detalle": sarc_detalle,

        # 15 días
        "15d - visión": d_vision,
        "15d - cefalea": d_cef,
        "15d - migraña": d_mig,
        "15d - mareo": d_mareo,
        "15d - equilibrio": d_equ,
        "15d - caídas": d_caidas,
        "15d - confusión": d_conf,
        "15d - memoria": d_mem,
        "15d - focalidad": d_foc,
        "15d - habla": d_hab,
        "15d - sueño": d_sueno,
        "15d - otros": d_otros,

        # Prótesis
        "Prótesis - uso": pro_uso,
        "Prótesis - tipo": pro_tipo,
        "Prótesis - ubicación": pro_ubi,
        "Prótesis - molestias": pro_mol,
        "Prótesis - masticación": pro_mast,
        "Prótesis - última revisión": pro_rev,

        # Urgencias
        "Caídas recientes": caidas,
        "Marcapasos/implantes": implantes,
        "Vacunas/infecciones recientes": vacunas_inf,
        "Directiva anticipada": directiva,
        "Tipo de sangre": sangre,
        "Seguro/afiliación": seguro,

        # Anexos (listado)
        "Anexos": anexos_listado,
    }

    final_pdf_bytes = build_pdf_with_attachments(data, uploads)
    filename = f"Ficha_medica_{(nombre or 'paciente').replace(' ', '_')}_con_anexos.pdf"

    st.success("PDF generado (incluye anexos al final).")
    st.download_button(
        label="⬇️ Descargar PDF",
        data=final_pdf_bytes,
        file_name=filename,
        mime="application/pdf",
    )

    st.info("Tip: si van a urgencias, también ayuda llevar foto de frascos/recetas y una identificación.")

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
    """Construye PDF base (solo ficha) y regresa bytes."""
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

    # 9) Urgencias
    ensure_space()
    section("9) Datos útiles en urgencias")
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
    """Convierte una imagen a un PDF (1+ páginas) y regresa bytes."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=LETTER)
    width, height = LETTER

    left = 0.75 * inch
    right = 0.75 * inch
    top = height - 0.75 * inch
    bottom = 0.75 * inch

    # Título
    c.setFont("Helvetica-Bold", 12)
    c.drawString(left, top, f"Anexo (Imagen): {title}")
    y = top - 18

    # Cargar imagen
    img = Image.open(io.BytesIO(image_bytes))
    img_w, img_h = img.size

    # Caja disponible
    box_w = width - left - right
    box_h = (y - bottom)

    # Escala manteniendo aspecto
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
    """
    Genera el PDF final:
    - PDF base de ficha
    - + anexos como páginas (PDFs se anexan; imágenes se convierten a PDF y se anexan)
    """
    base = build_base_pdf(data)
    parts = [base]

    if uploads:
        for uf in uploads:
            name = uf.name
            b = uf.getvalue()
            # PDFs: anexar directo
            if name.lower().endswith(".pdf"):
                parts.append(b)
            # Imágenes: convertir a páginas
            elif name.lower().endswith((".png", ".jpg", ".jpeg")):
                parts.append(image_to_pdf_page(b, name))
            else:
                # No anexamos otros tipos como páginas; ya se listan en el PDF
                pass

    return merge_pdfs(parts)


# ----------------------------
# UI Streamlit
# ----------------------------
st.set_page_config(page_title="Ficha médica (Adulto mayor)", layout="wide")
st.title("🩺 Ficha médica rápida (Adulto mayor) → PDF")
st.caption("Llena el formulario y al final descarga un PDF para llevar a urgencias/consulta.")

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

    st.divider()

    st.subheader("9) Datos útiles en urgencias")
    caidas = st.selectbox("Caídas recientes (últimos 30 días)", ["", "No", "Sí", "No sabe"])
    implantes = st.text_input("Marcapasos/implantes/metal (si aplica)")
    vacunas_inf = st.text_input("Vacunas/infecciones recientes (si aplica)")
    directiva = st.text_input("Directiva anticipada / voluntad (si existe)")
    sangre = st.text_input("Tipo de sangre (si se sabe)")
    seguro = st.text_input("Seguro/afiliación (IMSS/ISSSTE/privado/etc.)")

    submitted = st.form_submit_button("📄 Generar PDF (con anexos)")


if submitted:
    # Lista de anexos (solo nombres en el resumen)
    anexos_listado = []
    if uploads:
        for uf in uploads:
            anexos_listado.append(uf.name)

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

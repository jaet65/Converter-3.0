# Creacion de reportes PDF y Excel a partir de archivos CSV
import os
import sys
import pandas as pd
import re
from datetime import time as dt_time


def generar_pdf_reportlab(path_pdf, df, titulo_doc):
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from PIL import Image as PILImage

    doc = SimpleDocTemplate(path_pdf, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    styles = getSampleStyleSheet()
    h1_style = ParagraphStyle('h1', parent=styles['h1'], fontSize=16, leading=18, alignment=0) 

    logo_elemento = None
    try:
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        logo_path = os.path.join(base_path, 'logo_TrackSIM.png')
        if os.path.exists(logo_path):
            logo_pil = PILImage.open(logo_path)
            logo_pil.thumbnail((120, 60))
            logo_elemento = Image(logo_path, width=logo_pil.width, height=logo_pil.height)
            logo_elemento.hAlign = 'LEFT'
    except Exception as e:
        print(f"Error al procesar logo: {e}")

    texto_titulo = Paragraph("Reporte de conducción TrackSIM", h1_style)
    if logo_elemento:
        tabla_header = Table([[logo_elemento, texto_titulo]], colWidths=[130, 422])
        tabla_header.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (1, 0), (1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
        ]))
        story.append(tabla_header)
    else:
        story.append(texto_titulo)
    story.append(Spacer(1, 15))

    table_data = df.values.tolist()
    if not table_data:
        doc.build(story)
        return
    specs = {"Informe de sesión":4,"Condiciones iniciales":2,"Marcas": 3, "Resumen de marcas": 2, "Indicadores genéricos": 3}
    sections = []
    for i, row in enumerate(table_data):
        if row and str(row[0]).strip() in specs:
            sections.append({'keyword': str(row[0]).strip(), 'index': i})
    if not sections: return
    header_chunk = table_data[0:sections[0]['index']]
    if header_chunk:
        style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=9)
        wrapped = [[Paragraph(str(c), style) for c in r] for r in header_chunk]
        story.append(Table(wrapped, hAlign='LEFT', colWidths=[doc.width / len(r) for r in header_chunk][:1]))
        story.append(Spacer(1, 20))
    for i, sec in enumerate(sections):
        chunk = table_data[sec['index']:(sections[i+1]['index'] if i+1<len(sections) else len(table_data))]
        if chunk:
            data = [r[:specs.get(sec['keyword'], 1)] for r in chunk]
            style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=9)
            h_style = ParagraphStyle('Header', parent=style, fontName='Helvetica-Bold',textColor=colors.whitesmoke)
            wrapped = [[Paragraph(str(c), h_style) for c in data[0]]] + [[Paragraph(str(c), style) for c in r] for r in data[1:]]
            section_table = Table(wrapped, hAlign='LEFT', colWidths=[doc.width/len(data[0])]*len(data[0]))
            section_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#e9540d")),
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('BOTTOMPADDING', (0,0), (-1,0), 6),
            ]))
            story.append(section_table)
            story.append(Spacer(1, 20))
    doc.build(story)

def generar_excel_con_formato(path_xlsx, df):
    """
    Genera un archivo Excel a partir de un DataFrame, aplicando formatos específicos
    para números y tiempos (hh:mm).
    """
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Reporte"

    for r_idx, row in enumerate(df.values, 1):  # openpyxl is 1-indexed
        for c_idx, value in enumerate(row, 1):
            cell = ws.cell(row=r_idx, column=c_idx)
            if value is None or value == '':
                cell.value = ''
                continue

            value_str = str(value).strip()

            # Intenta convertir a número
            try:
                # Evita convertir valores que parecen fecha pero no lo son
                if len(value_str) > 15:
                    raise ValueError("String is too long for a number")
                num_value = float(value_str)
                cell.value = num_value
                if num_value == int(num_value):
                    cell.number_format = '0'
                else:
                    cell.number_format = '0.00'
                continue
            except (ValueError, TypeError):
                pass

            # Intenta tratarlo como formato de tiempo hh:mm
            if re.match(r'^\d{1,2}:\d{2}$', value_str):
                try:
                    h, m = map(int, value_str.split(':'))
                    if 0 <= h < 24 and 0 <= m < 60:
                        cell.value = dt_time(h, m)
                        cell.number_format = 'hh:mm'
                        continue
                except ValueError:
                    pass
            
            # Si nada de lo anterior funciona, es un string
            cell.value = value_str
    
    wb.save(path_xlsx)

def procesar_un_archivo(args):
    file_path, ruta_minor_report, ruta_converted, to_pdf, to_excel = args
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lineas = [l.strip() for l in f.readlines()]
        rows = []
        max_cols = 0
        for l in lineas:
            cols = [c.replace('"', '').strip() for c in l.split(';')]
            rows.append(cols)
            if len(cols) > max_cols: max_cols = len(cols)
        for r in rows:
            while len(r) < max_cols: r.append("")
        df = pd.DataFrame(rows)
        try:
            if df.shape[1] > 2:
                c2, c3 = df.iat[5, 1], df.iat[5, 2]
                df.iat[5, 1], df.iat[5, 2] = c3, c2
        except Exception: pass
        for r in range(df.shape[0]):
            for c in range(df.shape[1]):
                if "Tiempo de uso del freno continuo" in str(df.iloc[r,c]) and "m" in str(df.iloc[r,c+2]):
                    df.iloc[r, c+2] = "seg"
        try:
            if "Scania R450 Remolque Simple" in str(df.iloc[12,1]):
                idx = df[df[0].astype(str).str.contains("Indicadores",na=False)].index[0] + 10
                df = pd.concat([df.iloc[:idx], pd.DataFrame([["----","0"]+[""]*(max_cols-2),["----","0"]+[""]*(max_cols-2)]), df.iloc[idx:]],ignore_index=True)
        except: pass
        my_file = str(df.iloc[6, 2]).strip() if df.shape[0]>6 and df.shape[1]>2 else ""
        my_file2 = str(df.iloc[3, 1]).strip() if df.shape[0]>3 and df.shape[1]>1 else ""
        filename_base = "".join(c for c in f"{my_file or os.path.splitext(os.path.basename(file_path))[0]}__{my_file2 or 'Reporte'}" if c.isalnum() or c in ' _-').rstrip()
        id_file = 0
        while True:
            path_pdf = os.path.join(ruta_minor_report, f"{filename_base}{id_file}.pdf")
            path_xlsx = os.path.join(ruta_converted, f"{filename_base}{id_file}.xlsx")
            if (not to_pdf or not os.path.exists(path_pdf)) and (not to_excel or not os.path.exists(path_xlsx)):
                break
            id_file += 1
        if to_pdf: generar_pdf_reportlab(path_pdf, df, filename_base)
        if to_excel: generar_excel_con_formato(path_xlsx, df)
        return (True, f"OK: {os.path.basename(file_path)}")
    except Exception as e:
        return (False, f"ERROR: {os.path.basename(file_path)} -> {e}")

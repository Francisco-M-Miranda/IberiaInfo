import os
from flask import Flask, render_template, request, send_file, send_from_directory
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak, Frame, PageTemplate
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from werkzeug.utils import secure_filename
from PIL import Image as PILImage
import zipfile
from datetime import datetime
import io

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def generate_files(data, antes_path, despues_path):
    # Crear nombre del archivo basado en PDV, Categoría y fecha
    fecha = datetime.now().strftime("%Y%m%d")
    nombre_base =f"Informe_{fecha}"
    
    # Crear buffer en memoria para el ZIP
    zip_buffer = io.BytesIO()
    
    # Crear el archivo ZIP en memoria
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # Generar archivo de texto con los datos
        txt_content = io.StringIO()
        txt_content.write(f"PDV: {data['pdv']}\n")
        txt_content.write(f"Categoría: {data['categoria']}\n")
        txt_content.write(f"Observaciones: {data['observaciones']}\n\n")
        txt_content.write("Productos:\n")
        for i in range(len(data['producto'])):
            txt_content.write(f"\nProducto: {data['producto'][i]}\n")
            txt_content.write(f"Caras después: {data['caras_despues'][i]}\n")
            txt_content.write(f"Total Caras: {data['total_caras'][i]}\n")
            txt_content.write(f"Participación: {data['participacion'][i]}\n")
            txt_content.write(f"Inventario: {data['inventario'][i]}\n")
        
        # Agregar el archivo de texto al ZIP
        zipf.writestr(f"{nombre_base}.txt", txt_content.getvalue())
        
        # Agregar las imágenes al ZIP
        with PILImage.open(antes_path) as img:
            img_buffer = io.BytesIO()
            img.save(img_buffer, format="JPEG")
            img_buffer.seek(0)
            zipf.writestr("Antes.jpg", img_buffer.getvalue())
        
        with PILImage.open(despues_path) as img:
            img_buffer = io.BytesIO()
            img.save(img_buffer, format="JPEG")
            img_buffer.seek(0)
            zipf.writestr("Despues.jpg", img_buffer.getvalue())
    
    zip_buffer.seek(0)
    return zip_buffer, f"{nombre_base}.zip"

def generate_pdf(data, antes_path, despues_path):
    # Crear nombre del archivo basado en PDV, Categoría y fecha
    fecha = datetime.now().strftime("%Y%m%d")
    nombre_base = f"Informe_{fecha}"
    
    # Crear el documento en memoria
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    
    styles = getSampleStyleSheet()
    
    # Estilos personalizados
    custom_style = ParagraphStyle(
        'ObservacionesStyle',
        parent=styles['BodyText'],
        spaceAfter=10,
        fontSize=12,
        fontName='Helvetica'
    )
    
    titulo_style = ParagraphStyle(
        'TituloStyle',
        parent=styles['Title'],
        fontSize=18,
        alignment=0,
        spaceAfter=10,
        fontName='Helvetica-Bold'
    )
    
    elements = []
    
    # Función para escalado proporcional de imágenes
    def get_scaled_size(img_path, max_width, max_height):
        with PILImage.open(img_path) as img:
            width, height = img.size
            ratio = min(max_width/width, max_height/height)
            return width*ratio, height*ratio
    
    # Cargar logos
    logo_iberia = Image(os.path.join(app.static_folder, 'images', 'iberia-logo.png'), width=100, height=50)
    logo_adp = Image(os.path.join(app.static_folder, 'images', 'adp-logo.jfif'), width=100, height=50)
    
    # Encabezado con logos
    header_table = Table([
        [
            logo_adp,
            Paragraph("INFORME MERCADEO", titulo_style),
            logo_iberia
        ]
    ], colWidths=[150, 300, 150])
    
    header_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (0,0), 'LEFT'),
        ('ALIGN', (1,0), (1,0), 'LEFT'),
        ('ALIGN', (2,0), (2,0), 'RIGHT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 10)
    ]))
    
    elements.append(header_table)
    
    # Datos básicos en tabla
    info_table = Table([
        ["PDV", data['pdv']],
        ["Categoria", data['categoria']],
        ["Observaciones", Paragraph(data['observaciones'], custom_style)]
    ], colWidths=[letter[0]/4, letter[0]*3/4 - 72])  # 72 es el margen total (36*2)
    
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#ED7D31')),
        ('TEXTCOLOR', (0,0), (0,-1), colors.whitesmoke),
        ('ALIGN', (0,0), (0,-1), 'CENTER'),
        ('ALIGN', (1,0), (1,-1), 'LEFT'),
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 12),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('BACKGROUND', (1,0), (1,-1), colors.HexColor('#FCECE8')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#FFFFFF')),
        ('FONTNAME', (1,0), (1,-1), 'Helvetica'),
        ('LEFTPADDING', (1,0), (1,-1), 8),
        ('RIGHTPADDING', (1,0), (1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'TOP')  # Alineación vertical superior
    ]))
    
    elements.append(info_table)
    
    # Tabla de productos
    table_data = [["Producto", "Caras despues", "Participacion", "Inventario"]]
    for row in zip(data['producto'], data['caras_despues'], data['participacion'], data['inventario']):
        table_data.append(list(row))
    
    # Calcular anchos de columna proporcionales
    available_width = letter[0] - 72  # Ancho total menos márgenes
    col_widths = [
        available_width * 0.4,  # Producto: 40% del ancho disponible
        available_width * 0.2,  # Caras después: 20% del ancho disponible
        available_width * 0.2,  # Participación: 20% del ancho disponible
        available_width * 0.2   # Inventario: 20% del ancho disponible
    ]
    
    product_table = Table(table_data, colWidths=col_widths)
    product_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#ED7D31')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 12),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('BACKGROUND', (0,1), (-1,-1), colors.HexColor('#FCECE8')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#FFFFFF')),
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,1), (-1,-1), 12)
    ]))
    
    elements.append(product_table)
    
    # Crear tabla para las imágenes lado a lado
    img_width = (letter[0] - 72) / 2  # Ancho disponible para cada imagen
    antes_width, antes_height = get_scaled_size(antes_path, img_width, 300)
    despues_width, despues_height = get_scaled_size(despues_path, img_width, 300)
    
    antes_img = Image(antes_path, width=antes_width, height=antes_height)
    despues_img = Image(despues_path, width=despues_width, height=despues_height)
    
    # Crear tabla con las imágenes lado a lado
    img_table = Table([
        [
            Paragraph("<b>ANTES</b>", custom_style),
            Paragraph("<b>DESPUES</b>", custom_style)
        ],
        [antes_img, despues_img]
    ], colWidths=[letter[0]/2 - 36, letter[0]/2 - 36])
    
    img_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5)
    ]))
    
    elements.append(img_table)
    
    try:
        doc.build(elements)
        buffer.seek(0)
        return buffer, f"{nombre_base}.pdf"
    except Exception as e:
        print(f"Error al generar PDF: {str(e)}")
        raise

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        try:
            # Obtener los datos del formulario
            caras_despues = request.form.getlist('caras_despues[]')
            total_caras = request.form.getlist('total_caras[]')
            
            # Calcular el porcentaje de participación
            participacion = []
            for i in range(len(caras_despues)):
                try:
                    if float(total_caras[i]) > 0:
                        porcentaje = (float(caras_despues[i]) / float(total_caras[i])) * 100
                        participacion.append(f"{porcentaje:.2f}%")
                    else:
                        participacion.append("0%")
                except (ValueError, ZeroDivisionError):
                    participacion.append("0%")
            
            # Corregir la indentación de este bloque
            data = {
                'pdv': request.form['pdv'],
                'categoria': request.form['categoria'],
                'observaciones': request.form['observaciones'],
                'producto': request.form.getlist('producto[]'),
                'caras_despues': caras_despues,
                'total_caras': total_caras,
                'participacion': participacion,
                'inventario': request.form.getlist('inventario[]')
            }
            
            antes_file = request.files['antes']
            despues_file = request.files['despues']
            
            if not antes_file or not despues_file:
                return "Error: Faltan archivos de imagen", 400
            
            antes_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(antes_file.filename))
            despues_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(despues_file.filename))
            
            antes_file.save(antes_path)
            despues_file.save(despues_path)
            
            # Determinar el tipo de generación solicitado
            generation_type = request.form.get('type', 'pdf')
            
            if generation_type == 'pdf':
                # Generar PDF
                pdf_buffer, filename = generate_pdf(data, antes_path, despues_path)
                response = send_file(
                    pdf_buffer,
                    as_attachment=True,
                    download_name=filename,
                    mimetype='application/pdf'
                )
                response.headers['X-Success-Message'] = 'PDF generado exitosamente'
            else:
                # Generar ZIP
                zip_buffer, filename = generate_files(data, antes_path, despues_path)
                response = send_file(
                    zip_buffer,
                    as_attachment=True,
                    download_name=filename,
                    mimetype='application/zip'
                )
                response.headers['X-Success-Message'] = 'Archivos ZIP generados exitosamente'
            
            # Limpiar archivos temporales
            os.remove(antes_path)
            os.remove(despues_path)
            
            return response
            
        except Exception as e:
            print(f"Error en el servidor: {str(e)}")
            return str(e), 500
    
    return send_from_directory('.', 'index.html')

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)
# Importaciones estándar
import os
import re
import pandas as pd
from collections import defaultdict
import traceback

# Importaciones para PDF
import pdfplumber
from PyPDF2 import PdfReader

# Importaciones PyQt5
from PyQt5.QtWidgets import (
    QWidget, 
    QVBoxLayout, 
    QHBoxLayout, 
    QPushButton,
    QFileDialog, 
    QLabel, 
    QProgressDialog,
    QTableWidget,
    QTableWidgetItem, 
    QMessageBox, 
    QTabWidget,
    QComboBox,
    QHeaderView,
    QApplication
)
from PyQt5.QtCore import Qt



# Constantes y configuración global
COLUMN_HEADERS = {
    "A": "Nombre del Vendedor",
    "B": "Tipo Documento",
    "C": "Prefijo",
    "D": "Documento Comprador",
    "E": "Fecha",
    "F": "Indicador IVA",
    "G": "Concepto",
    "H": "Cantidad",
    "I": "Unidad Medida",
    "J": "Base Gravable",
    "K": "Porcentaje IVA",
    "L": "NIT",
    "M": "Número Factura",
    "N": "Fecha Factura",
    "O": "Número Control",
    "P": "Total IVA",
    "Q": "Total INC",
    "R": "Total Bolsas",
    "S": "Otros Impuestos",
    "T": "IBUA",
    "U": "ICUI",
    "V": "Rete Fuente",
    "W": "Rete IVA",
    "X": "Rete ICA"
}


def get_invoice_type(filename, pdf_path, user_selected_type, prefijo_venta):
    """Determina el tipo de factura basado en la selección del usuario"""
    # Mapear tipos de documento con sus códigos internos
    type_mapping = {
        'Factura de Venta': 'factura_venta',
        'Factura de Compra': 'factura_compra',
        'Nota Crédito': 'nota_credito',
        'Nota Débito': 'nota_debito',
        'Facturas de Compras Nuevos': 'facturas_compras_nuevos',
        'Facturas de Gastos': 'facturas_gastos'
    }
    
    # Retornar el tipo de documento seleccionado por el usuario
    return type_mapping.get(user_selected_type)

def get_document_type(filepath):
    """Determina el tipo de documento basado en el contenido del archivo"""
    try:
        with pdfplumber.open(filepath) as pdf:
            text = pdf.pages[0].extract_text()
            
            # Verificar el tipo de documento basado en el texto
            if "Factura Electrónica de Venta" in text:
                return "Factura de Venta"
            elif "Nota Crédito de la Factura Electrónica" in text:
                return "Nota Crédito"
            elif "Nota Débito de la Factura Electrónica" in text:
                return "Nota Débito"
            elif "Factura de Compra Electrónica" in text:
                return "Factura de Compra"
            elif "Factura de Gastos" in text:
                return "Facturas de Gastos"
            elif "Compras Nuevos" in text:
                return "Facturas de Compras Nuevos"
            
            # Si no se puede determinar, retornar None
            return None
            
    except Exception as e:
        print(f"Error determinando tipo de documento: {str(e)}")
        return None

# Funciones auxiliares
def get_iva_indicator(iva_value, inc_value=None, inc_percent=None):
    """
    Determina el indicador IVA basado en el valor del IVA o INC
    
    Args:
        iva_value: Valor o porcentaje del IVA
        inc_value: Valor del INC por producto (opcional)
        inc_percent: Porcentaje del INC (opcional)
    """
    try:
        # Primero verificar si hay INC
        if inc_value and inc_percent:
            inc = float(str(inc_percent).replace(',', '.'))
            if inc in [4, 8, 16]:
                return "004"  # Si hay INC con estos porcentajes, es 004
        
        # Si no hay INC, verificar el IVA
        if isinstance(iva_value, (int, float)) or (isinstance(iva_value, str) and iva_value.replace('.', '').isdigit()):
            iva = float(str(iva_value).replace(',', '.'))
            if iva == 19:
                return "001"
            elif iva == 5:
                return "002"
            elif iva == 0:
                return "003"
            elif iva in [4, 8, 16]:  # Si el IVA tiene estos valores y no hubo INC, también es 004
                return "004"
        
        # Para campos especiales
        if 'IBUA' in str(iva_value).upper():
            return str(iva_value)
        elif 'ICUI' in str(iva_value).upper():
            return str(iva_value)
        elif 'OTROS IMPUESTOS' in str(iva_value).upper():
            return str(iva_value)
        
        return ""
    except (ValueError, TypeError):
        return ""

def parse_colombian_number(text):
    """Convierte un número en formato colombiano a float"""
    try:
        # Si el texto está vacío o es None, retornar 0
        if not text or text.isspace():
            return 0.0
            
        # Remover el símbolo de peso y espacios
        clean_text = text.replace('$', '').replace(' ', '')
        
        # Si después de limpiar está vacío, retornar 0
        if not clean_text:
            return 0.0
            
        if '.' in clean_text and ',' not in clean_text:
            clean_text = clean_text.replace('.', '')
            return float(clean_text)
        
        parts = clean_text.split(',')
        if len(parts) > 1:
            integer_part = parts[0].replace('.', '')
            decimal_part = parts[1][:2]
            return float(f"{integer_part}.{decimal_part}")
        else:
            return float(clean_text.replace('.', ''))
    except (ValueError, AttributeError):
        print(f"No se pudo convertir el valor: '{text}'")
        return 0.0
        

def extract_field(text, start_marker, end_marker):
    """Extrae un campo específico del texto entre dos marcadores"""
    try:
        start_index = text.find(start_marker)
        if start_index == -1:
            return ""
        start_index += len(start_marker)
        
        end_index = text.find(end_marker, start_index)
        if end_index == -1:
            return text[start_index:].strip()
            
        return text[start_index:end_index].strip()
    except Exception:
        return ""

def extract_total_impuestos(pdf):
    """Extrae los impuestos totales del documento"""
    impuestos = {
        'total_iva': 0.00,
        'total_inc': 0.00,
        'total_bolsas': 0.00,
        'ibua': 0.00,
        'icui': 0.00,
        'otros_impuestos': 0.00,
        'rete_fuente': 0.00,
        'rete_iva': 0.00,
        'rete_ica': 0.00
    }
    
    try:
        datos_totales_text = ""
        for page in pdf.pages:
            text = page.extract_text()
            if "Datos Totales" in text:
                datos_totales_text = text[text.find("Datos Totales"):]
                break
        
        if datos_totales_text:
            patrones = {
                'total_iva': [r'IVA\s*[\$\s]*([0-9.,]+)'],
                'total_inc': [r'INC\s*[\$\s]*([0-9.,]+)'],
                'total_bolsas': [r'Bolsas\s*[\$\s]*([0-9.,]+)'],
                'ibua': [r'IBUA\s*[\$\s]*([0-9.,]+)'],
                'icui': [r'ICUI\s*[\$\s]*([0-9.,]+)'],
                'otros_impuestos': [r'Otros impuestos\s*[\$\s]*([0-9.,]+)'],
                'rete_fuente': [r'Rete fuente\s*[\$\s]*([0-9.,]+)'],
                'rete_iva': [r'Rete IVA\s*[\$\s]*([0-9.,]+)'],
                'rete_ica': [r'Rete ICA\s*[\$\s]*([0-9.,]+)']
            }
            
            for impuesto, lista_patrones in patrones.items():
                for patron in lista_patrones:
                    match = re.search(patron, datos_totales_text, re.IGNORECASE)
                    if match:
                        valor_str = match.group(1).strip()
                        try:
                            valor = parse_colombian_number(valor_str)
                            impuestos[impuesto] = valor
                            break
                        except Exception as e:
                            print(f"Error convirtiendo valor para {impuesto}: {valor_str} - {str(e)}")
    except Exception as e:
        print(f"Error extrayendo impuestos: {str(e)}")
    
    return impuestos

def create_base_row(emisor, tipo_documento, numero_documento, fecha_emision, numero_factura, iva_percent, base_iva, impuestos, indicador_iva):
    """Crea una fila base con todos los valores"""
    row = {
        "A": emisor,
        "B": tipo_documento,
        "C": "",
        "D": numero_documento,
        "E": fecha_emision,
        "F": indicador_iva,
        "G": "PRINCIPAL",
        "H": "1",
        "I": "UNIDAD",
        "J": f"{base_iva:.2f}",
        "K": str(iva_percent),
        "L": numero_documento,
        "M": numero_factura,
        "N": fecha_emision,
        "O": numero_factura,
        "P": str(impuestos['total_iva']),
        "Q": str(impuestos['total_inc']),
        "R": str(impuestos['total_bolsas']),
        "S": str(impuestos['otros_impuestos']),  # Valor directo de Otros Impuestos
        "T": str(impuestos['ibua']), 
        "U": str(impuestos['icui']),            # Valor directo de IBUA
        "V": str(impuestos['rete_fuente']),
        "W": str(impuestos['rete_iva']),
        "X": str(impuestos['rete_ica'])
    }
    return row


    
# Funciones de procesamiento principales
def process_factura_venta(pdf_path):
    """Procesa una factura de venta"""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            first_page = pdf.pages[0]
            text = first_page.extract_text()
            
            # Extraer campos básicos
            nombre_vendedor = extract_field(text, "Razón Social:", "Nombre Comercial:")
            documento_comprador = None
            if "Número de Documento:" in text:
                documento_comprador = extract_field(text, "Número de Documento:", "Departamento:")
            elif "Número Documento:" in text:
                documento_comprador = extract_field(text, "Número Documento:", "Departamento:")
            
            fecha_emision = extract_field(text, "Fecha de Emisión:", "Medio de Pago:")
            numero_factura = extract_field(text, "Número de Factura:", "Forma de pago:")
            cufe = extract_field(text, "CUFE:", "Fecha de")  # Extraer el CUFE
            
            if not all([nombre_vendedor, documento_comprador, fecha_emision, numero_factura]):
                raise Exception("Archivo sin datos iniciales o incorrectos")
            
            impuestos = extract_total_impuestos(pdf)
            bases_por_iva = defaultdict(float)
            
            # Validar precios en todas las filas antes de procesar
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        if not row or len(row) < 11:
                            continue
                        
                        row = [str(cell).strip() if cell is not None else '' for cell in row]
                        if row[0].strip().isdigit():
                            try:
                                precio_unitario = parse_colombian_number(row[5])
                                precio_unitario_venta = parse_colombian_number(row[12])
                                
                                if precio_unitario > precio_unitario_venta:
                                    error_msg = {
                                        'numero_factura': numero_factura,
                                        'detalle': "Precio unitario mayor que precio de venta"
                                    }
                                    return error_msg
                            except Exception as e:
                                print(f"Error procesando fila: {str(e)}")
                                continue

            # Si pasa la validación, procesar normalmente
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        if not row or len(row) < 11:
                            continue
                        
                        row = [str(cell).strip() if cell is not None else '' for cell in row]
                        if row[0].strip().isdigit():
                            try:
                                # Extraer valores de la fila
                                precio_unitario = parse_colombian_number(row[5])
                                cantidad = parse_colombian_number(row[4])
                                descuento = parse_colombian_number(row[6]) if row[6].strip() else 0.0
                                iva_pesos = parse_colombian_number(row[8]) if row[8].strip() else 0.0
                                iva_percent = float(row[9].replace(',', '.')) if row[9].strip() else 0.0
                                precio_unitario_venta = parse_colombian_number(row[12])
                                
                                # Hacer la operación
                                precio_calculado = (precio_unitario * cantidad) - descuento
                                
                                # Comparar con precio unitario de venta
                                if abs(precio_calculado - precio_unitario_venta) < 0.1:
                                    # Tiene IVA incluido, restar IVA
                                    base_gravable = precio_calculado - iva_pesos
                                else:
                                    # No tiene IVA incluido
                                    base_gravable = precio_calculado
                                
                                # Agrupar por porcentaje de IVA
                                bases_por_iva[iva_percent] += base_gravable
                                
                            except Exception as e:
                                print(f"Error procesando fila: {str(e)}")
                                continue
            
            # Crear una fila por cada porcentaje de IVA único
            rows = []
            for iva_percent, base_total in bases_por_iva.items():
                new_row = create_base_row(
                    emisor=nombre_vendedor,
                    tipo_documento="Factura de Venta",
                    numero_documento=documento_comprador,
                    fecha_emision=fecha_emision,
                    numero_factura=numero_factura,
                    iva_percent=iva_percent,
                    base_iva=round(base_total, 2),
                    impuestos=impuestos,
                    indicador_iva=get_iva_indicator(iva_percent)
                )
                rows.append(new_row)
            
            return rows
            
    except Exception as e:
        print(f"Error procesando factura de venta: {str(e)}")
        return None

def process_factura_compra(pdf_path):
    try:
        with pdfplumber.open(pdf_path) as pdf:
            first_page = pdf.pages[0]
            text = first_page.extract_text()
            
            # Extraer campos básicos
            nombre_comprador = extract_field(text, "Nombre o Razón Social:", "Tipo de Documento:")
            nit_vendedor = extract_field(text, "Nit del Emisor:", "País:")
            fecha_emision = extract_field(text, "Fecha de Emisión:", "Medio de Pago:")
            numero_factura = extract_field(text, "Número de Factura:", "Forma de pago:")
            
            impuestos = extract_total_impuestos(pdf)
            
            # Variables para los descuentos
            suma_descuentos_detalle = 0
            descuento_global = 0
            total_bruto = 0
            suma_descuento_global = 0  # Nueva variable para la diferencia
            tiene_descuento_detalle = False
            
            for page in pdf.pages:
                text = page.extract_text()
                if "Datos Totales" in text:
                    datos_totales = text[text.find("Datos Totales"):]
                    
                    # Buscar total bruto primero
                    match = re.search(r'Total Bruto Factura\s*[\$\s]*([0-9.,]+)', datos_totales)
                    if match:
                        total_bruto = parse_colombian_number(match.group(1))
                    
                    # Buscar descuento global
                    match = re.search(r'Descuento Global \(-\)\s*[\$\s]*([0-9.,]+)', datos_totales)
                    if match:
                        descuento_global = parse_colombian_number(match.group(1))
                        # Calcular la diferencia correcta
                        suma_descuento_global = descuento_global  # El descuento global es el valor a mostrar
            
            # Procesar items y calcular sumas por IVA
            sumas_por_iva = defaultdict(float)
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        if not row or len(row) < 10:
                            continue
                            
                        row = [str(cell).strip() if cell is not None else '' for cell in row]
                        
                        if row[0].strip().isdigit():
                            try:
                                cantidad = parse_colombian_number(row[4])
                                precio_unitario = parse_colombian_number(row[5])
                                descuento = parse_colombian_number(row[6])
                                iva_pesos = parse_colombian_number(row[8])
                                iva_percent = float(row[9].replace(',', '.')) if row[9].strip() else 0.0
                                precio_venta = parse_colombian_number(row[12])

                                # Agregar validación de precios aquí
                                if precio_unitario > precio_venta:
                                    error_msg = {
                                        'numero_factura': numero_factura,
                                        'detalle': "Precio unitario mayor que precio de venta"
                                    }
                                    return error_msg

                                # Calcular base gravable
                                base_gravable = calcular_base_gravable(
                                    precio_unitario, 
                                    cantidad, 
                                    descuento, 
                                    iva_pesos, 
                                    precio_venta
                                )
                                
                                sumas_por_iva[iva_percent] += base_gravable
                                
                                if descuento > 0:
                                    suma_descuentos_detalle += descuento
                                    tiene_descuento_detalle = True
                            except Exception as e:
                                print(f"Error procesando línea: {str(e)}")
                                continue
            
            # Crear filas normales
            rows = []
            for iva_percent, base_iva in sumas_por_iva.items():
                row = create_base_row(
                    emisor=nombre_comprador,
                    tipo_documento="Factura de Compra",
                    numero_documento=nit_vendedor,
                    fecha_emision=fecha_emision,
                    numero_factura=numero_factura,
                    iva_percent=iva_percent,
                    base_iva=base_iva,
                    impuestos=impuestos,
                    indicador_iva=get_iva_indicator(iva_percent)
                )
                rows.append(row)
            
            # Crear filas de descuentos según el caso
            descuentos = []
            
            # Si hay descuento global > 0, usamos ese
            if descuento_global > 0:
                descuento = {
                    "datos del comprador": nombre_comprador,
                    "tipo de factura": "Factura de Compra",
                    "en blanco": "",
                    "nit vendedor": nit_vendedor,
                    "Fecha de Emisión": fecha_emision,
                    "tipo de descuento": "24080199",
                    "suma de descuentos": f"{suma_descuento_global:.2f}",  # Usamos el valor del descuento global
                    "cero": "0",
                    "factura": numero_factura,
                    "nit vendedor2": nit_vendedor,
                    "fecha emision": fecha_emision,
                    "factura2": numero_factura
                }
                descuentos.append(descuento)
            # Si no hay descuento global pero hay descuentos por item
            elif tiene_descuento_detalle:
                print(f"Agregando descuento por items para factura {numero_factura}: ${suma_descuentos_detalle:.2f}")
                descuento = {
                    "datos del comprador": nombre_comprador,
                    "tipo de factura": "Factura de Compra",
                    "en blanco": "",
                    "nit vendedor": nit_vendedor,
                    "Fecha de Emisión": fecha_emision,
                    "tipo de descuento": "42104001",
                    "suma de descuentos": f"{suma_descuentos_detalle:.2f}",
                    "cero": "0",
                    "factura": numero_factura,
                    "nit vendedor2": nit_vendedor,
                    "fecha emision": fecha_emision,
                    "factura2": numero_factura
                }
                descuentos.append(descuento)
            
            # Procesar inventario
            inventory_items = process_inventory_from_compra(pdf_path)
            
            return rows, inventory_items, descuentos
            
    except Exception as e:
        print(f"Error procesando factura de compra: {str(e)}")
        traceback.print_exc()
        return None, None, None

def process_nota_credito(pdf_path):
    """Procesa una nota crédito"""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            first_page = pdf.pages[0]
            text = first_page.extract_text()
            
            # Extraer campos básicos
            nombre_vendedor = extract_field(text, "Razón Social:", "Nombre Comercial:")
            
            # Intentar diferentes patrones para el documento del comprador
            documento_comprador = None
            if "Número de Documento:" in text:
                documento_comprador = extract_field(text, "Número de Documento:", "Departamento:")
            elif "Número Documento:" in text:
                documento_comprador = extract_field(text, "Número Documento:", "Departamento:")
            
            fecha_emision = extract_field(text, "Fecha de Emisión:", "Medio de Pago:")
            numero_factura = extract_field(text, "Número de Factura:", "Forma de pago:")
            
            impuestos = extract_total_impuestos(pdf)
            
            # Diccionario para agrupar bases gravables por porcentaje de IVA
            bases_por_iva = defaultdict(float)
            
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        if not row or len(row) < 11:
                            continue
                        
                        row = [str(cell).strip() if cell is not None else '' for cell in row]
                        if row[0].strip().isdigit():
                            try:
                                # Extraer valores de la fila
                                precio_unitario = parse_colombian_number(row[5])
                                cantidad = parse_colombian_number(row[4])
                                descuento = parse_colombian_number(row[6]) if row[6].strip() else 0.0
                                iva_pesos = parse_colombian_number(row[8]) if row[8].strip() else 0.0
                                iva_percent = float(row[9].replace(',', '.')) if row[9].strip() else 0.0
                                precio_unitario_venta = parse_colombian_number(row[12])
                                
                                # Calcular base gravable
                                base_gravable = calcular_base_gravable(
                                    precio_unitario, 
                                    cantidad, 
                                    descuento, 
                                    iva_pesos, 
                                    precio_unitario_venta
                                )
                                
                                # Agrupar por porcentaje de IVA
                                bases_por_iva[iva_percent] += base_gravable
                                
                            except Exception as e:
                                print(f"Error procesando fila: {str(e)}")
                                continue
            
            # Crear una fila por cada porcentaje de IVA único
            rows = []
            for iva_percent, base_total in bases_por_iva.items():
                new_row = create_base_row(
                    emisor=nombre_vendedor,
                    tipo_documento="Nota Crédito",  # Cambiado a Nota Crédito
                    numero_documento=documento_comprador,
                    fecha_emision=fecha_emision,
                    numero_factura=numero_factura,
                    iva_percent=iva_percent,
                    base_iva=round(base_total, 2),
                    impuestos=impuestos,
                    indicador_iva=get_iva_indicator(iva_percent)
                )
                rows.append(new_row)
            
            return rows
            
    except Exception as e:
        print(f"Error procesando nota crédito: {str(e)}")
        traceback.print_exc()
        return None

def process_nota_debito(pdf_path):
    """Procesa una nota débito"""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            first_page = pdf.pages[0]
            text = first_page.extract_text()
            
            # Extraer campos básicos
            nombre_vendedor = extract_field(text, "Razón Social:", "Nombre Comercial:")
            
            # Intentar diferentes patrones para el documento del comprador
            documento_comprador = None
            if "Número de Documento:" in text:
                documento_comprador = extract_field(text, "Número de Documento:", "Departamento:")
            elif "Número Documento:" in text:
                documento_comprador = extract_field(text, "Número Documento:", "Departamento:")
            
            fecha_emision = extract_field(text, "Fecha de Emisión:", "Medio de Pago:")
            numero_factura = extract_field(text, "Número de Factura:", "Forma de pago:")
            
            impuestos = extract_total_impuestos(pdf)
            
            # Diccionario para agrupar bases gravables por porcentaje de IVA
            bases_por_iva = defaultdict(float)
            
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        if not row or len(row) < 11:
                            continue
                        
                        row = [str(cell).strip() if cell is not None else '' for cell in row]
                        if row[0].strip().isdigit():
                            try:
                                # Extraer valores de la fila
                                precio_unitario = parse_colombian_number(row[5])
                                cantidad = parse_colombian_number(row[4])
                                descuento = parse_colombian_number(row[6]) if row[6].strip() else 0.0
                                iva_pesos = parse_colombian_number(row[8]) if row[8].strip() else 0.0
                                iva_percent = float(row[9].replace(',', '.')) if row[9].strip() else 0.0
                                precio_unitario_venta = parse_colombian_number(row[12])
                                
                                # Calcular base gravable
                                base_gravable = calcular_base_gravable(
                                    precio_unitario, 
                                    cantidad, 
                                    descuento, 
                                    iva_pesos, 
                                    precio_unitario_venta
                                )
                                
                                # Agrupar por porcentaje de IVA
                                bases_por_iva[iva_percent] += base_gravable
                                
                            except Exception as e:
                                print(f"Error procesando fila: {str(e)}")
                                continue
            
            # Crear una fila por cada porcentaje de IVA único
            rows = []
            for iva_percent, base_total in bases_por_iva.items():
                new_row = create_base_row(
                    emisor=nombre_vendedor,
                    tipo_documento="Nota Débito",  # Cambiado a Nota Débito
                    numero_documento=documento_comprador,
                    fecha_emision=fecha_emision,
                    numero_factura=numero_factura,
                    iva_percent=iva_percent,
                    base_iva=round(base_total, 2),
                    impuestos=impuestos,
                    indicador_iva=get_iva_indicator(iva_percent)
                )
                rows.append(new_row)
            
            return rows
            
    except Exception as e:
        print(f"Error procesando nota débito: {str(e)}")
        traceback.print_exc()
        return None

def process_facturas_compras_nuevos(pdf_path):
    """Procesa una factura de compras nuevos"""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            # Lógica similar a process_factura_compra
            # ...
            pass
    except Exception as e:
        print(f"Error procesando facturas de compras nuevos: {str(e)}")
        return None


def process_facturas_gastos(pdf_path):
    """Procesa una factura de gastos"""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            first_page = pdf.pages[0]
            text = first_page.extract_text()
            
            nombre_comprador = extract_field(text, "Nombre o Razón Social:", "Tipo de Documento:")
            numero_documento = extract_field(text, "Nit del Emisor:", "País:")
            fecha_emision = extract_field(text, "Fecha de Emisión:", "Medio de Pago:")
            numero_factura = extract_field(text, "Número de Factura:", "Forma de pago:")
            
            impuestos = extract_total_impuestos(pdf)
            
            sumas_por_iva = defaultdict(float)
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        if not row or len(row) < 10:
                            continue
                        row = [str(cell).strip() if cell is not None else '' for cell in row]
                        if row[0].strip().isdigit():
                            try:
                                precio_unitario = parse_colombian_number(row[5])
                                iva_percent = float(row[9].replace(',', '.'))
                                sumas_por_iva[iva_percent] += precio_unitario
                            except Exception as e:
                                print(f"Error procesando fila: {str(e)}")
                                continue
            
            rows = []
            for iva_percent, base_iva in sumas_por_iva.items():
                row = create_base_row(
                    emisor=nombre_comprador,
                    tipo_documento="Facturas de Gastos",
                    numero_documento=numero_documento,
                    fecha_emision=fecha_emision,
                    numero_factura=numero_factura,
                    iva_percent=iva_percent,
                    base_iva=base_iva,
                    impuestos=impuestos,
                    indicador_iva=get_iva_indicator(iva_percent)
                )
                rows.append(row)
            
            return rows
            
    except Exception as e:
        print(f"Error procesando facturas de gastos: {str(e)}")
        return None

def process_inventory(pdf_path):
    """Procesa el inventario de un documento PDF"""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            first_page = pdf.pages[0]
            text = first_page.extract_text()
            
            nit_emisor = extract_field(text, "Nit del Emisor:", "País:")
            numero_factura = extract_field(text, "Número de Factura:", "Forma de pago:")
            
            inventory_items = []
            
            for page in pdf.pages:
                tables = page.extract_tables()
                
                for table in tables:
                    for row in table:
                        if not row or len(row) < 11:
                            continue
                            
                        row = [str(cell).strip() if cell is not None else '' for cell in row]
                        
                        if row[0].strip().isdigit():
                            try:
                                item = {
                                    "nit_emisor": nit_emisor,
                                    "numero_factura": numero_factura,
                                    "Nro": row[0],
                                    "Codigo": row[1],
                                    "Descripcion": row[2],
                                    "U/M": row[3],
                                    "Cantidad": parse_colombian_number(row[4]),
                                    "Precio_unitario": parse_colombian_number(row[5].replace('$', '')),
                                    "Descuento": parse_colombian_number(row[6].replace('$', '')),
                                    "Recargo": parse_colombian_number(row[7].replace('$', '')),
                                    "IVA": parse_colombian_number(row[8].replace('$', '')),
                                    "Porcentaje_IVA": float(row[9].replace('%', '').strip() or '0'),
                                    "INC": parse_colombian_number(row[10].replace('$', '')),
                                    "Porcentaje_INC": float(row[11].replace('%', '').strip() or '0'),
                                    "Precio_venta": parse_colombian_number(row[12].replace('$', ''))
                                }
                                inventory_items.append(item)
                            except Exception as e:
                                print(f"Error procesando línea de inventario: {row}")
                                print(f"Error: {str(e)}")
                                continue
            
            return inventory_items
            
    except Exception as e:
        print(f"Error procesando inventario: {str(e)}")
        return None

def calcular_base_gravable(precio_unitario, cantidad, descuento, iva_pesos, precio_venta):
    """
    Calcula la base gravable según si el precio incluye IVA o no
    """
    subtotal = precio_unitario * cantidad - descuento
    
    # Si el subtotal más IVA es igual al precio de venta, el precio incluye IVA
    if round(subtotal, 2) == round(precio_venta, 2):
        # El precio incluye IVA, restamos el IVA en pesos
        return subtotal - iva_pesos
    else:
        # El precio no incluye IVA, usamos el subtotal directo
        return subtotal

def process_inventory_from_compra(pdf_path):
    try:
        with pdfplumber.open(pdf_path) as pdf:
            first_page = pdf.pages[0]
            text = first_page.extract_text()
            
            # Extraer campos básicos ajustando el límite del NIT
            nit_comprador = extract_field(text, "Número Documento:", "Departamento:").strip()
            nombre_comprador = extract_field(text, "Nombre o Razón Social:", "Tipo de Documento:").strip()
            nit_vendedor = extract_field(text, "Nit del Emisor:", "País:").strip()
            forma_pago = extract_field(text, "Forma de pago:", "Medio de Pago:").strip()
            numero_factura = extract_field(text, "Número de Factura:", "Forma de pago:").strip()
            
            inventory_items = []
            
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        if not row or len(row) < 11:
                            continue
                            
                        row = [str(cell).strip() if cell is not None else '' for cell in row]
                        
                        if row[0].strip().isdigit():
                            try:
                                # Función para formatear números
                                def format_number(value):
                                    try:
                                        num = float(value)
                                        # Si el número es entero, no mostrar decimales
                                        if num.is_integer():
                                            return str(int(num))
                                        # Si tiene decimales, mostrar máximo 2
                                        return f"{num:.2f}"
                                    except:
                                        return value

                                item = {
                                    "NIT Comprador": nit_comprador,
                                    "Nombre Comprador": nombre_comprador,
                                    "NIT Vendedor": nit_vendedor,
                                    "Forma Pago": forma_pago,
                                    "Número Factura": numero_factura,
                                    "Nro": row[0],
                                    "Codigo": row[1],
                                    "Descripcion": row[2],
                                    "U/M": row[3],
                                    "Cantidad": format_number(parse_colombian_number(row[4])),
                                    "Precio_unitario": format_number(parse_colombian_number(row[5].replace('$', ''))),
                                    "Descuento": format_number(parse_colombian_number(row[6].replace('$', ''))),
                                    "Recargo": format_number(parse_colombian_number(row[7].replace('$', ''))),
                                    "IVA": format_number(parse_colombian_number(row[8].replace('$', ''))),
                                    "Porcentaje_IVA": format_number(float(row[9].replace('%', '').strip() or '0')),
                                    "INC": format_number(parse_colombian_number(row[10].replace('$', ''))),
                                    "Porcentaje_INC": format_number(float(row[11].replace('%', '').strip() or '0')),
                                    "Precio_venta": format_number(parse_colombian_number(row[12].replace('$', ''))),
                                    "Base_gravable": format_number(calcular_base_gravable(
                                        parse_colombian_number(row[5].replace('$', '')),
                                        parse_colombian_number(row[4]),
                                        parse_colombian_number(row[6].replace('$', '')),
                                        parse_colombian_number(row[8].replace('$', '')),
                                        parse_colombian_number(row[12].replace('$', ''))
                                    ))
                                }
                                inventory_items.append(item)
                                
                            except Exception as e:
                                print(f"Error procesando línea de inventario: {row}")
                                print(f"Error detallado: {str(e)}")
                                continue
            
            return inventory_items
            
    except Exception as e:
        print(f"Error general procesando inventario: {str(e)}")
        traceback.print_exc()
        return None

def extract_emisor_info(text):
    """Extrae información del emisor del texto del PDF"""
    info = {}
    
    # Extraer dirección
    direccion_match = re.search(r"Dirección:\s*(.*?)(?=\n|Teléfono|Email)", text)
    if direccion_match:
        info['direccion'] = direccion_match.group(1).strip()
    
    # Extraer teléfono
    telefono_match = re.search(r"Teléfono:\s*(.*?)(?=\n|Email)", text)
    if telefono_match:
        info['telefono'] = telefono_match.group(1).strip()
    
    # Extraer email
    email_match = re.search(r"Email:\s*(.*?)(?=\n)", text)
    if email_match:
        info['email'] = email_match.group(1).strip()
    
    # ... etc para los demás campos
    
    return info

def process_terceros(pdf_path):
    """Procesa un PDF para extraer información del emisor/vendedor"""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            first_page = pdf.pages[0]
            text = first_page.extract_text()
            
            # Imprimir para debug
            print(f"\nProcesando {pdf_path}")
            print("Texto extraído:")
            print(text[:500])  # Primeros 500 caracteres
            
            # Buscar la sección del emisor con un patrón más flexible
            emisor_section = re.search(r"(?:Datos del Emisor|Datos del Vendedor|Información del Emisor)(.*?)(?=Datos del|Información del|$)", text, re.DOTALL | re.IGNORECASE)
            if not emisor_section:
                print(f"No se encontró sección de emisor en {pdf_path}")
                return None
                
            text_emisor = emisor_section.group(1)
            print("\nTexto del emisor encontrado:")
            print(text_emisor)
            
            # Patrones ajustados para capturar la información completa
            patterns = {
                'Razón Social': r"(?:Razón Social|Nombre):\s*(.*?)(?=\n|Nombre|$)",
                'Nombre Comercial': r"(?:Nombre Comercial|Nombre de Establecimiento):\s*(.*?)(?=\n|Nit|$)",
                'NIT del Emisor': r"(?:Nit del Emisor|NIT|Número de Identificación):\s*(.*?)(?=\n|País|$)",  # Cambiado
                'Tipo de Contribuyente': r"(?:Tipo de Contribuyente|Tipo):\s*(.*?)(?=\n|Departamento|$)",  # Cambiado
                'Responsabilidad Tributaria': r"(?:Responsabilidad Tributaria|Responsabilidad):\s*(.*?)(?=\n|Dirección|$)",  # Cambiado
                'Régimen Fiscal': r"(?:Régimen Fiscal|Régimen):\s*(.*?)(?=\n|Municipio|$)",  # Cambiado
                'Actividad Económica': r"(?:Actividad Económica|Actividad):\s*(.*?)(?=\n|Teléfono|Móvil|$)",  # Cambiado
                'Dirección': r"(?:Dirección|Domicilio):\s*(.*?)(?=\n|Teléfono|Móvil|$)",
                'Teléfono/Móvil': r"(?:Teléfono|Móvil|Tel):\s*(.*?)(?=\n|Correo|Email|$)",
                'Correo': r"(?:Correo|Email|E-mail):\s*(.*?)(?=\n|$)",
                'País': r"País:\s*(.*?)(?=\n|$)",
                'Departamento': r"(?:Departamento|Depto):\s*(.*?)(?=\n|$)",
                'Municipio': r"(?:Municipio|Ciudad):\s*(.*?)(?=\n|$)"
            }
            
            emisor = {}
            for field, pattern in patterns.items():
                match = re.search(pattern, text_emisor, re.IGNORECASE)
                if match:
                    emisor[field] = match.group(1).strip()
                else:
                    emisor[field] = ''
            
            if any(emisor.values()):
                return [emisor]
            return None
            
    except Exception as e:
        print(f"Error procesando terceros en {pdf_path}: {str(e)}")
        traceback.print_exc()
        return None

class ValidatorTab(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.files_to_process = []
        self.current_type = None
        self.setup_data_containers()

    def setup_data_containers(self):
        """Inicializa los contenedores de datos"""
        self.processed_data = {
            'venta': [],
            'compra': [],
            'credito': [],
            'debito': [],
            'errores': [],
            'inventario': [],
            'descuentos': [],
            'compras_nuevos': [],
            'gastos': []
        }

    def setup_tables(self):
        """Configura las tablas para mostrar resultados"""
        # Lista de encabezados en orden
        self.column_headers = [
            "Razón Social",
            "Tipo Documento",
            "Prefijo",
            "Número Documento",
            "Fecha",
            "Indicador IVA",
            "Concepto",
            "Cantidad",
            "Unidad Medida",
            "Base Gravable",
            "Porcentaje IVA",
            "NIT",
            "Número Factura",
            "Fecha Factura",
            "Número Control",
            "Total IVA",
            "Total INC",
            "Total Bolsas",
            "Otros Impuestos",
            "ICUI",
            "Rete Fuente",
            "Rete IVA",
            "Rete ICA"
        ]

        self.tables = {
            'venta': QTableWidget(),
            'compra': QTableWidget(),
            'credito': QTableWidget(),
            'debito': QTableWidget(),
            'errores': QTableWidget(),
            'inventario': QTableWidget(),
            'descuentos': QTableWidget(),
            'compras_nuevos': QTableWidget(),
            'gastos': QTableWidget()
        }

        for name, table in self.tables.items():
            # Configurar columnas y encabezados
            table.setColumnCount(len(self.column_headers))
            table.setHorizontalHeaderLabels(self.column_headers)
            
            # Otras configuraciones de la tabla
            table.setSelectionBehavior(QTableWidget.SelectRows)
            table.setAlternatingRowColors(True)
            
            header = table.horizontalHeader()
            header.setSectionResizeMode(QHeaderView.ResizeToContents)
            header.setStretchLastSection(True)
            
            # Estilo para la tabla y encabezados
            table.setStyleSheet("""
                QTableWidget {
                    gridline-color: #ccc;
                    background-color: white;
                    alternate-background-color: #f5f5f5;
                }
                QHeaderView::section {
                    background-color: #f0f0f0;
                    padding: 6px;
                    border: 1px solid #ccc;
                    font-weight: bold;
                    font-size: 12px;
                }
            """)
            
            self.tab_widget.addTab(table, name.capitalize())

   

    
    
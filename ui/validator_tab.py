from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                            QFileDialog, QLabel, QProgressDialog, QTableWidget,
                            QTableWidgetItem, QMessageBox, QTabWidget, QComboBox,
                            QHeaderView, QDialog, QCheckBox, QProgressBar, QApplication, QStyle)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QSize
import pandas as pd
import os
from PyPDF2 import PdfReader
from core.pdf_processor import (process_factura_venta, process_factura_compra,
                             process_nota_credito, process_nota_debito,
                             process_facturas_gastos, process_inventory, 
                             get_document_type, COLUMN_HEADERS, process_terceros)
import pdfplumber
import logging
import time
import traceback

class ExportSelectionDialog(QDialog):
    def __init__(self, available_tabs, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Seleccionar hojas para exportar")
        self.selected_tabs = []
        
        layout = QVBoxLayout()
        
        # Añadir label con instrucciones
        label = QLabel("Seleccione las hojas que desea exportar:")
        layout.addWidget(label)
        
        # Crear checkboxes para cada tab
        self.checkboxes = {}
        for tab_name in available_tabs:
            if tab_name.lower() != 'errores':  # Opcional: excluir la pestaña de errores
                checkbox = QCheckBox(tab_name.capitalize())
                self.checkboxes[tab_name] = checkbox
                layout.addWidget(checkbox)
        
        # Botones de aceptar y cancelar
        buttons_layout = QHBoxLayout()
        accept_button = QPushButton("Exportar")
        cancel_button = QPushButton("Cancelar")
        
        accept_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        
        buttons_layout.addWidget(accept_button)
        buttons_layout.addWidget(cancel_button)
        layout.addLayout(buttons_layout)
        
        self.setLayout(layout)
    
    def get_selected_tabs(self):
        return [name for name, checkbox in self.checkboxes.items() if checkbox.isChecked()]

class ValidatorTab(QWidget):
    def __init__(self):
        super().__init__()
        self.files_to_process = []
        self.current_type = None
        self.processing = False
        
        # Inicializar componentes de UI
        self.files_label = None
        self.select_btn = None
        self.doc_type_combo = None
        self.process_btn = None
        self.progress_bar = None
        self.stop_button = None
        self.tab_widget = None
        
        # Configurar UI
        self.setup_ui()
        self.setup_data_containers()
        
        # Mapeos para procesamiento de documentos
        self.processor_map = {
            'Factura de Venta': process_factura_venta,
            'Factura de Compra': process_factura_compra,
            'Nota Crédito': process_nota_credito,
            'Nota Débito': process_nota_debito,
            'Terceros': process_terceros
        }
        
        self.type_to_key = {
            'Factura de Venta': 'venta',
            'Factura de Compra': 'compra',
            'Nota Crédito': 'credito',
            'Nota Débito': 'debito',
            'Terceros': 'terceros'
        }

    def setup_data_containers(self):
        """Inicializa los contenedores de datos"""
        self.processed_data = {
            'venta': [],
            'compra': [],
            'credito': [],
            'debito': [],
            'inventario': [],
            'descuentos': [],
            'terceros': [],
            'errores': []  # Movido al final
        }

    def setup_ui(self):
        layout = QVBoxLayout()
        
        # Instrucciones
        instructions = QLabel(
            "Pasos a seguir:\n"
            "1. Seleccione los archivos PDF a procesar\n"
            "2. Elija el tipo de documento\n"
            "3. Haga clic en 'Procesar Documentos'"
        )
        instructions.setStyleSheet("""
            QLabel {
                padding: 10px;
                background: #f0f0f0;
                border-radius: 5px;
                font-size: 14px;
                margin: 10px 0;
            }
        """)
        layout.addWidget(instructions)

        # Panel superior
        top_panel = QHBoxLayout()

        # Estilos comunes para los botones
        button_style = """
            QPushButton {
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 15px;
                font-size: 13px;
            }
            QPushButton:hover {
                opacity: 0.8;
            }
            QPushButton:pressed {
                opacity: 0.6;
            }
        """

        # Botón seleccionar archivos
        self.select_btn = QPushButton('1. Seleccionar PDFs')
        self.select_btn.setIcon(self.style().standardIcon(QStyle.SP_DialogOpenButton))
        self.select_btn.clicked.connect(self.select_files)
        self.select_btn.setStyleSheet(button_style + """
            QPushButton {
                background-color: #2962FF;
            }
        """)

        # Selector de tipo de documento
        doc_type_widget = QWidget()
        doc_type_layout = QHBoxLayout(doc_type_widget)
        doc_type_label = QLabel("2. Tipo de documento:")
        
        self.doc_type_combo = QComboBox()
        self.doc_type_combo.addItems([
            'Factura de Venta',
            'Factura de Compra',
            'Nota Crédito',
            'Nota Débito',
            'Terceros'
        ])

        doc_type_layout.addWidget(doc_type_label)
        doc_type_layout.addWidget(self.doc_type_combo)

        # Botón de procesar
        self.process_btn = QPushButton('3. Procesar')
        self.process_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.process_btn.clicked.connect(self.process_files)
        self.process_btn.setEnabled(False)
        self.process_btn.setStyleSheet(button_style + """
            QPushButton {
                background-color: #00C853;
            }
            QPushButton:disabled {
                background-color: #A5D6A7;
            }
        """)

        # Botón de limpiar (más pequeño)
        self.clear_btn = QPushButton()  # Sin texto, solo ícono
        self.clear_btn.setIcon(self.style().standardIcon(QStyle.SP_TrashIcon))
        self.clear_btn.setIconSize(QSize(16, 16))
        self.clear_btn.setFixedSize(32, 32)  # Tamaño fijo más pequeño
        self.clear_btn.setToolTip('Limpiar tabla actual')  # Tooltip para mostrar función
        self.clear_btn.clicked.connect(self.clear_current_tab)
        self.clear_btn.setStyleSheet(button_style + """
            QPushButton {
                background-color: #FF3D00;
                padding: 5px;
            }
        """)

        # Botón de exportar
        self.export_btn = QPushButton('Exportar')
        self.export_btn.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
        self.export_btn.clicked.connect(self.export_to_excel)
        self.export_btn.setStyleSheet(button_style + """
            QPushButton {
                background-color: #6200EA;
            }
        """)

        # Agregar espaciador antes de los botones de acción
        top_panel.addStretch()
        
        # Agregar los botones al panel
        top_panel.addWidget(self.select_btn)
        top_panel.addWidget(doc_type_widget)
        top_panel.addWidget(self.process_btn)
        top_panel.addSpacing(10)  # Espacio entre botones
        top_panel.addWidget(self.clear_btn)
        top_panel.addSpacing(10)  # Espacio entre botones
        top_panel.addWidget(self.export_btn)
        
        layout.addLayout(top_panel)

        # Label para archivos seleccionados
        self.files_label = QLabel('No hay archivos seleccionados')
        self.files_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #666;
                margin: 10px 0;
            }
        """)
        layout.addWidget(self.files_label)

        # TabWidget para resultados
        self.tab_widget = QTabWidget()
        self.setup_tables()
        layout.addWidget(self.tab_widget)

        # Barra de progreso y botón de cancelar
        bottom_panel = QHBoxLayout()
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("Procesando: %p% (%v/%m archivos)")
        self.progress_bar.hide()
        
        self.stop_button = QPushButton("Detener Proceso")
        self.stop_button.clicked.connect(self.stop_processing)
        self.stop_button.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
            QPushButton:pressed {
                background-color: #bd2130;
            }
        """)
        self.stop_button.hide()
        
        bottom_panel.addWidget(self.progress_bar)
        bottom_panel.addWidget(self.stop_button)
        
        layout.addLayout(bottom_panel)

        self.setLayout(layout)

    def setup_tables(self):
        """Configura las tablas para mostrar resultados"""
        # Headers generales para la mayoría de las tablas
        self.column_headers = [
            "Nombre del Vendedor", "Tipo Documento", "Prefijo", "Documento Comprador",
            "Fecha", "Indicador IVA", "Concepto", "Cantidad", "Unidad Medida",
            "Base Gravable", "Porcentaje IVA", "NIT", "Número Factura", "Fecha Factura",
            "Número Control", "Total IVA", "Total INC", "Total Bolsas", "Otros Impuestos",
            "ICUI", "Rete Fuente", "Rete IVA", "Rete ICA"
        ]

        # Headers específicos para tipos especiales
        self.special_headers = {
            'inventario': [
                "NIT Comprador", "Nombre Comprador", "NIT Vendedor", "Forma Pago",
                "Número Factura", "Nro", "Codigo", "Descripcion", "U/M", "Cantidad",
                "Precio_unitario", "Descuento", "Recargo", "IVA", "Porcentaje_IVA",
                "INC", "Porcentaje_INC", "Precio_venta", "Base_gravable"
            ],
            'descuentos': [
                "datos del comprador", "tipo de factura", "en blanco", "nit vendedor",
                "Fecha de Emisión", "tipo de descuento", "suma de descuentos", "cero",
                "factura", "nit vendedor2", "fecha emision", "factura2"
            ],
            'terceros': [
                "Razón Social", "Nombre Comercial", "NIT del Emisor", "Tipo de Contribuyente",
                "Responsabilidad Tributaria", "Régimen Fiscal", "Actividad Económica",
                "Dirección", "Teléfono/Móvil", "Correo", "País", "Departamento", "Municipio"
            ]
        }

        # Definir el orden específico de las pestañas
        tab_order = [
            'venta',
            'compra',
            'credito',
            'debito',
            'inventario',
            'descuentos',
            'terceros',
            'errores'  # Errores al final
        ]

        # Crear las tablas en el orden deseado
        self.tables = {}
        for tab_name in tab_order:
            self.tables[tab_name] = QTableWidget()
            table = self.tables[tab_name]
            
            # Usar headers específicos para tipos especiales
            headers = self.special_headers.get(tab_name, self.column_headers)
            table.setColumnCount(len(headers))
            table.setHorizontalHeaderLabels(headers)
            
            # Configuraciones de la tabla
            table.setSelectionBehavior(QTableWidget.SelectRows)
            table.setAlternatingRowColors(True)
            
            header = table.horizontalHeader()
            header.setSectionResizeMode(QHeaderView.ResizeToContents)
            header.setStretchLastSection(True)
            
            # Estilo para la tabla
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
            
            # Agregar la tabla al tab_widget en el orden especificado
            self.tab_widget.addTab(table, tab_name.capitalize())

    def select_files(self):
        """Permite al usuario seleccionar archivos PDF"""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Seleccionar PDFs a procesar",
            "",
            "PDF Files (*.pdf)"
        )
        
        if files:
            self.files_to_process = files
            self.files_label.setText(f'Archivos seleccionados: {len(files)}')
            self.process_btn.setEnabled(True)

    def stop_processing(self):
        """Detiene el procesamiento actual"""
        self.processing = False
        self.process_btn.setEnabled(True)
        self.select_btn.setEnabled(True)
        self.doc_type_combo.setEnabled(True)
        self.progress_bar.hide()
        self.stop_button.hide()

    def process_files(self):
        """Procesa los archivos seleccionados"""
        if not self.files_to_process:
            QMessageBox.warning(self, "Error", "No hay archivos seleccionados")
            return
        
        doc_type = self.doc_type_combo.currentText()
        processor = self.processor_map.get(doc_type)
        
        if not processor:
            return
        
        # Si es procesamiento de terceros, pedir Excel base
        if doc_type == 'Terceros':
            reply = QMessageBox.information(
                self,
                "Procesar Terceros",
                "A continuación seleccione el archivo Excel con los NITs existentes.\n\n"
                "Los nuevos emisores serán agregados automáticamente.",
                QMessageBox.Ok | QMessageBox.Cancel
            )
            
            if reply == QMessageBox.Ok:
                excel_path, _ = QFileDialog.getOpenFileName(
                    self,
                    "Seleccionar Excel de NITs",
                    "",
                    "Excel Files (*.xlsx *.xls)"
                )
                
                if not excel_path:
                    return
                    
                try:
                    # Cargar NITs existentes
                    df_nits = pd.read_excel(excel_path)
                    
                    # Buscar la columna que contenga NIT (más flexible)
                    nit_column = None
                    for col in df_nits.columns:
                        if 'NIT' in str(col).upper():
                            nit_column = col
                            break
                    
                    if not nit_column:
                        QMessageBox.warning(
                            self,
                            "Error",
                            "No se encontró una columna con NITs en el Excel.\n"
                            "Asegúrese que el archivo tenga una columna que contenga 'NIT' en su nombre."
                        )
                        return
                        
                    nits_existentes = set(str(nit) for nit in df_nits[nit_column].dropna())
                    
                    # Informar cuántos NITs se cargaron
                    QMessageBox.information(
                        self,
                        "Excel Cargado",
                        f"Se cargaron {len(nits_existentes)} NITs del archivo Excel.\n\n"
                        "Se procederá a procesar los documentos."
                    )
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Error cargando Excel: {str(e)}")
                    return
            else:
                return
        
        self.processing = True
        self.process_btn.setEnabled(False)
        self.select_btn.setEnabled(False)
        self.doc_type_combo.setEnabled(False)
        
        self.progress_bar.setMaximum(len(self.files_to_process))
        self.progress_bar.setValue(0)
        self.progress_bar.show()
        self.stop_button.show()
        
        processed = 0
        errors = 0
        nuevos_emisores = 0
        
        try:
            for i, filepath in enumerate(self.files_to_process):
                if not self.processing:
                    break
                    
                filename = os.path.basename(filepath)
                self.progress_bar.setValue(i)
                self.progress_bar.setFormat(f"Procesando: {filename} (%p%)")
                
                try:
                    if doc_type == 'Factura de Compra':
                        result = processor(filepath)
                        if result:
                            rows, inventario, descuentos = result if len(result) == 3 else (result, None, None)
                            if rows:
                                self.processed_data['compra'].extend(rows)
                                processed += 1
                                self.update_single_table('compra')
                            if inventario:
                                self.processed_data['inventario'].extend(inventario)
                                self.update_single_table('inventario')
                            if descuentos:
                                self.processed_data['descuentos'].extend(descuentos)
                                self.update_single_table('descuentos')
                    elif doc_type == 'Terceros':
                        rows = processor(filepath)
                        if rows:
                            # Verificar si es un emisor nuevo
                            for row in rows:
                                nit = row.get('NIT del Emisor', '')
                                if nit and nit not in nits_existentes:
                                    nuevos_emisores += 1
                                    nits_existentes.add(nit)
                        
                        key = self.type_to_key.get(doc_type)
                        if key:
                            self.processed_data[key].extend(rows)
                            processed += 1
                            self.update_single_table(key)
                    else:
                        rows = processor(filepath)
                        if rows:
                            key = self.type_to_key.get(doc_type)
                            if key:
                                self.processed_data[key].extend(rows)
                                processed += 1
                                self.update_single_table(key)
                
                except Exception as e:
                    errors += 1
                    print(f"Error procesando {filename}: {str(e)}")
                    self.processed_data['errores'].append({
                        'Factura': filename,
                        'Error': str(e)
                    })
                    self.update_single_table('errores')
                
                QApplication.processEvents()
                
        finally:
            self.processing = False
            self.process_btn.setEnabled(True)
            self.select_btn.setEnabled(True)
            self.doc_type_combo.setEnabled(True)
            self.progress_bar.hide()
            self.stop_button.hide()
            
            # Mensaje final para terceros
            if doc_type == 'Terceros':
                QMessageBox.information(
                    self,
                    "Proceso Completado",
                    f"Procesamiento finalizado:\n"
                    f"- Archivos procesados: {processed}\n"
                    f"- Nuevos emisores encontrados: {nuevos_emisores}\n"
                    f"- Errores: {errors}"
                )
            else:
                QMessageBox.information(
                    self,
                    "Proceso Completado",
                    f"Procesamiento finalizado:\n"
                    f"- Archivos procesados: {processed}\n"
                    f"- Errores: {errors}"
                )

    def update_single_table(self, data_type):
        try:
            if data_type not in self.tables:
                print(f"Tabla {data_type} no encontrada")
                return
            
            table = self.tables[data_type]
            data_list = self.processed_data[data_type]
            
            print(f"\nActualizando tabla {data_type}")
            print(f"Datos disponibles: {len(data_list)}")
            
            if not data_list:
                table.setRowCount(0)
                return
            
            # Configurar el número de filas
            table.setRowCount(len(data_list))
            
            # Usar los headers correctos según el tipo
            headers = self.special_headers.get(data_type, self.column_headers)
            
            # Llenar la tabla según el tipo
            for row_idx, row_data in enumerate(data_list):
                if data_type in ['terceros', 'inventario', 'descuentos']:
                    for col_idx, header in enumerate(headers):
                        value = str(row_data.get(header, ''))
                        item = QTableWidgetItem(value)
                        table.setItem(row_idx, col_idx, item)
                else:
                    if isinstance(row_data, list):
                        for col_idx, _ in enumerate(headers):
                            value = str(row_data[col_idx] if col_idx < len(row_data) else '')
                            item = QTableWidgetItem(value)
                            table.setItem(row_idx, col_idx, item)
                    else:
                        for col_idx, _ in enumerate(headers):
                            letra = chr(65 + col_idx)
                            value = str(row_data.get(letra, ''))
                            item = QTableWidgetItem(value)
                            table.setItem(row_idx, col_idx, item)
            
            # Ajustar el tamaño de las columnas
            table.resizeColumnsToContents()
            QApplication.processEvents()
            
        except Exception as e:
            print(f"Error actualizando tabla {data_type}: {str(e)}")
            traceback.print_exc()

    def export_to_excel(self):
        # Obtener solo las pestañas que tienen datos
        available_tabs = [name for name, table in self.tables.items() if table.rowCount() > 0]
        
        if not available_tabs:
            QMessageBox.warning(self, "Error", "No hay datos para exportar")
            return
        
        # Mostrar diálogo de selección
        dialog = ExportSelectionDialog(available_tabs, self)
        if dialog.exec_() == QDialog.Accepted:
            selected_tabs = dialog.get_selected_tabs()
            
            if not selected_tabs:
                QMessageBox.warning(self, "Error", "No se seleccionaron hojas para exportar")
                return
            
            # Pedir al usuario la ubicación para guardar el archivo
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Guardar Excel",
                "",
                "Excel Files (*.xlsx)"
            )
            
            if file_path:
                try:
                    with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                        for tab_name in selected_tabs:
                            df = self.table_to_dataframe(self.tables[tab_name])
                            df.to_excel(writer, sheet_name=tab_name.capitalize(), index=False)
                
                    QMessageBox.information(self, "Éxito", "Archivo exportado correctamente")
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Error al exportar: {str(e)}")
    
    def table_to_dataframe(self, table):
        # Convertir QTableWidget a DataFrame
        data = []
        headers = []
        
        # Obtener headers
        for col in range(table.columnCount()):
            headers.append(table.horizontalHeaderItem(col).text())
        
        # Obtener datos
        for row in range(table.rowCount()):
            row_data = []
            for col in range(table.columnCount()):
                item = table.item(row, col)
                row_data.append(item.text() if item else '')
            data.append(row_data)
        
        return pd.DataFrame(data, columns=headers)

    def clear_current_tab(self):
        """Limpia solo la pestaña actual"""
        current_tab = self.tab_widget.currentWidget()
        current_tab_name = self.tab_widget.tabText(self.tab_widget.currentIndex()).lower()
        
        reply = QMessageBox.question(
            self,
            "Confirmar Limpieza",
            f"¿Está seguro que desea limpiar los datos de la pestaña '{current_tab_name}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Limpiar solo los datos de la pestaña actual
            self.processed_data[current_tab_name] = []
            current_tab.setRowCount(0)
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                            QFileDialog, QLabel, QProgressDialog, QTableWidget,
                            QTableWidgetItem, QMessageBox, QTabWidget, QComboBox,
                            QHeaderView, QDialog, QCheckBox, QProgressBar)
from PyQt5.QtCore import Qt
import pandas as pd
import os
from PyPDF2 import PdfReader
from core.pdf_processor import (process_factura_venta, process_factura_compra,
                             process_nota_credito, process_nota_debito,
                             process_facturas_compras_nuevos, process_facturas_gastos,
                             process_inventory, get_document_type, COLUMN_HEADERS)
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QFileDialog, QLabel, QProgressDialog, QTableWidget,
                             QTableWidgetItem, QMessageBox, QTabWidget, QComboBox,
                             QHeaderView, QApplication)  #
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
            'Facturas de Compras Nuevos': process_facturas_compras_nuevos,
            'Facturas de Gastos': process_facturas_gastos
        }
        
        self.type_to_key = {
            'Factura de Venta': 'venta',
            'Factura de Compra': 'compra',
            'Nota Crédito': 'credito',
            'Nota Débito': 'debito',
            'Facturas de Compras Nuevos': 'compras_nuevos',
            'Facturas de Gastos': 'gastos'
        }

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

        # Botón seleccionar archivos
        self.select_btn = QPushButton('1. Seleccionar PDFs')
        self.select_btn.clicked.connect(self.select_files)
        self.select_btn.setStyleSheet("""
            QPushButton {
                background-color: #1a73e8;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 10px 20px;
                font-size: 14px;
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
            'Facturas de Compras Nuevos',
            'Facturas de Gastos'
        ])

        doc_type_layout.addWidget(doc_type_label)
        doc_type_layout.addWidget(self.doc_type_combo)

        # Botón de procesar
        self.process_btn = QPushButton('3. Procesar Documentos')
        self.process_btn.clicked.connect(self.process_files)
        self.process_btn.setEnabled(False)

        top_panel.addWidget(self.select_btn)
        top_panel.addWidget(doc_type_widget)
        top_panel.addWidget(self.process_btn)
        
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
        self.column_headers = {
            'venta': [
                "Nombre del Vendedor",
                "Tipo Documento",
                "Prefijo",
                "Documento Comprador",
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
            ],
            'compra': [
                "Nombre del Comprador",
                "Tipo Documento",
                "Prefijo",
                "NIT Vendedor",
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
            ],
            'inventario': [
                "NIT Comprador",
                "Nombre Comprador",
                "NIT Vendedor", 
                "Forma Pago",
                "Número Factura",
                "Nro",
                "Codigo",
                "Descripcion",
                "U/M",
                "Cantidad",
                "Precio_unitario",
                "Descuento",
                "Recargo",
                "IVA",
                "Porcentaje_IVA",
                "INC",
                "Porcentaje_INC",
                "Precio_venta",
                "Base_gravable"
            ]
        }

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

        # Configurar cada tabla con sus encabezados específicos
        for name, table in self.tables.items():
            headers = self.column_headers.get(name, self.column_headers['venta'])  # usar headers de venta por defecto
            table.setColumnCount(len(headers))
            table.setHorizontalHeaderLabels(headers)
            
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
            
        # Iniciar procesamiento
        self.processing = True
        self.process_btn.setEnabled(False)
        self.select_btn.setEnabled(False)
        self.doc_type_combo.setEnabled(False)
        
        # Mostrar barra de progreso y botón de detener
        self.progress_bar.setMaximum(len(self.files_to_process))
        self.progress_bar.setValue(0)
        self.progress_bar.show()
        self.stop_button.show()
        
        processed = 0
        errors = 0
        
        try:
            for i, filepath in enumerate(self.files_to_process):
                if not self.processing:
                    break
                    
                filename = os.path.basename(filepath)
                self.progress_bar.setValue(i)
                self.progress_bar.setFormat(f"Procesando: {filename} (%p%)")
                QApplication.processEvents()
                
                try:
                    doc_type = self.doc_type_combo.currentText()
                    processor = self.processor_map.get(doc_type)
                    
                    if processor:
                        if doc_type == 'Factura de Compra':
                            result = processor(filepath)
                            if result:
                                rows, inventario, descuentos = result if len(result) == 3 else (result, None, None)
                                if rows:
                                    self.processed_data['compra'].extend(rows)
                                    processed += 1
                                    # Actualizar tabla de compras inmediatamente
                                    self.update_single_table('compra')
                                if inventario:
                                    self.processed_data['inventario'].extend(inventario)
                                    self.update_single_table('inventario')
                                if descuentos:
                                    self.processed_data['descuentos'].extend(descuentos)
                                    self.update_single_table('descuentos')
                        else:
                            rows = processor(filepath)
                            if rows:
                                key = self.type_to_key.get(doc_type)
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
                
                # Actualizar UI
                QApplication.processEvents()
        
        finally:
            # Restaurar estado de la UI
            self.processing = False
            self.process_btn.setEnabled(True)
            self.select_btn.setEnabled(True)
            self.doc_type_combo.setEnabled(True)
            self.progress_bar.hide()
            self.stop_button.hide()
            
            # Mostrar resumen
            QMessageBox.information(
                self,
                "Proceso Completado",
                f"Procesamiento finalizado:\n"
                f"- Archivos procesados: {processed}\n"
                f"- Errores: {errors}"
            )

    def update_single_table(self, data_type):
        """Actualiza una tabla específica"""
        try:
            if data_type not in self.tables:
                print(f"Tabla {data_type} no encontrada")
                return
            
            table = self.tables[data_type]
            data_list = self.processed_data[data_type]
            
            print(f"\nActualizando tabla {data_type}")
            print(f"Datos disponibles: {len(data_list)}")
            
            if not data_list:
                print(f"No hay datos para la tabla {data_type}")
                table.setRowCount(0)
                return
            
            # Configurar el número de filas
            table.setRowCount(len(data_list))
            
            # Llenar la tabla según el tipo
            if data_type in ['venta', 'compra', 'credito', 'debito']:
                # Usar letras para estos tipos
                for row_idx, row_data in enumerate(data_list):
                    for col_idx, header in enumerate(self.column_headers.get(data_type, [])):
                        value = str(row_data.get(chr(65 + col_idx), ''))
                        item = QTableWidgetItem(value)
                        table.setItem(row_idx, col_idx, item)
            else:
                # Usar nombres de columnas para inventario y otros
                headers = self.column_headers.get(data_type, [])
                for row_idx, row_data in enumerate(data_list):
                    for col_idx, header in enumerate(headers):
                        value = str(row_data.get(header, ''))
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
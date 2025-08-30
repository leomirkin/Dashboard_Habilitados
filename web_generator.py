import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

class WebGenerator:
    def __init__(self, data_file: str = "recursos_data.json"):
        self.data_file = Path(data_file)
        self.output_dir = Path("web_output")
        self.output_dir.mkdir(exist_ok=True)
        
    def cargar_datos(self) -> Dict:
        """Carga los datos del scraping
        
        IMPORTANTE: Este método lee SOLO el archivo actual de datos (recursos_data.json).
        No acumula datos de scrapings anteriores. Cada vez que se ejecuta el scraping,
        se sobrescribe el archivo completo, asegurando que solo se muestren los datos más recientes.
        """
        try:
            if not self.data_file.exists():
                logger.error(f"Archivo de datos no encontrado: {self.data_file}")
                return {"recursos": [], "fecha_actualizacion": datetime.now().isoformat(), "total_recursos": 0}
                
            with open(self.data_file, 'r', encoding='utf-8') as f:
                datos = json.load(f)
                
            # Consolidar recursos duplicados antes de retornar
            recursos_consolidados = self._consolidar_recursos_duplicados(datos.get('recursos', []))
            datos['recursos'] = recursos_consolidados
            datos['total_recursos'] = len(recursos_consolidados)
            
            return datos
                
        except Exception as e:
            logger.error(f"Error cargando datos: {str(e)}")
            return {"recursos": [], "fecha_actualizacion": datetime.now().isoformat(), "total_recursos": 0}
    
    def _consolidar_recursos_duplicados(self, recursos: List[Dict]) -> List[Dict]:
        """Consolida recursos duplicados basándose en campos clave únicos
        
        Esta función identifica y consolida recursos que son exactamente iguales,
        evitando mostrar filas duplicadas en el HTML. La consolidación se basa en:
        
        - Para contratistas: CUIT + Proveedor + Cliente + Edificio
        - Para trabajadores: CUIL + Nombre + Proveedor + Cliente + Edificio  
        - Para vehículos: Dominio + Marca + Modelo + Proveedor + Cliente + Edificio
        
        Retorna una lista de recursos únicos consolidados.
        """
        if not recursos:
            return []
        
        recursos_consolidados = {}
        recursos_duplicados_eliminados = 0
        
        for recurso in recursos:
            # Determinar el tipo de recurso basándose en la categoría
            categoria = (recurso.get('categoria') or '').lower()
            
            # Normalizar campos clave para evitar duplicados por diferencias menores
            cuit_cuil = str(recurso.get('cuit', recurso.get('cuil', ''))).strip()
            nombre = str(recurso.get('nombre', '')).strip().upper()
            proveedor = str(recurso.get('proveedor', '')).strip().upper()
            cliente = str(recurso.get('cliente', '')).strip().upper()
            edificio = str(recurso.get('edificio', '')).strip()
            dominio = str(recurso.get('dominio', '')).strip().upper()
            marca = str(recurso.get('marca', '')).strip().upper()
            modelo = str(recurso.get('modelo', '')).strip().upper()
            
            if 'grupo' in categoria or 'proveedor' in categoria or 'contratista' in categoria:
                # CONTRATISTAS: CUIT + Proveedor + Cliente + Edificio
                if not cuit_cuil or cuit_cuil == 'None':
                    continue  # Saltar recursos sin CUIT válido
                clave = (cuit_cuil, proveedor, cliente, edificio)
            elif 'persona' in categoria or 'trabajador' in categoria:
                # TRABAJADORES: CUIL + Nombre + Proveedor + Cliente + Edificio
                if not cuit_cuil or cuit_cuil == 'None' or not nombre or nombre == 'None':
                    continue  # Saltar recursos sin CUIL o nombre válido
                clave = (cuit_cuil, nombre, proveedor, cliente, edificio)
            elif 'veh' in categoria or 'maquin' in categoria:
                # VEHÍCULOS: Dominio + Marca + Modelo + Proveedor + Cliente + Edificio
                if not dominio or dominio == 'None':
                    continue  # Saltar recursos sin dominio válido
                clave = (dominio, marca, modelo, proveedor, cliente, edificio)
            else:
                # CATEGORÍA DESCONOCIDA: usar todos los campos relevantes
                clave = (cuit_cuil, nombre, proveedor, cliente, edificio, dominio, marca, modelo)
            
            # Filtrar claves vacías o inválidas
            clave_filtrada = tuple(val for val in clave if val and val != 'None' and val.strip())
            
            if len(clave_filtrada) < 2:  # Necesitamos al menos 2 campos válidos
                continue
            
            # Convertir la tupla a string para usar como clave del diccionario
            clave_str = '|'.join(clave_filtrada)
            
            if clave_str not in recursos_consolidados:
                # Primer recurso con esta clave - agregarlo
                recursos_consolidados[clave_str] = recurso
            else:
                # Recurso duplicado encontrado - consolidar información
                recursos_duplicados_eliminados += 1
                recurso_existente = recursos_consolidados[clave_str]
                
                # Si el recurso duplicado tiene información adicional, consolidarla
                if recurso.get('observaciones') and not recurso_existente.get('observaciones'):
                    recurso_existente['observaciones'] = recurso['observaciones']
                
                # Si el recurso duplicado tiene fecha más reciente, actualizarla
                if recurso.get('fecha_actualizacion') and not recurso_existente.get('fecha_actualizacion'):
                    recurso_existente['fecha_actualizacion'] = recurso['fecha_actualizacion']
                
                # Si el recurso duplicado tiene estado más favorable, mantenerlo
                estado_actual = (recurso_existente.get('estado') or '').lower()
                estado_nuevo = (recurso.get('estado') or '').lower()
                
                # Priorizar estados más favorables (habilitado > condicionado > bloqueado)
                if 'habilit' in estado_nuevo and 'habilit' not in estado_actual:
                    recurso_existente['estado'] = recurso['estado']
                elif 'condicion' in estado_nuevo and 'bloque' in estado_actual:
                    recurso_existente['estado'] = recurso['estado']
                
                # Agregar metadatos de consolidación
                if 'recursos_consolidados' not in recurso_existente:
                    recurso_existente['recursos_consolidados'] = 1
                recurso_existente['recursos_consolidados'] += 1
        
        # Convertir de vuelta a lista
        lista_consolidada = list(recursos_consolidados.values())
        
        if recursos_duplicados_eliminados > 0:
            logger.info(f"Consolidación completada: {len(lista_consolidada)} recursos únicos de {len(recursos)} originales")
            logger.info(f"Duplicados eliminados: {recursos_duplicados_eliminados}")
        
        return lista_consolidada
    
    def generar_estadisticas(self, datos: Dict) -> Dict:
        """Genera estadísticas de los recursos incluyendo KPIs detallados"""
        recursos = datos.get("recursos", [])
        
        # Limpiar datos: reemplazar valores "Desconocido" con valores por defecto apropiados
        recursos_limpios = []
        for recurso in recursos:
            recurso_limpio = recurso.copy()
            
            # Si no hay cliente, usar el contratista como cliente
            if not recurso_limpio.get("cliente") or recurso_limpio.get("cliente") == "Desconocido":
                recurso_limpio["cliente"] = recurso_limpio.get("contratista", "Sin Cliente")
            
            # Si no hay contratista, usar el cliente como contratista
            if not recurso_limpio.get("contratista") or recurso_limpio.get("contratista") == "Desconocido":
                recurso_limpio["contratista"] = recurso_limpio.get("cliente", "Sin Contratista")
            
            # Si no hay edificio, usar "Sin especificar"
            if not recurso_limpio.get("edificio") or recurso_limpio.get("edificio") == "Desconocido":
                recurso_limpio["edificio"] = "Sin especificar"
            
            recursos_limpios.append(recurso_limpio)
        
        recursos = recursos_limpios
        
        stats = {
            "total": len(recursos),
            "por_cliente": {},
            "por_contratista": {},
            "por_estado": {},
            "por_edificio": {},
            "habilitados": 0,
            "kpis_por_cliente": {},
            "kpis_generales": {
                "habilitados": 0,
                "bloqueados": 0,
                "condicionados": 0
            }
        }
        
        for recurso in recursos:
            cliente = recurso.get("cliente", "Sin Cliente")
            contratista = recurso.get("contratista", "Sin Contratista")
            estado = (recurso.get("estado") or "").lower()
            edificio = recurso.get("edificio", "Sin especificar")
            
            # Contar por cliente
            stats["por_cliente"][cliente] = stats["por_cliente"].get(cliente, 0) + 1
            
            # Contar por contratista
            stats["por_contratista"][contratista] = stats["por_contratista"].get(contratista, 0) + 1
            
            # Contar por estado
            stats["por_estado"][estado] = stats["por_estado"].get(estado, 0) + 1
            
            # Contar por edificio
            stats["por_edificio"][edificio] = stats["por_edificio"].get(edificio, 0) + 1
            
            # Clasificar estados para KPIs - orden sensible para evitar falsos positivos ("inhabilitado" contiene "habilitado")
            if any(term in estado for term in ["inhabilit", "no habilit", "rechaz", "baja"]):
                stats["kpis_generales"]["bloqueados"] += 1
                estado_kpi = "bloqueados"
            elif any(term in estado for term in ["bloqueado", "bloquea", "inactivo", "vencido", "bloqueada", "inactiva", "vencida", "suspendido", "suspendida"]):
                stats["kpis_generales"]["bloqueados"] += 1
                estado_kpi = "bloqueados"
            elif any(term in estado for term in ["condicion", "pendiente", "observacion", "condicionada", "observada", "revision", "revisión"]):
                stats["kpis_generales"]["condicionados"] += 1
                estado_kpi = "condicionados"
            else:
                # Si no coincide con ninguno, asumir que está habilitado por defecto
                stats["habilitados"] += 1
                stats["kpis_generales"]["habilitados"] += 1
                estado_kpi = "habilitados"
            
            # KPIs por cliente
            if cliente not in stats["kpis_por_cliente"]:
                stats["kpis_por_cliente"][cliente] = {
                    "total": 0,
                    "habilitados": 0,
                    "bloqueados": 0,
                    "condicionados": 0,
                    "edificios": {}
                }
            
            stats["kpis_por_cliente"][cliente]["total"] += 1
            stats["kpis_por_cliente"][cliente][estado_kpi] += 1
            
            # KPIs por edificio dentro de cada cliente
            if edificio not in stats["kpis_por_cliente"][cliente]["edificios"]:
                stats["kpis_por_cliente"][cliente]["edificios"][edificio] = {
                    "total": 0,
                    "habilitados": 0,
                    "bloqueados": 0,
                    "condicionados": 0
                }
            
            stats["kpis_por_cliente"][cliente]["edificios"][edificio]["total"] += 1
            stats["kpis_por_cliente"][cliente]["edificios"][edificio][estado_kpi] += 1
        
        return stats
    
    def generar_html(self):
        """Genera la interfaz web completa"""
        datos = self.cargar_datos()
        stats = self.generar_estadisticas(datos)
        
        html_content = f"""
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard - Recursos Habilitados</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #f8f9fa;
            min-height: 100vh;
            color: #2c3e50;
            margin: 0;
            padding: 0;
            width: 100%;
            box-sizing: border-box;
        }}
        
        .container {{
            width: 100%;
            margin: 0;
            padding: 0;
        }}
        
        .header {{
            background: white;
            color: #2c3e50;
            padding: 25px 40px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            border-bottom: 1px solid #ecf0f1;
            margin: 0;
            width: 100%;
            box-sizing: border-box;
            position: relative;
            left: 0;
            right: 0;
        }}
        
        .header-left {{
            display: flex;
            align-items: center;
            gap: 20px;
        }}
        
        .header-right {{
            display: flex;
            align-items: center;
            justify-content: flex-end;
        }}
        
        .logo-secco {{
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        
        .secco-logo {{
            height: 100px;
            width: auto;
            max-width: 250px;
            object-fit: contain;
        }}
        
        .logo {{
            width: 50px;
            height: 50px;
            background: #3498db;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
            font-size: 18px;
        }}
        
        .header-text {{
            display: flex;
            flex-direction: column;
        }}
        
        .date-subtle {{
            color: #95a5a6;
            font-size: 0.75em;
            font-weight: 400;
            margin-bottom: 4px;
            opacity: 0.8;
            letter-spacing: 0.5px;
        }}
        
        .admin-note {{
            color: #b0b4b9;
            font-size: 0.7em;
            font-weight: 400;
            margin-top: 2px;
            opacity: 0.7;
            font-style: italic;
        }}
        
        .header h1 {{
            color: #2c3e50;
            font-size: 2em;
            margin: 0;
            font-weight: 600;
            text-transform: uppercase;
        }}
        
        .header .subtitle {{
            color: #7f8c8d;
            font-size: 0.95em;
            margin-top: 5px;
            text-transform: uppercase;
        }}
        
        .header .date {{
            color: #7f8c8d;
            font-size: 0.9em;
            text-transform: uppercase;
        }}
        
        .content {{
            padding: 30px 40px;
            background: #f8f9fa;
        }}
        
        /* KPI Section Styles */
        .kpi-section {{
            margin-bottom: 30px;
        }}
        
        .kpi-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 20px;
        }}
        
        .kpi-header h2 {{
            color: #2c3e50;
            font-size: 1.5em;
            font-weight: 600;
            text-transform: uppercase;
            margin: 0;
        }}
        
        .kpi-reset-btn {{
            background: #95a5a6;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.9em;
            text-transform: uppercase;
            transition: background-color 0.3s ease;
        }}
        
        .kpi-reset-btn:hover {{
            background: #7f8c8d;
        }}
        
        .kpi-cards {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 25px;
        }}
        
        @media (max-width: 768px) {{
            .kpi-cards {{
                grid-template-columns: 1fr;
            }}
        }}
        
        .kpi-card {{
            background: white;
            border-radius: 12px;
            padding: 25px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
            border: 1px solid #ecf0f1;
            cursor: pointer;
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }}
        
        .kpi-card:hover {{
            transform: translateY(-3px);
            box-shadow: 0 6px 20px rgba(0, 0, 0, 0.15);
        }}
        
        .kpi-card.selected {{
            border-color: #3498db;
            box-shadow: 0 4px 15px rgba(52, 152, 219, 0.3);
        }}
        
        .kpi-card-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 15px;
        }}
        
        .kpi-title {{
            font-size: 1.1em;
            font-weight: 600;
            color: #2c3e50;
            text-transform: uppercase;
            margin: 0;
        }}
        
        .kpi-icon {{
            width: 40px;
            height: 40px;
            background: linear-gradient(135deg, #3498db, #2980b9);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 16px;
        }}
        
        .kpi-percentage {{
            font-size: 2.5em;
            font-weight: 700;
            color: #27ae60;
            margin: 10px 0;
            line-height: 1;
        }}
        
        .kpi-details {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.9em;
            color: #7f8c8d;
            text-transform: uppercase;
        }}
        
        .kpi-total {{
            font-weight: 600;
        }}
        
        .cliente-selector-container {{
            background: white;
            border-radius: 12px;
            padding: 25px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
            border: 1px solid #ecf0f1;
            margin-bottom: 20px;
        }}
        
        .selector-header {{
            display: flex;
            align-items: center;
            gap: 15px;
            margin-bottom: 20px;
        }}
        
        .selector-icon {{
            width: 40px;
            height: 40px;
            background: linear-gradient(135deg, #3498db, #2980b9);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 16px;
        }}
        
        .selector-title {{
            font-size: 1.1em;
            font-weight: 600;
            color: #2c3e50;
            text-transform: uppercase;
            margin: 0;
        }}
        
        .cliente-dropdown {{
            width: 100%;
            padding: 12px 15px;
            border: 2px solid #ecf0f1;
            border-radius: 8px;
            font-size: 1em;
            background: white;
            cursor: pointer;
            text-transform: uppercase;
            transition: all 0.3s ease;
            font-weight: 500;
        }}
        
        .cliente-dropdown:focus {{
            outline: none;
            border-color: #3498db;
            box-shadow: 0 0 0 3px rgba(52, 152, 219, 0.2);
        }}
        
        .cliente-dropdown:hover {{
            border-color: #bdc3c7;
        }}
        
        .kpi-card.cliente-selected {{
            display: block;
            animation: slideIn 0.3s ease-out;
        }}
        
        .kpi-card.cliente-hidden {{
            display: none;
        }}
        
        @keyframes slideIn {{
            from {{
                opacity: 0;
                transform: translateY(-10px);
            }}
            to {{
                opacity: 1;
                transform: translateY(0);
            }}
        }}
        
        .kpi-chart-container {{
            background: white;
            border-radius: 12px;
            padding: 25px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
            border: 1px solid #ecf0f1;
            display: none;
            margin-bottom: 25px;
        }}
        
        .kpi-chart-container.active {{
            display: block;
        }}
        
        .chart-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 20px;
            flex-wrap: wrap;
            gap: 15px;
        }}
        
        .chart-title {{
            font-size: 1.2em;
            font-weight: 600;
            color: #2c3e50;
            text-transform: uppercase;
            margin: 0;
        }}
        
        .chart-subtitle {{
            font-size: 0.9em;
            color: #7f8c8d;
            text-transform: uppercase;
        }}
        
        .edificio-selector {{
            padding: 8px 12px;
            border: 1px solid #ddd;
            border-radius: 6px;
            font-size: 0.9em;
            background: white;
            min-width: 200px;
            cursor: pointer;
            text-transform: uppercase;
        }}
        
        .chart-content {{
            display: grid;
            grid-template-columns: 1fr 300px;
            gap: 30px;
            align-items: center;
        }}
        
        .chart-canvas {{
            position: relative;
            height: 300px;
        }}
        
        .chart-legends {{
            display: flex;
            flex-direction: column;
            gap: 15px;
        }}
        
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 12px;
            background: #f8f9fa;
            border-radius: 8px;
            border-left: 4px solid;
        }}
        
        .legend-item.habilitados {{
            border-left-color: #27ae60;
        }}
        
        .legend-item.bloqueados {{
            border-left-color: #e74c3c;
        }}
        
        .legend-item.condicionados {{
            border-left-color: #f39c12;
        }}
        

        
        .legend-color {{
            width: 16px;
            height: 16px;
            border-radius: 50%;
        }}
        
        .legend-color.habilitados {{
            background: #27ae60;
        }}
        
        .legend-color.bloqueados {{
            background: #e74c3c;
        }}
        
        .legend-color.condicionados {{
            background: #f39c12;
        }}
        

        
        .legend-text {{
            flex: 1;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        .legend-label {{
            font-weight: 600;
            color: #2c3e50;
            text-transform: uppercase;
        }}
        
        .legend-value {{
            display: flex;
            flex-direction: column;
            text-align: right;
        }}
        
        .legend-count {{
            font-size: 1.2em;
            font-weight: 700;
            color: #2c3e50;
        }}
        
        .legend-percentage {{
            font-size: 0.9em;
            color: #7f8c8d;
        }}
        
        /* Estilos para indicadores de registros y edificios */
        .registros-info, .edificios-info {{
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            padding: 8px 12px;
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            border-radius: 6px;
            border: 1px solid #dee2e6;
            color: #495057;
            font-weight: 500;
            transition: all 0.2s ease;
            cursor: pointer;
        }}
        
        .registros-info:hover, .edificios-info:hover {{
            background: linear-gradient(135deg, #e9ecef 0%, #dee2e6 100%);
            border-color: #adb5bd;
            transform: translateY(-1px);
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        
        .registros-count, .edificios-count {{
            font-size: 1.1em;
            font-weight: 700;
            color: #495057;
            min-width: 20px;
            text-align: center;
        }}
        
        .registros-label, .edificios-label {{
            font-size: 0.9em;
            color: #6c757d;
            text-transform: lowercase;
        }}
        
        .expand-icon {{
            font-size: 0.8em;
            color: #6c757d;
            margin-left: 4px;
            transition: transform 0.2s ease;
        }}
        
        .tree-row:hover .expand-icon,
        .tree-client:hover .expand-icon {{
            transform: translateY(1px);
        }}
        
        /* Mejoras en las filas expandibles */
        .tree-row, .tree-client {{
            transition: background-color 0.2s ease;
        }}
        
        .tree-row:hover, .tree-client:hover {{
            background-color: #f8f9fa !important;
        }}
        
        @media (max-width: 768px) {{
            .chart-content {{
                grid-template-columns: 1fr;
                gap: 20px;
            }}
            
            .chart-canvas {{
                height: 250px;
            }}
            
            .kpi-cards {{
                grid-template-columns: 1fr;
            }}
            
            .chart-header {{
                flex-direction: column;
                align-items: stretch;
            }}
        }}
        
        .controls {{
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            border: 1px solid #ecf0f1;
        }}
        
        .filter-info {{
            margin-top: 15px;
            padding: 10px 15px;
            background: linear-gradient(135deg, #e8f5e8 0%, #d4edda 100%);
            border: 1px solid #c3e6cb;
            border-radius: 6px;
            text-align: center;
        }}
        
        .filter-indicator {{
            color: #155724;
            font-size: 0.9em;
            font-weight: 500;
            text-transform: uppercase;
        }}
        
        .search-bar {{
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
            align-items: center;
        }}
        
        .search-input {{
            flex: 1;
            min-width: 300px;
            padding: 10px 15px;
            border: 1px solid #ddd;
            border-radius: 6px;
            font-size: 14px;
            background: #f8f9fa;
            transition: border-color 0.3s ease;
            text-transform: uppercase;
        }}
        
        .search-input:focus {{
            outline: none;
            border-color: #3498db;
            background: white;
            box-shadow: 0 0 0 2px rgba(52, 152, 219, 0.2);
        }}
        
        .filter-select {{
            padding: 10px 15px;
            border: 1px solid #ddd;
            border-radius: 6px;
            font-size: 14px;
            background: white;
            min-width: 150px;
            cursor: pointer;
            text-transform: uppercase;
        }}
        
        .table-container {{
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            border: 1px solid #ecf0f1;
        }}
        
        table {{ 
            width: 100%; 
            border-collapse: collapse; 
        }}
        
        thead {{ 
            background: #34495e; 
            color: white; 
        }}
        
        th {{
            padding: 12px 15px;
            text-align: left;
            font-weight: 500;
            font-size: 0.9rem;
            border-bottom: 1px solid #bdc3c7;
            text-transform: uppercase;
        }}
        
        td {{
            padding: 12px 15px;
            border-bottom: 1px solid #ecf0f1;
            color: #2c3e50;
            font-size: 0.9rem;
            vertical-align: middle;
            text-transform: uppercase;
        }}
        
        /* Estilos para vista colapsable tipo árbol */
        .tree-row {{
            cursor: pointer;
            font-weight: 600;
            background: #f8f9fa;
        }}
        
        .tree-row:hover {{
            background: #e9ecef;
        }}
        
        .tree-client {{
            cursor: pointer;
            padding-left: 30px;
            background: #ffffff;
            border-left: 3px solid #3498db;
        }}
        
        .tree-client:hover {{
            background: #f1f3f4;
        }}
        
        .tree-building {{
            padding-left: 60px;
            background: #fafafa;
            border-left: 3px solid #95a5a6;
            font-size: 0.85rem;
        }}
        
        .tree-building:hover {{
            background: #f0f0f0;
        }}
        
        .tree-icon {{
            display: inline-block;
            width: 16px;
            height: 16px;
            margin-right: 8px;
            text-align: center;
            font-size: 12px;
            transition: transform 0.2s ease;
        }}
        
        .tree-icon.expanded {{
            transform: rotate(90deg);
        }}
        
        .tree-hidden {{
            display: none;
        }}
        
        /* Removemos el nth-child automático para controlarlo dinámicamente */
        tbody tr {{
            background: white;
        }}
        
        tbody tr.row-even {{
            background: #f8f9fa;
        }}
        
        tbody tr:hover {{
            background: #e8f4f8 !important;
        }}
        
        thead tr {{
            background: #34495e;
        }}
        
        thead tr:hover {{
            background: #34495e;
        }}
        
        .estado-dot {{ 
            display: inline-block; 
            width: 20px; 
            height: 20px; 
            border-radius: 50%; 
            margin: 0 auto;
            text-align: center;
        }}
        
        /* Centrar los círculos de estado en la columna Estado */
        #tablaProveedores td:nth-child(4) {{ /* Columna Estado en tabla Contratistas */
            text-align: center;
        }}
        
        #tablaPersonas td:nth-child(7) {{ /* Columna Estado en tabla Trabajadores */
            text-align: center;
        }}
        
        #tablaVehiculos td:nth-child(8) {{ /* Columna Estado en tabla Vehículos */
            text-align: center;
        }}
        
        .estado-dot.verde {{ background: #27ae60; }}
        .estado-dot.rojo {{ background: #e74c3c; }}
        .estado-dot.amarillo {{ background: #f1c40f; }}
        .estado-dot.gris {{ background: #95a5a6; }}
        

        

        
        .estado {{
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 0.85em;
            font-weight: 600;
            text-transform: uppercase;
        }}
        
        .estado.habilitado {{
            background-color: #d4edda;
            color: #155724;
        }}
        
        .estado.deshabilitado {{
            background-color: #f8d7da;
            color: #721c24;
        }}
        
        .estado.pendiente {{
            background-color: #fff3cd;
            color: #856404;
        }}
        
        @media (max-width: 768px) {{
            .header {{
                flex-direction: column;
                text-align: center;
                gap: 15px;
            }}
            
            .search-bar {{
                flex-direction: column;
            }}
            
            .search-input {{
                min-width: 100%;
            }}
            
            table {{
                font-size: 0.9em;
            }}
            
            th, td {{
                padding: 10px 8px;
            }}
        }}
        
        .footer {{
            background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
            border-top: 1px solid #34495e;
            margin-top: 40px;
            padding: 25px 0;
            color: #ecf0f1;
        }}
        
        .footer-content {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 20px;
        }}
        
        .footer-text {{
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 8px;
        }}
        
        .gcg-brand {{
            font-size: 1.1em;
            font-weight: 600;
            color: #ecf0f1;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        
        .copyright {{
            font-size: 0.85em;
            color: #bdc3c7;
            opacity: 0.8;
        }}
        
        .no-data {{
            text-align: center;
            padding: 50px;
            color: #7f8c8d;
            font-size: 1.2em;
        }}
        

    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="header-left">
                <div class="logo">GCG</div>
                <div class="header-text">
                    <div class="date-subtle">Actualizado el {datetime.fromisoformat(datos.get('fecha_actualizacion', datetime.now().isoformat())).strftime('%d-%m-%Y %H:%M')}</div>
                    <h1>Dashboard de Recursos Habilitados</h1>
                    <div class="subtitle">Gestión de Recursos - Control de Ingresos</div>
                    <div class="admin-note">Datos válidos hasta la fecha de actualización. Verifique cambios recientes con el administrador.</div>
                </div>
            </div>
            <div class="header-right">
                <div class="logo-secco">
                    <img src="https://raw.githubusercontent.com/leomirkin/Dashboard_Habilitados/main/logosecco.svg" alt="SECCO Logo" class="secco-logo">
                </div>
            </div>
        </div>
        
        <div class="content">
            <!-- KPI Section -->
            <div class="kpi-section">
                <div class="kpi-header">
                    <h2><i class="fas fa-chart-pie"></i> KPIs por Cliente</h2>
                    <button class="kpi-reset-btn" onclick="resetearKPIs()">
                        <i class="fas fa-refresh"></i> Resetear Selección
                    </button>
                </div>
                
                <!-- Selector de Cliente -->
                <div class="cliente-selector-container">
                    <div class="selector-header">
                        <div class="selector-icon">
                            <i class="fas fa-building"></i>
                        </div>
                        <h3 class="selector-title">Seleccionar Cliente</h3>
                    </div>
                    <select class="cliente-dropdown" id="clienteKpiSelector">
                        <option value="">-- Seleccionar un cliente --</option>
                    </select>
                </div>
                
                <div class="kpi-cards">
                    <!-- Vista General Card (siempre visible) -->
                    <div class="kpi-card" onclick="seleccionarKPI('general')" data-client="general" id="generalKpiCard">
                        <div class="kpi-card-header">
                            <h3 class="kpi-title">Vista General</h3>
                            <div class="kpi-icon">
                                <i class="fas fa-globe"></i>
                            </div>
                        </div>
                        <div class="kpi-percentage" id="generalPercentage">0%</div>
                        <div class="kpi-details">
                            <span id="generalHabilitados">Habilitados: 0</span>
                            <span class="kpi-total" id="generalTotal">Total: 0</span>
                        </div>
                    </div>
                    
                    <!-- Cliente Seleccionado Card (oculta por defecto) -->
                    <div class="kpi-card cliente-hidden" id="clienteSeleccionadoCard" onclick="seleccionarKPICliente()">
                        <div class="kpi-card-header">
                            <h3 class="kpi-title" id="clienteSeleccionadoTitulo">Cliente</h3>
                            <div class="kpi-icon">
                                <i class="fas fa-building"></i>
                            </div>
                        </div>
                        <div class="kpi-percentage" id="clienteSeleccionadoPercentage">0%</div>
                        <div class="kpi-details">
                            <span id="clienteSeleccionadoHabilitados">Habilitados: 0</span>
                            <span class="kpi-total" id="clienteSeleccionadoTotal">Total: 0</span>
                        </div>
                    </div>
                </div>
                
                <div class="kpi-chart-container" id="kpiChartContainer">
                    <div class="chart-header">
                        <div>
                            <div class="chart-title" id="chartTitle">Vista General</div>
                            <div class="chart-subtitle" id="chartSubtitle">Distribución de estados</div>
                        </div>
                        <select class="edificio-selector" id="edificioKpiSelector" style="display: none;">
                            <option value="">Todos los edificios</option>
                        </select>
                    </div>
                    
                    <div class="chart-content">
                        <div class="chart-canvas">
                            <canvas id="estadosChart"></canvas>
                        </div>
                        <div class="chart-legends" id="chartLegends">
                            <!-- Legends will be generated here -->
                        </div>
                    </div>
                </div>
            </div>
        
                <div class="controls">
            <div class="search-bar">
                <input type="text" id="searchInput" class="search-input" placeholder="🔍 Buscar por nombre, CUIL, DNI, patente...">
                                 <select id="clienteFilter" class="filter-select">
                     <option value="">Todos los clientes</option>
                     {self._generar_opciones_filtro(stats['por_cliente'])}
                 </select>
                <select id="edificioFilter" class="filter-select" disabled>
                   <option value="">Selecciona un cliente primero</option>
                </select>
                <select id="estadoFilter" class="filter-select">
                   <option value="">Todos los estados</option>
                   {self._generar_opciones_filtro(stats['por_estado'])}
                </select>
            </div>
            <div class="filter-info" id="filterInfo" style="display: none;">
                <span class="filter-indicator">📋 Mostrando filas completas (filtros específicos activos)</span>
            </div>
        </div>
        
        <div class="table-container">
            {self._generar_tabla(datos.get('recursos', []))}
        </div>
        
        </div>
        
        
    </div>

    <script>
        // Datos para JavaScript
        const recursos = {json.dumps(datos.get('recursos', []), ensure_ascii=False)};
        const kpisData = {json.dumps(stats.get('kpis_por_cliente', {}), ensure_ascii=False)};
        const kpisGenerales = {json.dumps(stats.get('kpis_generales', {}), ensure_ascii=False)};
        
        // Elementos del DOM
        const searchInput = document.getElementById('searchInput');
        const clienteFilter = document.getElementById('clienteFilter');
        const edificioFilter = document.getElementById('edificioFilter');
        const estadoFilter = document.getElementById('estadoFilter');
        const tbody = document.querySelector('tbody');
        
        // Función para extraer datos de observaciones
        function extraerDatosObservaciones(recurso) {{
            try {{
                if (recurso.observaciones && typeof recurso.observaciones === 'string') {{
                    const obs = JSON.parse(recurso.observaciones);
                    return {{
                        apellido: obs.apellido || '',
                        nombre: obs.nombre || recurso.nombre || '',
                        proveedor: obs.proveedor || recurso.proveedor || '',
                        cuil: obs['cuil/cuit'] || recurso.cuil || recurso.cuit || ''
                    }};
                }}
            }} catch (e) {{
                // Si no se puede parsear, usar datos directos
            }}
            return {{
                apellido: '',
                nombre: recurso.nombre || '',
                proveedor: recurso.proveedor || '',
                cuil: recurso.cuil || recurso.cuit || ''
            }};
        }}

        // Función para filtrar y mostrar recursos
        function filtrarRecursos() {{
            const searchTerm = searchInput.value.toLowerCase();
            const clienteSeleccionado = clienteFilter.value;
            const edificioSeleccionado = edificioFilter.value;
            const estadoSeleccionado = estadoFilter.value.toLowerCase();
            
            const recursosFiltrados = recursos.filter(recurso => {{
                const nombreLower = (recurso.nombre || '').toLowerCase();
                const contratistaRaw = recurso.contratista || '';
                const contratistaLower = contratistaRaw.toLowerCase();
                
                // Usar campo 'clientes' si está disponible (recursos consolidados), sino fallback a 'cliente'
                const clientesDisponibles = recurso.clientes || [recurso.cliente || ''];
                const clienteRaw = clientesDisponibles.join(', ');
                const clienteLower = clienteRaw.toLowerCase();
                
                const edificioRaw = recurso.edificio || '';
                const estadoLower = (recurso.estado || '').toLowerCase();
                const cuil = (recurso.cuil || recurso.cuit || recurso.cuil_cuit || '').toString().toLowerCase();
                const patente = (recurso.dominio || '').toString().toLowerCase();

                // Búsqueda amplia en todos los campos relevantes incluyendo observaciones
                const datosObs = extraerDatosObservaciones(recurso);
                const nombre = (recurso.nombre || '').toLowerCase();
                const apellido = datosObs.apellido.toLowerCase();
                const nombreCompleto = `${{apellido}} ${{datosObs.nombre}}`.toLowerCase();
                const proveedor = (recurso.proveedor || datosObs.proveedor || '').toLowerCase();
                const marca = (recurso.marca || '').toLowerCase();
                const modelo = (recurso.modelo || '').toLowerCase();
                const edificioLower = edificioRaw.toLowerCase();
                
                const matchSearch = !searchTerm ||
                    nombreLower.includes(searchTerm) ||
                    nombre.includes(searchTerm) ||
                    apellido.includes(searchTerm) ||
                    nombreCompleto.includes(searchTerm) ||
                    proveedor.includes(searchTerm) ||
                    cuil.includes(searchTerm) ||
                    patente.includes(searchTerm) ||
                    marca.includes(searchTerm) ||
                    modelo.includes(searchTerm) ||
                    contratistaLower.includes(searchTerm) ||
                    clienteLower.includes(searchTerm) ||
                    edificioLower.includes(searchTerm);
                    
                // Para filtro de cliente, verificar si está en el array de clientes
                const matchCliente = !clienteSeleccionado || 
                    clientesDisponibles.some(cliente => cliente === clienteSeleccionado);
                const matchEdificio = !edificioSeleccionado || edificioRaw === edificioSeleccionado;
                const matchEstado = !estadoSeleccionado || estadoLower.includes(estadoSeleccionado);
                
                return matchSearch && matchCliente && matchEdificio && matchEstado;
            }});
            
            actualizarTabla(recursosFiltrados);
        }}
        
        // Función para actualizar opciones de edificio basado en cliente seleccionado
        function actualizarEdificios() {{
            const clienteSeleccionado = clienteFilter.value;
            const edificioFilter = document.getElementById('edificioFilter');
            
            // Limpiar opciones actuales
            edificioFilter.innerHTML = '';
            
            if (!clienteSeleccionado) {{
                // No hay cliente seleccionado
                edificioFilter.disabled = true;
                edificioFilter.innerHTML = '<option value="">Selecciona un cliente primero</option>';
                actualizarIndicadorFiltros();
                return;
            }}
            
            // Obtener edificios únicos para el cliente seleccionado
            const edificiosCliente = new Set();
            recursos.forEach(recurso => {{
                if (recurso.cliente === clienteSeleccionado && recurso.edificio) {{
                    edificiosCliente.add(recurso.edificio);
                }}
            }});
            
            // Habilitar el select y agregar opciones
            edificioFilter.disabled = false;
            edificioFilter.innerHTML = '<option value="">Todos los edificios de este cliente</option>';
            
            // Agregar opciones ordenadas alfabéticamente
            Array.from(edificiosCliente)
                .sort()
                .forEach(edificio => {{
                    const option = document.createElement('option');
                    option.value = edificio;
                    option.textContent = edificio;
                    edificioFilter.appendChild(option);
                }});
            
            actualizarIndicadorFiltros();
        }}
        
        // Función para mostrar/ocultar indicador de filtros
        function actualizarIndicadorFiltros() {{
            const clienteSeleccionado = clienteFilter.value;
            const edificioSeleccionado = edificioFilter.value;
            const filterInfo = document.getElementById('filterInfo');
            
            if (clienteSeleccionado && edificioSeleccionado) {{
                filterInfo.style.display = 'block';
            }} else {{
                filterInfo.style.display = 'none';
            }}
        }}
        
        // Función para crear vista tipo árbol (mejorada para registros únicos)
        function crearVistaArbol(recursos, tbody, tipo) {{
            const agrupados = {{}};
            
            // Verificar si ambos filtros están activos
            const clienteFiltro = document.getElementById('clienteFilter').value;
            const edificioFiltro = document.getElementById('edificioFilter').value;
            const filtrosCompletos = clienteFiltro && edificioFiltro;
            
            // Agrupar por CUIL/CUIT, Dominio o CUIT (para contratistas)
            recursos.forEach(r => {{
                let clave;
                if (tipo === 'trabajadores') {{
                    clave = r.cuil || r.cuit || 'Sin CUIL';
                }} else if (tipo === 'vehiculos') {{
                    clave = r.dominio || 'Sin Dominio';
                }} else if (tipo === 'contratistas') {{
                    clave = r.cuit || 'Sin CUIT';
                }}
                
                if (!agrupados[clave]) {{
                    agrupados[clave] = {{}};
                }}
                
                // Para recursos consolidados, usar el campo 'clientes', sino fallback a cliente
                let clientesRecurso;
                if (r.clientes && Array.isArray(r.clientes)) {{
                    clientesRecurso = r.clientes;
                }} else {{
                    clientesRecurso = [r.cliente || 'Sin Cliente'];
                }}
                
                // Agregar cada cliente del recurso (respetando filtro de cliente si está activo)
                clientesRecurso.forEach(cliente => {{
                    if (clienteFiltro && cliente !== clienteFiltro) {{
                        return; // ignorar otros clientes cuando hay filtro de cliente
                    }}
                    if (!agrupados[clave][cliente]) {{
                        agrupados[clave][cliente] = [];
                    }}
                    agrupados[clave][cliente].push(r);
                }});
            }});
            
            let rowId = 0;
            Object.keys(agrupados).forEach(clave => {{
                const clientes = agrupados[clave];
                const totalRegistros = Object.values(clientes).flat().length;
                const todosLosRecursos = Object.values(clientes).flat();
                const primerRecurso = todosLosRecursos[0];
                
                                // Si ambos filtros están activos, mostrar filas completas directamente
                if (filtrosCompletos) {{
                    const recurso = primerRecurso;
                    const cliente = Object.keys(clientes)[0];
                    
                    const toDot = (estado) => {{
                        const e = (estado||'').toLowerCase();
                        let colorClass = '';
                        if (e === 'inactivo') {{
                            colorClass = 'gris';
                        }} else if (e.includes('inhabilit') || e.includes('bloque') || e.includes('vencid') || e.includes('inactiv')) {{
                            colorClass = 'rojo';
                        }} else if (e.includes('condicion') || e.includes('pend')) {{
                            colorClass = 'amarillo';
                        }} else if (e.includes('habilit') || e.includes('vigent') || e.includes('activo')) {{
                            colorClass = 'verde';
                        }}
                        return '<span class="estado-dot ' + colorClass + '"></span>';
                    }};
                    
                    // Generar fila según el tipo de tabla
                    let filaHTML = '';
                    if (tipo === 'contratistas') {{
                        filaHTML = `
                            <tr>
                                <td>${{clave}}</td>
                                <td>${{recurso.proveedor || recurso.nombre || ''}}</td>
                                <td>${{cliente}}</td>
                                <td>${{toDot(recurso.estado)}}</td>
                                <td>${{recurso.fecha_vencimiento || recurso.fecha || ''}}</td>
                                <td>${{recurso.edificio === '<>' ? 'Todos los Edificios' : (recurso.edificio || '')}}</td>
                            </tr>
                        `;
                    }} else if (tipo === 'trabajadores') {{
                        const datosObs = extraerDatosObservaciones(recurso);
                        const nombreCompleto = datosObs.apellido ? `${{datosObs.apellido}}, ${{datosObs.nombre}}` : (datosObs.nombre || recurso.nombre || '');
                        filaHTML = `
                            <tr>
                                <td>${{clave}}</td>
                                <td>${{nombreCompleto}}</td>
                                <td>${{datosObs.proveedor}}</td>
                                <td>${{cliente}}</td>
                                <td>${{recurso.edificio === '<>' ? 'Todos los Edificios' : (recurso.edificio || '')}}</td>
                                <td>${{toDot(recurso.estado)}}</td>
                                <td>${{recurso.fecha_vencimiento || recurso.fecha || ''}}</td>
                            </tr>
                        `;
                    }} else if (tipo === 'vehiculos') {{
                        filaHTML = `
                            <tr>
                                <td>${{clave}}</td>
                                <td>${{recurso.marca || ''}}</td>
                                <td>${{recurso.modelo || ''}}</td>
                                <td>${{recurso.proveedor || ''}}</td>
                                <td>${{cliente}}</td>
                                <td>${{recurso.edificio === '<>' ? 'Todos los Edificios' : (recurso.edificio || '')}}</td>
                                <td>${{recurso.tipo || ''}}</td>
                                <td>${{toDot(recurso.estado)}}</td>
                                <td>${{recurso.fecha_vencimiento || recurso.fecha || ''}}</td>
                            </tr>
                        `;
                    }}
                    
                    tbody.insertAdjacentHTML('beforeend', filaHTML);
                }} else if (clienteFiltro && totalRegistros === 1) {{
                    // Filtro por cliente activo y solo 1 registro → mostrar fila directa
                    const recurso = primerRecurso;
                    const cliente = Object.keys(clientes)[0];
                    
                    const toDot = (estado) => {{
                        const e = (estado||'').toLowerCase();
                        let colorClass = '';
                        if (e === 'inactivo') {{
                            colorClass = 'gris';
                        }} else if (e.includes('inhabilit') || e.includes('bloque') || e.includes('vencid') || e.includes('inactiv')) {{
                            colorClass = 'rojo';
                        }} else if (e.includes('condicion') || e.includes('pend')) {{
                            colorClass = 'amarillo';
                        }} else if (e.includes('habilit') || e.includes('vigent') || e.includes('activo')) {{
                            colorClass = 'verde';
                        }}
                        return '<span class="estado-dot ' + colorClass + '"></span>';
                    }};
                    
                    let filaHTML = '';
                    if (tipo === 'contratistas') {{
                        filaHTML = `
                            <tr>
                                <td>${{clave}}</td>
                                <td>${{recurso.proveedor || recurso.nombre || ''}}</td>
                                <td>${{cliente}}</td>
                                <td>${{toDot(recurso.estado)}} </td>
                                <td>${{recurso.fecha_vencimiento || recurso.fecha || ''}}</td>
                                <td>${{recurso.edificio === '<>' ? 'Todos los Edificios' : (recurso.edificio || '')}}</td>
                            </tr>
                        `;
                    }} else if (tipo === 'trabajadores') {{
                        const datosObs = extraerDatosObservaciones(recurso);
                        const nombreCompleto = datosObs.apellido ? `${{datosObs.apellido}}, ${{datosObs.nombre}}` : (datosObs.nombre || recurso.nombre || '');
                        filaHTML = `
                            <tr>
                                <td>${{clave}}</td>
                                <td>${{nombreCompleto}}</td>
                                <td>${{datosObs.proveedor}}</td>
                                <td>${{cliente}}</td>
                                <td>${{recurso.edificio === '<>' ? 'Todos los Edificios' : (recurso.edificio || '')}}</td>
                                <td>${{toDot(recurso.estado)}}</td>
                                <td>${{recurso.fecha_vencimiento || recurso.fecha || ''}}</td>
                            </tr>
                        `;
                    }} else if (tipo === 'vehiculos') {{
                        filaHTML = `
                            <tr>
                                <td>${{clave}}</td>
                                <td>${{recurso.marca || ''}}</td>
                                <td>${{recurso.modelo || ''}}</td>
                                <td>${{recurso.proveedor || ''}}</td>
                                <td>${{cliente}}</td>
                                <td>${{recurso.edificio === '<>' ? 'Todos los Edificios' : (recurso.edificio || '')}}</td>
                                <td>${{recurso.tipo || ''}}</td>
                                <td>${{toDot(recurso.estado)}}</td>
                                <td>${{recurso.fecha_vencimiento || recurso.fecha || ''}}</td>
                            </tr>
                        `;
                    }}
                    
                    tbody.insertAdjacentHTML('beforeend', filaHTML);
                }} else if (Object.keys(clientes).length === 1 && (Object.keys(clientes)[0] === 'Sin Contratista' || Object.keys(clientes)[0].includes('CERTRONIC'))) {{
                    // Caso especial: Un solo contratista "Sin Contratista" o cliente CERTRONIC único → Mostrar estado directo
                    const cliente = Object.keys(clientes)[0];
                    const recurso = primerRecurso;
                    
                    const toDot = (estado) => {{
                        const e = (estado||'').toLowerCase();
                        let colorClass = '';
                        if (e === 'inactivo') {{
                            colorClass = 'gris';
                        }} else if (e.includes('inhabilit') || e.includes('bloque') || e.includes('vencid') || e.includes('inactiv')) {{
                            colorClass = 'rojo';
                        }} else if (e.includes('condicion') || e.includes('pend')) {{
                            colorClass = 'amarillo';
                        }} else if (e.includes('habilit') || e.includes('vigent') || e.includes('activo')) {{
                            colorClass = 'verde';
                        }}
                        return '<span class="estado-dot ' + colorClass + '"></span>';
                    }};
                    
                    // Generar fila directa según el tipo de tabla (sin dropdown)
                    let filaHTML = '';
                    if (tipo === 'contratistas') {{
                        filaHTML = `
                            <tr>
                                <td>${{clave}}</td>
                                <td>${{recurso.proveedor || recurso.nombre || ''}}</td>
                                <td>${{recurso.cliente || ''}}</td>
                                <td>${{toDot(recurso.estado)}}</td>
                                <td>${{recurso.fecha_vencimiento || recurso.fecha || ''}}</td>
                                <td>${{recurso.edificio === '<>' ? 'Todos los Edificios' : (recurso.edificio || '')}}</td>
                            </tr>
                        `;
                    }} else if (tipo === 'trabajadores') {{
                        const datosObs = extraerDatosObservaciones(recurso);
                        const nombreCompleto = datosObs.apellido ? `${{datosObs.apellido}}, ${{datosObs.nombre}}` : (datosObs.nombre || recurso.nombre || '');
                        filaHTML = `
                            <tr>
                                <td>${{clave}}</td>
                                <td>${{nombreCompleto}}</td>
                                <td>${{datosObs.proveedor}}</td>
                                <td>${{recurso.cliente || ''}}</td>
                                <td>${{toDot(recurso.estado)}}</td>
                                <td>${{recurso.fecha_vencimiento || recurso.fecha || ''}}</td>
                                <td>${{recurso.edificio === '<>' ? 'Todos los Edificios' : (recurso.edificio || '')}}</td>
                            </tr>
                        `;
                    }} else if (tipo === 'vehiculos') {{
                        filaHTML = `
                            <tr>
                                <td>${{clave}}</td>
                                <td>${{recurso.marca || ''}}</td>
                                <td>${{recurso.modelo || ''}}</td>
                                <td>${{recurso.proveedor || ''}}</td>
                                <td>${{recurso.cliente || ''}}</td>
                                <td>${{recurso.edificio === '<>' ? 'Todos los Edificios' : (recurso.edificio || '')}}</td>
                                <td>${{recurso.tipo || ''}}</td>
                                <td>${{toDot(recurso.estado)}}</td>
                                <td>${{recurso.fecha_vencimiento || recurso.fecha || ''}}</td>
                            </tr>
                        `;
                    }}
                    
                    tbody.insertAdjacentHTML('beforeend', filaHTML);
                }} else {{
                    // Si hay múltiples registros/clientes, usar estructura colapsable
                    const mainRowId = `main-${{tipo}}-${{rowId}}`;
                    // Generar fila colapsada principal según el tipo
                    let filaColapsadaHTML = '';
                    if (tipo === 'contratistas') {{
                        filaColapsadaHTML = `
                            <tr class="tree-row" data-id="${{mainRowId}}" onclick="toggleClients('${{mainRowId}}')">
                                <td><span class="tree-icon">▶</span>${{clave}}</td>
                                <td>${{primerRecurso.proveedor || primerRecurso.nombre || ''}}</td>
                                <td colspan="4" class="registros-info" title="Clic para expandir ${{totalRegistros}} registros">
                                    <span class="registros-count">${{totalRegistros}}</span>
                                    <span class="registros-label">registros</span>
                                    <i class="fas fa-chevron-down expand-icon"></i>
                                </td>
                            </tr>
                        `;
                    }} else if (tipo === 'trabajadores') {{
                        const datosPrimerRecurso = extraerDatosObservaciones(primerRecurso);
                        const nombreCompletoPrimero = datosPrimerRecurso.apellido ? `${{datosPrimerRecurso.apellido}}, ${{datosPrimerRecurso.nombre}}` : (datosPrimerRecurso.nombre || primerRecurso.nombre || '');
                        filaColapsadaHTML = `
                            <tr class="tree-row" data-id="${{mainRowId}}" onclick="toggleClients('${{mainRowId}}')">
                                <td><span class="tree-icon">▶</span>${{clave}}</td>
                                <td>${{nombreCompletoPrimero}}</td>
                                <td>${{datosPrimerRecurso.proveedor}}</td>
                                <td colspan="4" class="registros-info" title="Clic para expandir ${{totalRegistros}} registros">
                                    <span class="registros-count">${{totalRegistros}}</span>
                                    <span class="registros-label">registros</span>
                                    <i class="fas fa-chevron-down expand-icon"></i>
                                </td>
                            </tr>
                        `;
                    }} else if (tipo === 'vehiculos') {{
                        filaColapsadaHTML = `
                            <tr class="tree-row" data-id="${{mainRowId}}" onclick="toggleClients('${{mainRowId}}')">
                                <td><span class="tree-icon">▶</span>${{clave}}</td>
                                <td>${{primerRecurso.marca || ''}}</td>
                                <td>${{primerRecurso.modelo || ''}}</td>
                                <td colspan="6" class="registros-info" title="Clic para expandir ${{totalRegistros}} registros">
                                    <span class="registros-count">${{totalRegistros}}</span>
                                    <span class="registros-label">registros</span>
                                    <i class="fas fa-chevron-down expand-icon"></i>
                                </td>
                            </tr>
                        `;
                    }}
                    
                    tbody.insertAdjacentHTML('beforeend', filaColapsadaHTML);
                    
                    // Filas de clientes (ocultas inicialmente)
                    let clientIndex = 0;
                    Object.keys(clientes).forEach(cliente => {{
                        const clienteRowId = `client-${{tipo}}-${{rowId}}-${{clientIndex}}`;
                        const edificios = clientes[cliente];
                        clientIndex++;
                        
                        // Generar fila de cliente expandida según el tipo
                        let filaClienteHTML = '';
                        if (tipo === 'contratistas') {{
                            filaClienteHTML = `
                                <tr class="tree-client tree-hidden client-${{mainRowId}}" data-id="${{clienteRowId}}" onclick="toggleBuildings('${{clienteRowId}}')">
                                    <td style="padding-left: 30px;"><span class="tree-icon">▶</span>${{clave}}</td>
                                    <td>${{edificios[0].proveedor || edificios[0].nombre || ''}}</td>
                                    <td style="font-weight: 600;">${{cliente}}</td>
                                    <td colspan="3" class="edificios-info" title="Clic para expandir ${{edificios.length}} edificio(s)">
                                        <span class="edificios-count">${{edificios.length}}</span>
                                        <span class="edificios-label">edificio(s)</span>
                                        <i class="fas fa-chevron-down expand-icon"></i>
                                    </td>
                                </tr>
                            `;
                        }} else if (tipo === 'trabajadores') {{
                            const datosPrimerEdificio = extraerDatosObservaciones(edificios[0]);
                            const nombreCompletoPrimerEdificio = datosPrimerEdificio.apellido ? `${{datosPrimerEdificio.apellido}}, ${{datosPrimerEdificio.nombre}}` : (datosPrimerEdificio.nombre || edificios[0].nombre || '');
                            filaClienteHTML = `
                                <tr class="tree-client tree-hidden client-${{mainRowId}}" data-id="${{clienteRowId}}" onclick="toggleBuildings('${{clienteRowId}}')">
                                    <td style="padding-left: 30px;"><span class="tree-icon">▶</span>${{clave}}</td>
                                    <td>${{nombreCompletoPrimerEdificio}}</td>
                                    <td>${{datosPrimerEdificio.proveedor}}</td>
                                    <td>${{edificios[0].contratista || ''}}</td>
                                    <td style="font-weight: 600;">${{cliente}}</td>
                                    <td colspan="3" class="edificios-info" title="Clic para expandir ${{edificios.length}} edificio(s)">
                                        <span class="edificios-count">${{edificios.length}}</span>
                                        <span class="edificios-label">edificio(s)</span>
                                        <i class="fas fa-chevron-down expand-icon"></i>
                                    </td>
                                </tr>
                            `;
                        }} else if (tipo === 'vehiculos') {{
                            filaClienteHTML = `
                                <tr class="tree-client tree-hidden client-${{mainRowId}}" data-id="${{clienteRowId}}" onclick="toggleBuildings('${{clienteRowId}}')">
                                    <td style="padding-left: 30px;"><span class="tree-icon">▶</span>${{clave}}</td>
                                    <td>${{edificios[0].marca || ''}}</td>
                                    <td>${{edificios[0].modelo || ''}}</td>
                                    <td>${{edificios[0].proveedor || ''}}</td>
                                    <td style="font-weight: 600;">${{cliente}}</td>
                                    <td colspan="4" class="edificios-info" title="Clic para expandir ${{edificios.length}} edificio(s)">
                                        <span class="edificios-count">${{edificios.length}}</span>
                                        <span class="edificios-label">edificio(s)</span>
                                        <i class="fas fa-chevron-down expand-icon"></i>
                                    </td>
                                </tr>
                            `;
                        }}
                        
                        tbody.insertAdjacentHTML('beforeend', filaClienteHTML);
                        
                        // Filas de edificios (ocultas inicialmente)
                        edificios.forEach(recurso => {{
                            const toDot = (estado) => {{
                                const e = (estado||'').toLowerCase();
                                let colorClass = '';
                                if (e === 'inactivo') {{
                                    colorClass = 'gris';
                                }} else if (e.includes('inhabilit') || e.includes('bloque') || e.includes('vencid') || e.includes('inactiv')) {{
                                    colorClass = 'rojo';
                                }} else if (e.includes('condicion') || e.includes('pend')) {{
                                    colorClass = 'amarillo';
                                }} else if (e.includes('habilit') || e.includes('vigent') || e.includes('activo')) {{
                                    colorClass = 'verde';
                                }}
                                return '<span class="estado-dot ' + colorClass + '"></span>';
                            }};
                            
                            // Generar fila de edificio final según el tipo
                            let filaEdificioHTML = '';
                            if (tipo === 'contratistas') {{
                                filaEdificioHTML = `
                                    <tr class="tree-building tree-hidden building-${{clienteRowId}}">
                                        <td style="padding-left: 60px;">${{clave}}</td>
                                        <td>${{recurso.proveedor || recurso.nombre || ''}}</td>
                                        <td>${{cliente}}</td>
                                        <td>${{toDot(recurso.estado)}}</td>
                                        <td>${{recurso.fecha_vencimiento || recurso.fecha || ''}}</td>
                                        <td>${{recurso.edificio === '<>' ? 'Todos los Edificios' : (recurso.edificio || '')}}</td>
                                    </tr>
                                `;
                            }} else if (tipo === 'trabajadores') {{
                                const datosRecurso = extraerDatosObservaciones(recurso);
                                const nombreCompletoRecurso = datosRecurso.apellido ? `${{datosRecurso.apellido}}, ${{datosRecurso.nombre}}` : (datosRecurso.nombre || recurso.nombre || '');
                                filaEdificioHTML = `
                                    <tr class="tree-building tree-hidden building-${{clienteRowId}}">
                                        <td style="padding-left: 60px;">${{clave}}</td>
                                        <td>${{nombreCompletoRecurso}}</td>
                                        <td>${{datosRecurso.proveedor}}</td>
                                        <td>${{cliente}}</td>
                                        <td>${{recurso.edificio === '<>' ? 'Todos los Edificios' : (recurso.edificio || '')}}</td>
                                        <td>${{toDot(recurso.estado)}}</td>
                                        <td>${{recurso.fecha_vencimiento || recurso.fecha || ''}}</td>
                                    </tr>
                                `;
                            }} else if (tipo === 'vehiculos') {{
                                filaEdificioHTML = `
                                    <tr class="tree-building tree-hidden building-${{clienteRowId}}">
                                        <td style="padding-left: 60px;">${{clave}}</td>
                                        <td>${{recurso.marca || ''}}</td>
                                        <td>${{recurso.modelo || ''}}</td>
                                        <td>${{recurso.proveedor || ''}}</td>
                                        <td>${{cliente}}</td>
                                        <td>${{recurso.edificio === '<>' ? 'Todos los Edificios' : (recurso.edificio || '')}}</td>
                                        <td>${{recurso.tipo || ''}}</td>
                                        <td>${{toDot(recurso.estado)}}</td>
                                        <td>${{recurso.fecha_vencimiento || recurso.fecha || ''}}</td>
                                    </tr>
                                `;
                            }}
                            
                            tbody.insertAdjacentHTML('beforeend', filaEdificioHTML);
                        }});
                    }});
                }}
                
                rowId++;
            }});
        }}
        
        // Función para actualizar colores alternados de filas visibles
        function actualizarColoresFilas() {{
            const tablas = ['#tablaProveedores', '#tablaPersonas', '#tablaVehiculos'];
            
            tablas.forEach(tablaId => {{
                const tbody = document.querySelector(`${{tablaId}} tbody`);
                if (!tbody) return;
                
                const filasVisibles = Array.from(tbody.querySelectorAll('tr')).filter(row => 
                    !row.classList.contains('tree-hidden')
                );
                
                filasVisibles.forEach((row, index) => {{
                    row.classList.remove('row-even');
                    if (index % 2 === 1) {{
                        row.classList.add('row-even');
                    }}
                }});
            }});
        }}

        // Función para alternar clientes
        function toggleClients(mainRowId) {{
            event.stopPropagation();
            const icon = document.querySelector(`[data-id="${{mainRowId}}"] .tree-icon`);
            const expandIcon = document.querySelector(`[data-id="${{mainRowId}}"] .expand-icon`);
            const clients = document.querySelectorAll(`.client-${{mainRowId}}`);
            
            if (icon.textContent === '▶') {{
                icon.textContent = '▼';
                icon.classList.add('expanded');
                if (expandIcon) expandIcon.style.transform = 'rotate(180deg)';
                clients.forEach(row => row.classList.remove('tree-hidden'));
            }} else {{
                icon.textContent = '▶';
                icon.classList.remove('expanded');
                if (expandIcon) expandIcon.style.transform = 'rotate(0deg)';
                clients.forEach(row => {{
                    row.classList.add('tree-hidden');
                    // También ocultar edificios si están expandidos
                    const clientId = row.getAttribute('data-id');
                    if (clientId) {{
                        const buildings = document.querySelectorAll(`.building-${{clientId}}`);
                        buildings.forEach(b => b.classList.add('tree-hidden'));
                        const clientIcon = row.querySelector('.tree-icon');
                        const clientExpandIcon = row.querySelector('.expand-icon');
                        if (clientIcon) {{
                            clientIcon.textContent = '▶';
                            clientIcon.classList.remove('expanded');
                        }}
                        if (clientExpandIcon) clientExpandIcon.style.transform = 'rotate(0deg)';
                    }}
                }});
            }}
            
            // Actualizar colores después del toggle
            setTimeout(actualizarColoresFilas, 10);
        }}
        
        // Función para alternar edificios
        function toggleBuildings(clientRowId) {{
            event.stopPropagation();
            const icon = document.querySelector(`[data-id="${{clientRowId}}"] .tree-icon`);
            const expandIcon = document.querySelector(`[data-id="${{clientRowId}}"] .expand-icon`);
            const buildings = document.querySelectorAll(`.building-${{clientRowId}}`);
            
            if (icon.textContent === '▶') {{
                icon.textContent = '▼';
                icon.classList.add('expanded');
                if (expandIcon) expandIcon.style.transform = 'rotate(180deg)';
                buildings.forEach(row => row.classList.remove('tree-hidden'));
            }} else {{
                icon.textContent = '▶';
                icon.classList.remove('expanded');
                if (expandIcon) expandIcon.style.transform = 'rotate(0deg)';
                buildings.forEach(row => row.classList.add('tree-hidden'));
            }}
            
            // Actualizar colores después del toggle
            setTimeout(actualizarColoresFilas, 10);
        }}

        // Función para actualizar la tabla
        function actualizarTabla(recursosAMostrar) {{
            // Rellenar 3 tablas por categoría
            const provTbody = document.querySelector('#tablaProveedores tbody');
            const persTbody = document.querySelector('#tablaPersonas tbody');
            const vehTbody = document.querySelector('#tablaVehiculos tbody');
            provTbody.innerHTML = persTbody.innerHTML = vehTbody.innerHTML = '';

            if (recursosAMostrar.length === 0) {{
                provTbody.innerHTML = '<tr><td colspan="6" class="no-data">Sin datos</td></tr>';
                persTbody.innerHTML = '<tr><td colspan="8" class="no-data">Sin datos</td></tr>';
                vehTbody.innerHTML = '<tr><td colspan="9" class="no-data">Sin datos</td></tr>';
                return;
            }}

            // Separar recursos por categoría
            const contratistas = recursosAMostrar.filter(r => {{
                const cat = (r.categoria||'').toLowerCase();
                return cat.includes('grupo') || cat.includes('proveedor') || cat.includes('contratista');
            }});
            
            const trabajadores = recursosAMostrar.filter(r => {{
                const cat = (r.categoria||'').toLowerCase();
                return cat.includes('persona') || cat.includes('trabajador');
            }});
            
            const vehiculos = recursosAMostrar.filter(r => {{
                const cat = (r.categoria||'').toLowerCase();
                // Solo aceptar categorías explícitas de vehículos o maquinarias
                const esVehiculo = cat.includes('veh');
                const esMaquinaria = cat.includes('maquin');
                if (!(esVehiculo || esMaquinaria)) return false;
                const dominioRaw = (r.dominio || '').toUpperCase().trim();
                const dominio = dominioRaw.replace(/\s|-/g, '');
                const marcaVal = (r.marca || '').trim();
                const modeloVal = (r.modelo || '').trim();
                const dominioOk = (/^[A-Z]{3}\d{3}$/.test(dominio) || /^[A-Z]{2}\d{3}[A-Z]{2}$/.test(dominio) || (/[0-9]/.test(dominio) && dominio.length >= 5 && /^[A-Z0-9]+$/.test(dominio)));
                const pareceRazonSocial = dominioRaw.split(' ').length >= 2 && !dominioOk;
                // Regla clave: para vehiculos se exige patente válida; para maquinarias bastan marca/modelo
                const tieneCamposVehiculo = esVehiculo ? (dominioOk && !pareceRazonSocial) : (marcaVal.length > 0 || modeloVal.length > 0);
                const parecePersona = !!(r.cuil && !tieneCamposVehiculo);
                return tieneCamposVehiculo && !parecePersona;
            }});

            // Crear vista árbol para todas las categorías
            if (contratistas.length > 0) {{
                crearVistaArbol(contratistas, provTbody, 'contratistas');
            }}
            
            if (trabajadores.length > 0) {{
                crearVistaArbol(trabajadores, persTbody, 'trabajadores');
            }}
            
            if (vehiculos.length > 0) {{
                crearVistaArbol(vehiculos, vehTbody, 'vehiculos');
            }}
            
            // Actualizar colores de filas después de crear las tablas
            setTimeout(actualizarColoresFilas, 50);
        }}
        
        // Función para obtener la clase CSS del estado
        function getEstadoClass(estado) {{
            if (!estado) return '';
            const estadoLower = estado.toLowerCase();
            if (estadoLower.includes('habilitado') || estadoLower.includes('activo') || estadoLower.includes('vigente')) {{
                return 'habilitado';
            }} else if (estadoLower.includes('deshabilitado') || estadoLower.includes('inactivo') || estadoLower.includes('vencido')) {{
                return 'deshabilitado';
            }} else {{
                return 'pendiente';
            }}
        }}
        
        // Event listeners
        searchInput.addEventListener('input', filtrarRecursos);
        clienteFilter.addEventListener('change', function() {{
            actualizarEdificios();
            filtrarRecursos();
        }});
        edificioFilter.addEventListener('change', function() {{
            actualizarIndicadorFiltros();
            filtrarRecursos();
        }});
        estadoFilter.addEventListener('change', filtrarRecursos);
        
        // Variables globales para KPIs
        let currentChart = null;
        let selectedClient = null;
        let selectedBuilding = null;
        
        // Funciones para KPIs
        function generarKPICards() {{
            // Actualizar datos de la tarjeta general
            const totalGeneral = Object.values(kpisGenerales).reduce((sum, val) => sum + val, 0);
            const porcentajeGeneral = totalGeneral > 0 ? Math.round((kpisGenerales.habilitados / totalGeneral) * 100) : 0;
            
            document.getElementById('generalPercentage').textContent = `${{porcentajeGeneral}}%`;
            document.getElementById('generalHabilitados').textContent = `Habilitados: ${{kpisGenerales.habilitados}}`;
            document.getElementById('generalTotal').textContent = `Total: ${{totalGeneral}}`;
            
            // Poblar selector de clientes ordenado por porcentaje (menor a mayor)
            const clientesOrdenados = Object.keys(kpisData)
                .map(cliente => {{
                    const clienteData = kpisData[cliente];
                    const porcentaje = clienteData.total > 0 ? Math.round((clienteData.habilitados / clienteData.total) * 100) : 0;
                    return {{ nombre: cliente, porcentaje, data: clienteData }};
                }})
                .sort((a, b) => a.porcentaje - b.porcentaje);
            
            const selector = document.getElementById('clienteKpiSelector');
            selector.innerHTML = '<option value="">-- Seleccionar un cliente --</option>';
            
            clientesOrdenados.forEach(cliente => {{
                const option = document.createElement('option');
                option.value = cliente.nombre;
                option.textContent = `${{cliente.nombre}} (${{cliente.porcentaje}}% - ${{cliente.data.habilitados}}/${{cliente.data.total}})`;
                selector.appendChild(option);
            }});
        }}
        
        function seleccionarKPI(cliente) {{
            // Actualizar estado de selección
            document.querySelectorAll('.kpi-card').forEach(card => {{
                card.classList.remove('selected');
            }});
            
            document.getElementById('generalKpiCard').classList.add('selected');
            
            // Limpiar selector de cliente
            document.getElementById('clienteKpiSelector').value = '';
            ocultarClienteSeleccionado();
            
            // Mostrar contenedor del gráfico
            const chartContainer = document.getElementById('kpiChartContainer');
            chartContainer.classList.add('active');
            
            selectedClient = null;
            mostrarGraficoGeneral();
        }}
        
        function seleccionarKPICliente() {{
            if (selectedClient) {{
                // Actualizar estado de selección
                document.querySelectorAll('.kpi-card').forEach(card => {{
                    card.classList.remove('selected');
                }});
                
                document.getElementById('clienteSeleccionadoCard').classList.add('selected');
                
                // Mostrar contenedor del gráfico
                const chartContainer = document.getElementById('kpiChartContainer');
                chartContainer.classList.add('active');
                
                mostrarGraficoCliente(selectedClient);
            }}
        }}
        
        function mostrarClienteSeleccionado(cliente) {{
            const clienteData = kpisData[cliente];
            const porcentaje = clienteData.total > 0 ? Math.round((clienteData.habilitados / clienteData.total) * 100) : 0;
            
            document.getElementById('clienteSeleccionadoTitulo').textContent = cliente;
            document.getElementById('clienteSeleccionadoPercentage').textContent = `${{porcentaje}}%`;
            document.getElementById('clienteSeleccionadoHabilitados').textContent = `Habilitados: ${{clienteData.habilitados}}`;
            document.getElementById('clienteSeleccionadoTotal').textContent = `Total: ${{clienteData.total}}`;
            
            const card = document.getElementById('clienteSeleccionadoCard');
            card.classList.remove('cliente-hidden');
            card.classList.add('cliente-selected');
        }}
        
        function ocultarClienteSeleccionado() {{
            const card = document.getElementById('clienteSeleccionadoCard');
            card.classList.remove('cliente-selected');
            card.classList.add('cliente-hidden');
        }}
        
        function mostrarGraficoGeneral() {{
            const chartTitle = document.getElementById('chartTitle');
            const chartSubtitle = document.getElementById('chartSubtitle');
            const edificioSelector = document.getElementById('edificioKpiSelector');
            
            chartTitle.textContent = 'Vista General';
            chartSubtitle.textContent = 'Distribución de estados - Todos los clientes';
            edificioSelector.style.display = 'none';
            
            const data = {{
                habilitados: kpisGenerales.habilitados,
                bloqueados: kpisGenerales.bloqueados,
                condicionados: kpisGenerales.condicionados
            }};
            
            crearGraficoPie(data);
            actualizarLeyenda(data);
        }}
        
        function mostrarGraficoCliente(cliente) {{
            const clienteData = kpisData[cliente];
            const chartTitle = document.getElementById('chartTitle');
            const chartSubtitle = document.getElementById('chartSubtitle');
            const edificioSelector = document.getElementById('edificioKpiSelector');
            
            chartTitle.textContent = cliente;
            chartSubtitle.textContent = 'Distribución de estados - Todos los edificios';
            
            // Poblar selector de edificios
            edificioSelector.innerHTML = '<option value="">Todos los edificios</option>';
            Object.keys(clienteData.edificios).forEach(edificio => {{
                const option = document.createElement('option');
                option.value = edificio;
                option.textContent = edificio;
                edificioSelector.appendChild(option);
            }});
            
            edificioSelector.style.display = 'block';
            edificioSelector.value = '';
            selectedBuilding = null;
            
            const data = {{
                habilitados: clienteData.habilitados,
                bloqueados: clienteData.bloqueados,
                condicionados: clienteData.condicionados
            }};
            
            crearGraficoPie(data);
            actualizarLeyenda(data);
        }}
        
        function mostrarGraficoEdificio(cliente, edificio) {{
            const edificioData = kpisData[cliente].edificios[edificio];
            const chartSubtitle = document.getElementById('chartSubtitle');
            
            chartSubtitle.textContent = `Distribución de estados - ${{edificio}}`;
            selectedBuilding = edificio;
            
            const data = {{
                habilitados: edificioData.habilitados,
                bloqueados: edificioData.bloqueados,
                condicionados: edificioData.condicionados
            }};
            
            crearGraficoPie(data);
            actualizarLeyenda(data);
        }}
        
        function crearGraficoPie(data) {{
            const ctx = document.getElementById('estadosChart').getContext('2d');
            
            if (currentChart) {{
                currentChart.destroy();
            }}
            
            const total = Object.values(data).reduce((sum, val) => sum + val, 0);
            
            if (total === 0) {{
                currentChart = new Chart(ctx, {{
                    type: 'doughnut',
                    data: {{
                        labels: ['Sin datos'],
                        datasets: [{{
                            data: [1],
                            backgroundColor: ['#ecf0f1'],
                            borderColor: ['#bdc3c7'],
                            borderWidth: 1
                        }}]
                    }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {{
                            legend: {{
                                display: false
                            }},
                            tooltip: {{
                                enabled: false
                            }}
                        }}
                    }}
                }});
                return;
            }}
            
            currentChart = new Chart(ctx, {{
                type: 'doughnut',
                data: {{
                    labels: ['Habilitados', 'Bloqueados', 'Condicionales'],
                    datasets: [{{
                        data: [data.habilitados, data.bloqueados, data.condicionados],
                        backgroundColor: ['#27ae60', '#e74c3c', '#f39c12'],
                        borderColor: ['#ffffff', '#ffffff', '#ffffff'],
                        borderWidth: 3,
                        hoverBorderWidth: 5
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{
                            display: false
                        }},
                        tooltip: {{
                            backgroundColor: 'rgba(0, 0, 0, 0.8)',
                            titleColor: '#ffffff',
                            bodyColor: '#ffffff',
                            borderColor: '#ffffff',
                            borderWidth: 1,
                            callbacks: {{
                                label: function(context) {{
                                    const percentage = total > 0 ? Math.round((context.parsed / total) * 100) : 0;
                                    return `${{context.label}}: ${{context.parsed}} (${{percentage}}%)`;
                                }}
                            }}
                        }}
                    }},
                    animation: {{
                        animateRotate: true,
                        duration: 1000
                    }}
                }}
            }});
        }}
        
        function actualizarLeyenda(data) {{
            const container = document.getElementById('chartLegends');
            const total = Object.values(data).reduce((sum, val) => sum + val, 0);
            
            const estados = [
                {{ key: 'habilitados', label: 'Habilitados', value: data.habilitados }},
                {{ key: 'bloqueados', label: 'Bloqueados', value: data.bloqueados }},
                {{ key: 'condicionados', label: 'Condicionales', value: data.condicionados }}
            ];
            
            container.innerHTML = estados.map(estado => {{
                const percentage = total > 0 ? Math.round((estado.value / total) * 100) : 0;
                return `
                    <div class="legend-item ${{estado.key}}">
                        <div class="legend-color ${{estado.key}}"></div>
                        <div class="legend-text">
                            <span class="legend-label">${{estado.label}}</span>
                            <div class="legend-value">
                                <span class="legend-count">${{estado.value}}</span>
                                <span class="legend-percentage">${{percentage}}%</span>
                            </div>
                        </div>
                    </div>
                `;
            }}).join('');
        }}
        
        function resetearKPIs() {{
            document.querySelectorAll('.kpi-card').forEach(card => {{
                card.classList.remove('selected');
            }});
            
            // Limpiar selector
            document.getElementById('clienteKpiSelector').value = '';
            ocultarClienteSeleccionado();
            
            const chartContainer = document.getElementById('kpiChartContainer');
            chartContainer.classList.remove('active');
            
            if (currentChart) {{
                currentChart.destroy();
                currentChart = null;
            }}
            
            selectedClient = null;
            selectedBuilding = null;
        }}
        
        // Event listener para selector de clientes
        document.getElementById('clienteKpiSelector').addEventListener('change', function() {{
            const cliente = this.value;
            if (cliente) {{
                selectedClient = cliente;
                mostrarClienteSeleccionado(cliente);
                
                // Auto-seleccionar la tarjeta del cliente
                document.querySelectorAll('.kpi-card').forEach(card => {{
                    card.classList.remove('selected');
                }});
                document.getElementById('clienteSeleccionadoCard').classList.add('selected');
                
                // Mostrar gráfico
                const chartContainer = document.getElementById('kpiChartContainer');
                chartContainer.classList.add('active');
                mostrarGraficoCliente(cliente);
            }} else {{
                selectedClient = null;
                ocultarClienteSeleccionado();
                resetearKPIs();
            }}
        }});
        
        // Event listener para selector de edificios
        document.getElementById('edificioKpiSelector').addEventListener('change', function() {{
            if (selectedClient && this.value) {{
                mostrarGraficoEdificio(selectedClient, this.value);
            }} else if (selectedClient) {{
                mostrarGraficoCliente(selectedClient);
            }}
        }});
        
        // Cargar datos iniciales
        document.addEventListener('DOMContentLoaded', function() {{
            actualizarTabla(recursos);
            generarKPICards();
        }});
    </script>
    
    <!-- Footer -->
    <footer class="footer">
        <div class="footer-content">
            <div class="footer-text">
                <span class="gcg-brand">Reporte Generado por GCG CONTROL</span>
                <span class="copyright">© 2025 GCG CONTROL. Todos los derechos reservados.</span>
            </div>
        </div>
    </footer>
</body>
</html>
"""
        
        # Guardar archivo HTML
        output_file = self.output_dir / "dashboard.html"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
            
        logger.info(f"Dashboard generado: {output_file}")
        return str(output_file)
    
    def _formatear_edificio(self, edificio: str) -> str:
        """Formatea el valor del edificio para mostrar 'Todos los Edificios' en lugar de '<>'"""
        if edificio == '<>':
            return 'Todos los Edificios'
        return edificio or ''
    
    def _generar_opciones_filtro(self, diccionario: Dict) -> str:
        """Genera opciones HTML para los filtros desplegables"""
        opciones = []
        for clave, cantidad in sorted(diccionario.items()):
            opciones.append(f'<option value="{clave}">{clave} ({cantidad})</option>')
        return '\n'.join(opciones)
    
    def _generar_tabla(self, recursos: List[Dict]) -> str:
        """Genera la estructura HTML de la tabla"""
        if not recursos:
            return '''
            <table>
                <thead>
                    <tr>
                        <th>Nombre</th>
                        <th>Contratista</th>
                        <th>Cliente</th>
                        <th>Estado</th>
                        <th>Fecha Habilitación</th>
                        <th>Fecha Vencimiento</th>
                        <th>Categoría</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td colspan="7" class="no-data">No hay datos disponibles</td>
                    </tr>
                </tbody>
            </table>
            '''
        
        # Tres tablas separadas: Proveedores, Personas, Vehículos
        return '''
                 <div class="table-section">
             <h3 style="padding:15px 20px; color:white; background:#34495e; margin:0; font-size:1.1rem; font-weight:500; text-transform:uppercase;">Contratistas</h3>
            <table id="tablaProveedores">
                <thead>
                    <tr>
                        <th>CUIT</th>
                        <th>Proveedor</th>
                        <th>Cliente</th>
                        <th>Estado</th>
                        <th>Fecha</th>
                        <th>Edificio/Sector</th>
                    </tr>
                </thead>
                <tbody></tbody>
            </table>
        </div>
                                   <div class="table-section" style="margin-top:24px">
              <h3 style="padding:15px 20px; color:white; background:#34495e; margin:0; font-size:1.1rem; font-weight:500; text-transform:uppercase;">Trabajadores</h3>
             <table id="tablaPersonas">
                 <thead>
                     <tr>
                         <th>Cuil/Cuit</th>
                         <th>Apellido, Nombre</th>
                         <th>Proveedor</th>
                         <th>Cliente</th>
                         <th>Edificio/Sector</th>
                         <th>Estado</th>
                         <th>Fecha</th>
                     </tr>
                 </thead>
                 <tbody></tbody>
             </table>
         </div>
                 <div class="table-section" style="margin-top:24px">
             <h3 style="padding:15px 20px; color:white; background:#34495e; margin:0; font-size:1.1rem; font-weight:500; text-transform:uppercase;">Vehículos</h3>
             <table id="tablaVehiculos">
                 <thead>
                     <tr>
                         <th>Dominio</th>
                         <th>Marca</th>
                         <th>Modelo</th>
                         <th>Proveedor</th>
                         <th>Cliente</th>
                         <th>Edificio/Sector</th>
                         <th>Tipo</th>
                         <th>Estado</th>
                         <th>Fecha</th>
                     </tr>
                 </thead>
                 <tbody></tbody>
             </table>
         </div>
        '''

if __name__ == "__main__":
    generator = WebGenerator()
    output_path = generator.generar_html()
    print(f"Dashboard generado en: {output_path}")
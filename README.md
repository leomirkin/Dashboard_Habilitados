# Sistema de Gestión de Recursos

Sistema automatizado para scraping de múltiples sistemas de gestión documental y generación de dashboard web centralizado.

## 🚀 Instalación Rápida

1. Ejecuta el setup:
```bash
python setup.py
```

2. Edita el archivo `sistemas_config.json` con tus credenciales y selectores

3. Prueba el sistema:
```bash
python main.py --completo
```

## 📋 Configuración

### Archivo `sistemas_config.json`

Edita este archivo para configurar cada sistema:

```json
{
  "nombre": "Sistema_Cliente_A",
  "url_login": "https://tu-sistema.com/login",
  "usuario": "tu_usuario",
  "password": "tu_password",
  "selectores": {
    "usuario": "#username",
    "password": "#password",
    "login_btn": "#login-button",
    "tabla": "#recursos-table",
    "col_nombre": 0,
    "col_contratista": 1,
    "col_estado": 2
  },
  "filtros_requeridos": ["filtro_habilitados"]
}
```

### Selectores CSS

Los selectores deben apuntar a los elementos correctos de cada sistema:

- `usuario`: Campo de entrada del nombre de usuario
- `password`: Campo de entrada de la contraseña
- `login_btn`: Botón de login
- `tabla`: Tabla que contiene los recursos
- `col_nombre`: Índice de columna para el nombre (0-based)
- `col_contratista`: Índice de columna para el contratista
- `col_estado`: Índice de columna para el estado

## 🎯 Uso

### Comandos principales:

```bash
# Ejecutar scraping completo y generar dashboard
python main.py --completo

# Solo scraping (sin navegador visible)
python main.py --scraping --headless

# Solo generar dashboard
python main.py --dashboard

# Iniciar servidor web local
python main.py --servidor

# Programar ejecución diaria a las 7:00 AM
python main.py --programar

# Ver estadísticas actuales
python main.py --stats
```

### Script de inicio rápido:

```bash
# Usar script de inicio (Linux/Mac)
./inicio.sh completo
./inicio.sh servidor
./inicio.sh stats
```

## 📊 Dashboard Web

El dashboard incluye:

- ✅ Vista centralizada de todos los recursos
- 🔍 Búsqueda en tiempo real
- 🏷️ Filtros por cliente, contratista y estado
- 📈 Estadísticas resumidas
- 📱 Diseño responsivo
- 🎨 Interfaz moderna y profesional

## ⚙️ Programación Automática

Para ejecutar el sistema automáticamente todos los días:

```bash
python main.py --programar --hora 07:00
```

O usa cron (Linux/Mac):
```bash
# Editar crontab
crontab -e

# Agregar línea para ejecutar a las 7:00 AM diariamente
0 7 * * * /usr/bin/python3 /ruta/a/tu/proyecto/main.py --completo --headless
```

## 🔧 Solución de Problemas

### ChromeDriver no encontrado
```bash
pip install webdriver-manager
```

### Error de permisos
```bash
chmod +x inicio.sh
```

### Error de dependencias
```bash
pip install -r requirements.txt
```

## 📁 Estructura del Proyecto

```
proyecto/
├── main.py                 # Script principal
├── scraping_system.py      # Motor de scraping
├── web_generator.py        # Generador de dashboard
├── sistemas_config.json    # Configuración de sistemas
├── requirements.txt        # Dependencias
├── inicio.sh              # Script de inicio rápido
├── web_output/            # Dashboard generado
├── logs/                 # Archivos de log
└── data/                # Datos extraídos
```

## 🚨 Seguridad

- Nunca subas `sistemas_config.json` a repositorios públicos
- Usa variables de entorno para credenciales sensibles
- Considera usar autenticación de dos factores cuando sea posible

## 🤝 Contribuir

1. Fork el proyecto
2. Crea una rama para tu feature
3. Commit tus cambios
4. Push a la rama
5. Abre un Pull Request

## 📄 Licencia

Este proyecto está bajo la Licencia MIT.

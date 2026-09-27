# Job Hunt

Busca ofertas de empleo que encajan con tu CV, las puntúa con IA y aplica por ti. Todo corre en tu equipo; tus datos no salen de él
salvo para hablar con la IA que elijas y con los portales de empleo.

## Instalar (una vez)

1. En GitHub pulsa **Code → Download ZIP** y descomprímelo donde quieras (por ejemplo en Documentos).
2. Abre la carpeta y haz doble clic en el instalador de tu sistema:
   - **Windows:** `Instalar.bat`
   - **Mac:** `instalar.command` (si macOS lo bloquea: clic derecho → Abrir)
   - **Linux:** en una terminal, `./instalar.sh`
3. Espera a que termine (5–15 minutos la primera vez). Instala lo que falte (Python, Node.js, Git, Chrome), crea un acceso
   directo **Job Hunt** en el escritorio y abre la aplicación en tu navegador.

## Primer uso (3 pasos en pantalla)

1. **Elige la IA:**
   - **Claude** (recomendado): evalúa las ofertas y además rellena y envía los formularios. Necesitas
     [Claude Code](https://claude.com/claude-code) instalado y con sesión iniciada.
   - **Gemini** (gratis o muy barato): evalúa las ofertas; los formularios de empresa los envías tú con un clic desde la lista.
     Consigue una clave en [Google AI Studio](https://aistudio.google.com/apikey).
2. **Sube tu CV** (PDF, Word, .md o .txt). La IA rellena tu perfil y propone los puestos a buscar.
3. **Revisa y confirma** tus datos y filtros: puestos, modalidad (remoto / híbrido / presencial), ciudades o países, sueldo mínimo,
   idiomas, lo que quieres descartar…

Después pulsa **Ejecutar ahora** (la primera vez tarda más) y **Activar programación** para que busque sola cada día.
Si quieres aplicar también con **LinkedIn Easy Apply**, actívalo en Configuración y pulsa «Iniciar sesión» en el Panel: se abre
un Chrome aparte donde inicias sesión una sola vez. Tiene un tope diario para no arriesgar tu cuenta.

## Uso diario

Abre **Job Hunt** desde el escritorio. La ventana que se abre junto al navegador es el servidor: no la cierres mientras la uses.

- **Panel:** estado, próxima ejecución, progreso en vivo y consumo de IA.
- **Solicitudes:** cada oferta con su estado (En cola, Enviada, Acción requerida, Fallida, Descartada), el motivo y su historial.
  «Acción requerida» significa que debes terminarla tú (CAPTCHA, portal con cuenta propia, envío por email…).
- **Ejecuciones:** historial y logs de cada ejecución.
- **Perfil / Configuración:** tus datos y todos los filtros. Al guardar se aplica todo automáticamente.

## ¿Qué gasta tokens de IA?

| Paso | Gasta IA |
|---|---|
| Buscar ofertas y aplicar filtros | No |
| Evaluar cada oferta que pasa los filtros | Sí (modelo económico) |
| Rellenar y enviar formularios (solo con Claude) | Sí, es lo más costoso por unidad |
| LinkedIn Easy Apply | No |

El Panel muestra las evaluaciones y envíos hechos. Con Claude se usa tu propia suscripción o cuenta.

## Salvaguardas (no se pueden desactivar)

- Nunca resuelve CAPTCHAs, nunca crea cuentas y nunca escribe contraseñas: esos casos quedan como «Acción requerida».
- Nunca inventa experiencia: el CV adaptado solo reordena lo que ya pone tu CV.
- Las preguntas personales o legales que no hayas respondido en tu Perfil se dejan en blanco.
- LinkedIn aplica con un tope diario configurable.

## Actualizar

En **Conexiones → Buscar e instalar actualización** (si instalaste desde un ZIP, descarga el nuevo ZIP y vuelve a ejecutar el
instalador: tus datos se conservan porque viven en `jobhunt.db` y `profile/`).

## Problemas frecuentes

- **No abre en el navegador:** vuelve a abrir el acceso directo; entra en http://127.0.0.1:8765.
- **La IA no responde:** en Conexiones pulsa «Probar». Con Claude, abre una terminal y ejecuta `claude` una vez para iniciar sesión.
- **Pausar todo:** botón «Pausar» del Panel.

## Comprobación en Mac y Linux (para quien lo pruebe primero)

- [ ] El instalador termina sin errores y aparece el acceso directo.
- [ ] El alta con un CV en PDF y otro en Word rellena el perfil.
- [ ] «Ejecutar ahora» completa una ejecución y aparecen ofertas en Solicitudes.
- [ ] «Activar programación» crea la tarea (Mac: `launchctl list | grep jobhunt`; Linux: `crontab -l`).
- [ ] «Iniciar sesión» en LinkedIn abre Chrome con un perfil aparte.

## Licencias

Ver [NOTICE](NOTICE).

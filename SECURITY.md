# Política de seguridad

## Reportar una vulnerabilidad

No abras un issue público. Usa **[Report a vulnerability](https://github.com/juanjo32/tasas-co/security/advisories/new)** (pestaña *Security* del repositorio) para enviar un reporte privado. Incluye qué encontraste, cómo reproducirlo y el impacto que ves.

Respondo en un plazo de 7 días.

## Alcance

- El sitio estático en `juanjo32.github.io/tasas-co`: XSS, inyección de contenido y carga de recursos de terceros.
- El flujo de GitHub Actions (`.github/workflows/`): escalada de permisos, fuga de secretos e inyección en scripts.
- El código de `tasasco/`: cómo procesa los datos de datos.gov.co (inyección en CSV o Markdown).

## Fuera de alcance

- La exactitud de los datos de la Superintendencia Financiera. Esos errores se reportan en un issue normal.
- Hallazgos que dependan de un navegador desactualizado o de una extensión del usuario.

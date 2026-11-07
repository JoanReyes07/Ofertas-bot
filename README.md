# Ofertas bot (Mercado Libre afiliados)

Toma los más vendidos de varias categorías, se queda con los de mayor descuento, redacta los textos con Claude y los reparte a 4 canales:

| Canal | Qué hace el bot |
|---|---|
| Web | Genera `docs/index.html` solo (GitHub Pages) |
| Facebook | Publica en tu Página con la API oficial |
| WhatsApp | Deja `out/whatsapp/FECHA.txt` listo para pegar en tu canal |
| TikTok | Deja `out/tiktok/ID.md` con guion, texto e imagen |

## Flujo diario
1. **fetch** (automático, 8:00): revisa el top 20 de más vendidos de cada categoría (`CATEGORIES`) y pone los de mayor descuento en `links_pendientes.csv`.
2. **Tú:** en la app de Mercado Libre abre cada producto de la lista, toca Compartir → *Copiar link* y pega ese enlace en la columna `affiliate_link` del CSV (se puede editar desde el celular en github.com).
3. **publish** (automático, 12:00 y 20:00): verifica que el precio siga igual, redacta y publica.

Los enlaces de afiliado se generan por producto desde la app; no encontré forma de hacerlo en lote, por eso el paso 2 es manual.

## Instalación
```bash
pip install -r requirements.txt
cp .env.example .env     # llénalo
python -m bot fetch
python -m bot publish
python -m pytest
```

### En GitHub (automático)
1. Sube la carpeta a un repo **privado** (para que no se vean tus datos) o público si quieres Pages gratis.
2. Settings → Secrets and variables → Actions: crea los secretos `MELI_CLIENT_ID`, `MELI_CLIENT_SECRET`, `FB_PAGE_ID`, `FB_PAGE_TOKEN`, `ANTHROPIC_API_KEY` y las variables `WEB_URL`, `SITE_NAME` y, si quieres cambiar las categorías, `CATEGORIES`.
3. Settings → Pages → Branch `main`, carpeta `/docs`.
4. Actions → *ofertas-diarias* → Run workflow para probar.

## Cómo obtiene las ofertas
Con un token `client_credentials`, `/sites/MLM/search` y `/items/{id}` responden **403** (verificado en noviembre de 2026). Por eso el bot usa:

| Endpoint | Para qué |
|---|---|
| `/highlights/MLM/category/{cat}` | Top 20 más vendidos de la categoría |
| `/products/{id}/items` | Precio, precio original y vendedor de la oferta ganadora |
| `/products/{id}` | Nombre e imagen |
| `/users/{seller_id}` | Reputación del vendedor |

La lista de categorías está en `https://api.mercadolibre.com/sites/MLM/categories`. Vehículos, Inmuebles y Servicios se ignoran siempre.

## Pendiente por verificar
- El token de Página de Facebook debe tener permiso para publicar en la Página. Con tu propia app en modo desarrollo normalmente funciona sin revisión de Meta.
- Revisa los términos del programa de afiliados antes de publicar en masa.

## Reglas que el bot respeta
- Solo vendedores con reputación verde, cuando la API la informa.
- Si el precio cambió más de 2 % o el producto ya no está activo, no se publica.
- Todos los textos incluyen aviso de enlace de afiliado.
- La IA solo recibe datos verificados y, si inventa o omite el enlace o el precio, se usa una plantilla.

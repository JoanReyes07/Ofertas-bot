package mx.ofertas.app;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.ContentResolver;
import android.content.ContentValues;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Bundle;
import android.os.Environment;
import android.provider.MediaStore;
import android.webkit.JavascriptInterface;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;

import org.json.JSONArray;
import org.json.JSONObject;

/**
 * Cáscara nativa que carga la app web de GitHub Pages a pantalla completa.
 * Extras nativos expuestos a JavaScript como window.Android:
 *  - readClipboard(): lee el portapapeles sin pedir permiso del navegador.
 *  - openExternal(url): abre el enlace fuera (la app de Mercado Libre si está instalada).
 *  - copyText(text): copia al portapapeles.
 *  - saveFiles(json): guarda los archivos de un producto en Descargas/OfertasMX/<carpeta>/.
 *    json = {"id": "...", "folder": "...", "files": [{"url","name","mime"}]}
 *  - share(url, mime, text, target): descarga la imagen/video y lo comparte a
 *    "tiktok", "whatsapp" o al selector de Android (target vacío). El texto se
 *    copia también al portapapeles porque TikTok ignora el texto adjunto.
 */
public class MainActivity extends Activity {

    private static final String APP_URL = "https://cazaofertasmx.github.io/app/";
    private static final String APP_HOST = "cazaofertasmx.github.io";

    private WebView web;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        web = new WebView(this);
        setContentView(web);

        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true); // localStorage: token y borradores de enlaces
        // siempre la versión más reciente de la app web (GitHub Pages cachea 10 min)
        s.setCacheMode(WebSettings.LOAD_NO_CACHE);

        web.addJavascriptInterface(new Bridge(), "Android");
        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest req) {
                Uri uri = req.getUrl();
                if (APP_HOST.equals(uri.getHost())) {
                    return false; // navegación dentro de la app
                }
                openExternal(uri.toString());
                return true;
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest req, WebResourceError err) {
                if (req.isForMainFrame()) {
                    view.loadData(
                        "<html><body style='font-family:sans-serif;text-align:center;padding:40px'>"
                            + "<h3>Sin conexión</h3><p>Revisa tu internet.</p>"
                            + "<button style='padding:12px 20px;font-size:16px' onclick='location.href=\"" + APP_URL + "\"'>Reintentar</button>"
                            + "</body></html>",
                        "text/html; charset=utf-8", "UTF-8");
                }
            }
        });

        if (savedInstanceState != null) {
            web.restoreState(savedInstanceState);
        } else {
            web.loadUrl(APP_URL);
        }
    }

    @Override
    protected void onSaveInstanceState(Bundle out) {
        super.onSaveInstanceState(out);
        web.saveState(out);
    }

    @Override
    public void onBackPressed() {
        if (web.canGoBack()) {
            web.goBack();
        } else {
            super.onBackPressed();
        }
    }

    private void openExternal(String url) {
        try {
            Intent i = new Intent(Intent.ACTION_VIEW, Uri.parse(url));
            i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            startActivity(i);
        } catch (ActivityNotFoundException e) {
            Toast.makeText(this, "No hay app para abrir el enlace", Toast.LENGTH_SHORT).show();
        }
    }

    private static final String[] TIKTOK = {"com.zhiliaoapp.musically", "com.ss.android.ugc.trill"};
    private static final String[] WHATSAPP = {"com.whatsapp", "com.whatsapp.w4b"};

    private String installed(String[] pkgs) {
        PackageManager pm = getPackageManager();
        for (String p : pkgs) {
            try {
                pm.getPackageInfo(p, 0);
                return p;
            } catch (PackageManager.NameNotFoundException ignored) {
            }
        }
        return null;
    }

    private void copy(String text) {
        ClipboardManager cm = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
        if (cm != null && text != null && !text.isEmpty()) {
            cm.setPrimaryClip(ClipData.newPlainText("Cazaofertas", text));
        }
    }

    private void notifyJs(String status) {
        String js = "window.onShareStatus && window.onShareStatus('" + status.replace("'", "") + "')";
        runOnUiThread(() -> web.evaluateJavascript(js, null));
    }

    private File download(String url) throws Exception {
        String name = Uri.parse(url).getLastPathSegment();
        if (name == null || name.isEmpty()) name = "archivo";
        name = name.replaceAll("[^A-Za-z0-9._-]", "_");
        File out = new File(ShareProvider.shareDir(this), name);
        HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
        c.setConnectTimeout(20000);
        c.setReadTimeout(60000);
        c.setUseCaches(false);
        if (c.getResponseCode() != 200) throw new Exception("HTTP " + c.getResponseCode());
        try (InputStream in = c.getInputStream(); OutputStream os = new FileOutputStream(out)) {
            byte[] buf = new byte[64 * 1024];
            int n;
            while ((n = in.read(buf)) > 0) os.write(buf, 0, n);
        } finally {
            c.disconnect();
        }
        return out;
    }

    private void doShare(String url, String mime, String text, String target) {
        new Thread(() -> {
            try {
                notifyJs("Descargando…");
                File f = download(url);
                Uri uri = ShareProvider.uriFor(f);
                runOnUiThread(() -> {
                    copy(text);
                    Intent send = new Intent(Intent.ACTION_SEND);
                    send.setType(mime);
                    send.putExtra(Intent.EXTRA_STREAM, uri);
                    if (text != null && !text.isEmpty()) send.putExtra(Intent.EXTRA_TEXT, text);
                    send.setClipData(ClipData.newRawUri("", uri));
                    send.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                    String pkg = "tiktok".equals(target) ? installed(TIKTOK)
                        : "whatsapp".equals(target) ? installed(WHATSAPP) : null;
                    try {
                        if (pkg != null) {
                            send.setPackage(pkg);
                            startActivity(send);
                        } else {
                            startActivity(Intent.createChooser(send, "Compartir"));
                        }
                        notifyJs("Texto copiado: pégalo en la descripción");
                    } catch (ActivityNotFoundException e) {
                        startActivity(Intent.createChooser(send, "Compartir"));
                    }
                });
            } catch (Exception e) {
                notifyJs("No se pudo descargar: " + e.getMessage());
            }
        }).start();
    }

    /** Abre en Chrome (no en la app de Mercado Libre, que no tiene el panel de afiliados). */
    private void openInBrowser(String url) {
        Intent i = new Intent(Intent.ACTION_VIEW, Uri.parse(url));
        i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        String[] browsers = {"com.android.chrome", "com.chrome.beta", "org.mozilla.firefox", "com.sec.android.app.sbrowser"};
        String pkg = installed(browsers);
        if (pkg != null) i.setPackage(pkg);
        try {
            startActivity(i);
        } catch (ActivityNotFoundException e) {
            openExternal(url);
        }
    }

    /** Descarga url y la escribe en Descargas/OfertasMX/folder/name (reemplaza si existe). */
    private void saveToDownloads(String url, String folder, String name, String mime) throws Exception {
        ContentResolver cr = getContentResolver();
        String rel = Environment.DIRECTORY_DOWNLOADS + "/OfertasMX/" + folder + "/";
        // borrar versión anterior del mismo archivo (si la creó esta app)
        try {
            cr.delete(MediaStore.Downloads.EXTERNAL_CONTENT_URI,
                MediaStore.MediaColumns.RELATIVE_PATH + "=? AND " + MediaStore.MediaColumns.DISPLAY_NAME + "=?",
                new String[]{rel, name});
        } catch (Exception ignored) {
        }
        ContentValues v = new ContentValues();
        v.put(MediaStore.MediaColumns.DISPLAY_NAME, name);
        v.put(MediaStore.MediaColumns.MIME_TYPE, mime);
        v.put(MediaStore.MediaColumns.RELATIVE_PATH, rel);
        v.put(MediaStore.MediaColumns.IS_PENDING, 1);
        Uri item = cr.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, v);
        if (item == null) throw new Exception("no pude crear " + name);
        HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
        c.setConnectTimeout(20000);
        c.setReadTimeout(60000);
        c.setUseCaches(false);
        try {
            if (c.getResponseCode() != 200) throw new Exception("HTTP " + c.getResponseCode() + " en " + name);
            try (InputStream in = c.getInputStream(); OutputStream os = cr.openOutputStream(item)) {
                byte[] buf = new byte[64 * 1024];
                int n;
                while ((n = in.read(buf)) > 0) os.write(buf, 0, n);
            }
        } catch (Exception e) {
            cr.delete(item, null, null);
            throw e;
        } finally {
            c.disconnect();
        }
        ContentValues done = new ContentValues();
        done.put(MediaStore.MediaColumns.IS_PENDING, 0);
        cr.update(item, done, null, null);
    }

    private void doSave(String json) {
        new Thread(() -> {
            String id = "";
            try {
                JSONObject o = new JSONObject(json);
                id = o.optString("id");
                String folder = o.getString("folder").replaceAll("[\\/:*?\"<>|]", "_");
                JSONArray files = o.getJSONArray("files");
                for (int i = 0; i < files.length(); i++) {
                    JSONObject f = files.getJSONObject(i);
                    notifyJs("Guardando " + (i + 1) + "/" + files.length() + "…");
                    saveToDownloads(f.getString("url"), folder, f.getString("name"), f.getString("mime"));
                }
                final String done = id;
                runOnUiThread(() -> web.evaluateJavascript(
                    "window.onSaved && window.onSaved('" + done.replace("'", "") + "', true)", null));
            } catch (Exception e) {
                final String failed = id;
                notifyJs("Error al guardar: " + e.getMessage());
                runOnUiThread(() -> web.evaluateJavascript(
                    "window.onSaved && window.onSaved('" + failed.replace("'", "") + "', false)", null));
            }
        }).start();
    }

    /** Métodos visibles desde JavaScript. */
    private class Bridge {
        @JavascriptInterface
        public String readClipboard() {
            ClipboardManager cm = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
            if (cm == null || !cm.hasPrimaryClip()) return "";
            ClipData clip = cm.getPrimaryClip();
            if (clip == null || clip.getItemCount() == 0) return "";
            CharSequence text = clip.getItemAt(0).coerceToText(MainActivity.this);
            return text == null ? "" : text.toString();
        }

        @JavascriptInterface
        public void openExternal(final String url) {
            runOnUiThread(() -> MainActivity.this.openExternal(url));
        }

        @JavascriptInterface
        public void openInBrowser(final String url) {
            runOnUiThread(() -> MainActivity.this.openInBrowser(url));
        }

        @JavascriptInterface
        public void copyText(final String text) {
            runOnUiThread(() -> copy(text));
        }

        @JavascriptInterface
        public void saveFiles(String json) {
            doSave(json);
        }

        @JavascriptInterface
        public void share(String url, String mime, String text, String target) {
            doShare(url, mime, text, target);
        }
    }
}

package mx.ofertas.app;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.webkit.JavascriptInterface;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

/**
 * Cáscara nativa que carga la app web de GitHub Pages a pantalla completa.
 * Extras nativos expuestos a JavaScript como window.Android:
 *  - readClipboard(): lee el portapapeles sin pedir permiso del navegador.
 *  - openExternal(url): abre el enlace fuera (la app de Mercado Libre si está instalada).
 */
public class MainActivity extends Activity {

    private static final String APP_URL = "https://joanreyes07.github.io/Ofertas-bot/app/";
    private static final String APP_HOST = "joanreyes07.github.io";

    private WebView web;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        web = new WebView(this);
        setContentView(web);

        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true); // localStorage: token y borradores de enlaces
        s.setCacheMode(WebSettings.LOAD_DEFAULT);

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
    }
}

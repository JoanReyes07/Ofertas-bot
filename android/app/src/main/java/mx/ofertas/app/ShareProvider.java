package mx.ofertas.app;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.database.Cursor;
import android.database.MatrixCursor;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import android.provider.OpenableColumns;

import java.io.File;
import java.io.FileNotFoundException;
import java.io.IOException;

/**
 * Entrega a otras apps (TikTok, WhatsApp) los archivos descargados en cache/share/.
 * Versión mínima de FileProvider para no depender de AndroidX.
 */
public class ShareProvider extends ContentProvider {

    public static final String AUTHORITY = "mx.ofertas.app.share";

    static File shareDir(android.content.Context ctx) {
        File d = new File(ctx.getCacheDir(), "share");
        d.mkdirs();
        return d;
    }

    static Uri uriFor(File f) {
        return Uri.parse("content://" + AUTHORITY + "/" + Uri.encode(f.getName()));
    }

    private File fileFor(Uri uri) throws FileNotFoundException {
        File dir = shareDir(getContext());
        File f = new File(dir, uri.getLastPathSegment());
        try {
            // evitar rutas fuera de cache/share
            if (!f.getCanonicalPath().startsWith(dir.getCanonicalPath() + File.separator)) {
                throw new FileNotFoundException("ruta inválida");
            }
        } catch (IOException e) {
            throw new FileNotFoundException(e.getMessage());
        }
        if (!f.exists()) throw new FileNotFoundException(f.getName());
        return f;
    }

    @Override
    public boolean onCreate() {
        return true;
    }

    @Override
    public String getType(Uri uri) {
        String n = uri.getLastPathSegment() == null ? "" : uri.getLastPathSegment().toLowerCase();
        if (n.endsWith(".mp4")) return "video/mp4";
        if (n.endsWith(".png")) return "image/png";
        return "image/jpeg";
    }

    @Override
    public ParcelFileDescriptor openFile(Uri uri, String mode) throws FileNotFoundException {
        return ParcelFileDescriptor.open(fileFor(uri), ParcelFileDescriptor.MODE_READ_ONLY);
    }

    @Override
    public Cursor query(Uri uri, String[] projection, String selection, String[] args, String sort) {
        MatrixCursor c = new MatrixCursor(new String[]{OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE});
        try {
            File f = fileFor(uri);
            c.addRow(new Object[]{f.getName(), f.length()});
        } catch (FileNotFoundException ignored) {
        }
        return c;
    }

    @Override
    public Uri insert(Uri uri, ContentValues values) {
        return null;
    }

    @Override
    public int update(Uri uri, ContentValues values, String sel, String[] args) {
        return 0;
    }

    @Override
    public int delete(Uri uri, String sel, String[] args) {
        return 0;
    }
}

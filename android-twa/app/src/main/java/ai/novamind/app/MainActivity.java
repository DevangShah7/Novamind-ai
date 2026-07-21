package ai.novamind.app;

import android.net.Uri;
import com.google.androidbrowserhelper.trusted.LauncherActivity;

/**
 * NovaMind entry point. Subclasses browserhelper's LauncherActivity so we can
 * point the TWA at the live Vercel deployment without bundling the URL in
 * the signed APK (the Vercel URL is baked at build time).
 */
public class MainActivity extends LauncherActivity {
    @Override
    protected Uri getLaunchingUrl() {
        // Live Vercel deployment. Update this if you redeploy under a new
        // domain. For local testing, point to http://10.0.2.2:8000 instead.
        return Uri.parse("https://web-ivory-eta-87.vercel.app");
    }
}

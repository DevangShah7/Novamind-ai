package ai.novamind.app;

import android.net.Uri;
import com.google.androidbrowserhelper.trusted.LauncherActivity;

/**
 * NovaMind entry point. Subclasses browserhelper's LauncherActivity so we can
 * point the TWA at the live deployment without bundling the URL in the
 * signed APK (the URL is baked at build time).
 */
public class MainActivity extends LauncherActivity {
    @Override
    protected Uri getLaunchingUrl() {
        // Live Tailscale Funnel deployment (public ingress to the dev box).
        // Update this if you move off Tailscale Funnel to a permanent domain.
        // For local emulator testing, point to http://10.0.2.2:3000 instead.
        return Uri.parse("https://novamind.taile50f6f.ts.net");
    }
}

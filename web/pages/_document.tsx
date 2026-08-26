import Document, { Html, Head, Main, NextScript } from 'next/document';

// Runs before React hydrates — sets the `dark` class on <html> based on
// the stored theme or the OS preference. Without this, dark-mode users
// see a flash of light on every page load.
const themeInitScript = `
(function () {
  try {
    var stored = localStorage.getItem('theme');
    var resolved;
    if (stored === 'light' || stored === 'dark') {
      resolved = stored;
    } else {
      resolved = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }
    if (resolved === 'dark') document.documentElement.classList.add('dark');
    else document.documentElement.classList.remove('dark');
  } catch (_) {}
})();
`;

export default class MyDocument extends Document {
  static async getInitialProps(ctx) {
    const initialProps = await Document.getInitialProps(ctx);
    return { ...initialProps };
  }

  render() {
    return (
      <Html>
        <Head>
          <link rel="manifest" href="/manifest.json" />
          <link rel="apple-touch-icon" href="/icons/icon-192x192.png" />
          <link rel="preconnect" href="https://fonts.googleapis.com" />
          <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
          <meta name="theme-color" content="#7c5cff" />
          <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
        </Head>
        <body>
          <Main />
          <NextScript />
        </body>
      </Html>
    );
  }
}

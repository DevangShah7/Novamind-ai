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
          <meta name="theme-color" content="#4f46e5" />
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

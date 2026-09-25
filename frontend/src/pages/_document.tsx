import { Html, Head, Main, NextScript } from 'next/document';

export default function Document() {
  return (
    <Html lang="en">
      <Head>
        {/* The public reverse proxy sets `Referrer-Policy: same-origin`, which strips the
            Referer from the embedded Superset iframe and makes Superset reject it (403,
            allowed_domains check). The meta tag takes precedence over the header. */}
        <meta name="referrer" content="strict-origin-when-cross-origin" />
      </Head>
      <body>
        <Main />
        <NextScript />
      </body>
    </Html>
  );
}

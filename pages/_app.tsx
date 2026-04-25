import type { AppProps } from 'next/app';
import '../styles/globals.css';
import { AuthProvider } from '../hooks/useAuth';
import { QuoteProvider } from '../hooks/useQuote';

export default function App({ Component, pageProps }: AppProps) {
  return (
    <AuthProvider>
      <QuoteProvider>
        <Component {...pageProps} />
      </QuoteProvider>
    </AuthProvider>
  );
}

import Nav from '@/components/Nav';

export default function VerifyEmail() {
  return (
    <div className="flex min-h-screen flex-col">
      <Nav />
      <main className="mx-auto flex w-full max-w-md flex-1 flex-col items-center justify-center px-6 py-16 text-center">
        <p className="text-xs uppercase tracking-widest text-pine">One more step</p>
        <h1 className="mt-3 font-display text-3xl font-medium text-ink">Check your email</h1>
        <p className="mt-3 text-ink-soft">
          We&apos;ve sent a confirmation link. Click it to verify your account, then log in to
          claim your 3 free generations.
        </p>
      </main>
    </div>
  );
}

import { redirect } from 'next/navigation';
import Nav from '@/components/Nav';
import { createClient } from '@/lib/supabase/server';

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  // Belt-and-braces: middleware already redirects unauthenticated requests
  // away from these routes, but a Server Component shouldn't render
  // authenticated-only content without checking for itself too.
  if (!user) {
    redirect('/login');
  }

  return (
    <div className="flex min-h-screen flex-col">
      <Nav email={user.email} />
      <main className="mx-auto w-full max-w-5xl flex-1 px-6 py-10">{children}</main>
    </div>
  );
}

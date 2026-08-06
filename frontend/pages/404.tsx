export default function Custom404() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-24">
      <h1 className="text-6xl font-bold text-primary mb-4">404</h1>
      <p className="text-xl text-gray-600">Page not found</p>
      <a href="/" className="mt-8 text-primary underline hover:text-blue-800">
        Go back home
      </a>
    </main>
  );
}

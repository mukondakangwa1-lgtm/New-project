function Error({ statusCode }: { statusCode: number }) {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-24">
      <h1 className="text-6xl font-bold text-red-600 mb-4">
        {statusCode || "Error"}
      </h1>
      <p className="text-xl text-gray-600">
        {statusCode
          ? `A ${statusCode} error occurred on server`
          : "An error occurred on client"}
      </p>
      <a href="/" className="mt-8 text-primary underline hover:text-blue-800">
        Go back home
      </a>
    </main>
  );
}

Error.getInitialProps = ({ res, err }: { res: any; err: any }) => {
  const statusCode = res ? res.statusCode : err ? err.statusCode : 404;
  return { statusCode };
};

export default Error;

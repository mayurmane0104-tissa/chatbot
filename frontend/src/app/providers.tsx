// "use client";
// import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
// import { useState } from "react";
// import { Toaster } from "sonner";

// export function Providers({ children }: { children: React.ReactNode }) {
//   const [qc] = useState(() => new QueryClient({ defaultOptions: { queries: { staleTime: 60000, retry: 1 } } }));
//   return (
//     <QueryClientProvider client={qc}>
//       {children}
//       <Toaster
//         position="top-right"
//         toastOptions={{
//           style: {
//             background: "var(--tt-surface)",
//             border: "1px solid var(--tt-border)",
//             color: "var(--tt-text)",
//             fontFamily: "var(--font-main)",
//           }
//         }}
//       />
//     </QueryClientProvider>
//   );
// }
"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, PropsWithChildren } from "react";
import { Toaster } from "sonner";

export function Providers({ children }: PropsWithChildren) {
  const [qc] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { staleTime: 60000, retry: 1 },
        },
      })
  );

  return (
    <QueryClientProvider client={qc}>
      {children}
      <Toaster
        position="top-right"
        toastOptions={{
          style: {
            background: "var(--tt-surface)",
            border: "1px solid var(--tt-border)",
            color: "var(--tt-text)",
            fontFamily: "var(--font-main)",
          },
        }}
      />
    </QueryClientProvider>
  );
}
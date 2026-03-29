'use client';

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function Page() {
  const router = useRouter();

  useEffect(() => {
    // Landing page should open the admin area.
    router.replace("/admin");
  }, [router]);

  return null;
}

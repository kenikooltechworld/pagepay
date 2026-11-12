import { Redirect } from "expo-router";
import { useAuthStore } from "@/src/shared/store/auth";

export default function Index() {
  const hydrated = useAuthStore((s) => s.hydrated);
  const token = useAuthStore((s) => s.token);

  if (!hydrated) return null;
  return <Redirect href={token ? "/(app)/home" : "/(auth)"} />;
}

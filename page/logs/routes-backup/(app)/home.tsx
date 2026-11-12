import { View } from "react-native";
import { Text } from "@/components/ui/text";
import { Button } from "@/components/ui/button";
import { useLogout } from "@/src/shared/api/auth";

export default function Home() {
  const logout = useLogout();
  return (
    <View className="flex-1 items-center justify-center bg-background p-6">
      <Text className="mb-6 text-2xl font-bold text-foreground">Home</Text>
      <Button onPress={() => logout.mutate()} disabled={logout.isPending}>
        {logout.isPending ? "Logging out..." : "Logout"}
      </Button>
    </View>
  );
}


import { useEffect, useRef, useState } from "react";
import { KeyboardAvoidingView, Platform, ScrollView, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { StatusBar } from "expo-status-bar";
import Animated, { Easing, useAnimatedStyle, useSharedValue, withTiming } from "react-native-reanimated";
import { Text } from "@/components/ui/text";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { AuthTabSwitch, type AuthTab } from "@/src/features/auth/components/AuthTabSwitch";
import { LoginForm } from "@/src/features/auth/components/LoginForm";
import { RegisterForm } from "@/src/features/auth/components/RegisterForm";

export default function AuthIndex() {
  const [activeTab, setActiveTab] = useState<AuthTab>("login");
  const contentOpacity = useSharedValue(1);
  const pendingTab = useRef<AuthTab | null>(null);
  const isMounted = useRef(true);

  useEffect(() => () => {
    isMounted.current = false;
  }, []);

  const handleTabChange = (tab: AuthTab) => {
    if (tab === activeTab) return;
    contentOpacity.value = withTiming(0, { duration: 80, easing: Easing.out(Easing.cubic) });
    pendingTab.current = tab;
    setTimeout(() => {
      if (!isMounted.current) return;
      if (pendingTab.current) setActiveTab(pendingTab.current);
      pendingTab.current = null;
      contentOpacity.value = withTiming(1, { duration: 150, easing: Easing.out(Easing.cubic) });
    }, 80);
  };

  const contentStyle = useAnimatedStyle(() => ({ opacity: contentOpacity.value }));

  return (
    <View className="flex-1 bg-background">
      <StatusBar style="auto" />
      <SafeAreaView style={{ flex: 1 }} edges={["top", "bottom"]}>
        <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : "height"} style={{ flex: 1 }}>
          <ScrollView contentContainerClassName="flex-grow justify-center px-4 py-6" keyboardShouldPersistTaps="handled">
            <View className="mb-2 px-1">
              <Text className="text-sm font-semibold tracking-[2px] uppercase text-muted-foreground">PagePay</Text>
            </View>
            <AuthTabSwitch activeTab={activeTab} onTabChange={handleTabChange} />
            <Animated.View style={contentStyle}>
              {activeTab === "login" ? (
                <LoginForm onSwitchToRegister={() => handleTabChange("register")} />
              ) : (
                <RegisterForm onSwitchToLogin={() => handleTabChange("login")} />
              )}
            </Animated.View>
            <View className="flex-row items-center gap-3 my-6 px-1">
              <Separator className="flex-1" />
              <Text className="text-muted-foreground text-xs font-medium">OR</Text>
              <Separator className="flex-1" />
            </View>
            <Button variant="outline" className="w-full" onPress={() => {}}>
              Continue with Google
            </Button>
          </ScrollView>
        </KeyboardAvoidingView>
      </SafeAreaView>
    </View>
  );
}

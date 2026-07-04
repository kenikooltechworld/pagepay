import { Tabs } from 'expo-router';
import React from 'react';
import { StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { PagePay } from '@/constants/theme';
import { useEffectiveScheme } from '@/src/shared/hooks/use-effective-scheme';

type Tokens = (typeof PagePay)['light'];

/**
 * Tab bar uses the PagePay token block instead of the stock RN palette. Mint
 * for the active tab (matches the auth CTA and the balance dot on Home), ink
 * for labels so the bar doesn't look like an afterthought.
 *
 * The tab bar background is the same paper tone as Home so the bar feels like
 * part of the surface rather than a black strip at the bottom.
 */
export default function TabLayout() {
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme];

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: tokens.mint,
        tabBarInactiveTintColor: tokens.inkMuted,
        tabBarStyle: {
          backgroundColor: tokens.paper,
          borderTopColor: tokens.border,
          borderTopWidth: StyleSheet.hairlineWidth,
          // Slight elevation so the bar reads as a physical surface above the
          // paper rather than a painted stripe.
          shadowColor: '#000',
          shadowOpacity: 0.04,
          shadowRadius: 12,
          shadowOffset: { width: 0, height: -2 },
          elevation: 6,
        },
        tabBarLabelStyle: {
          fontSize: 11,
          lineHeight: 14,
          letterSpacing: 0.2,
          fontFamily: 'SpaceGrotesk_500Medium',
        },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: 'Home',
          tabBarIcon: ({ color, size, focused }) => (
            <TabIcon name="home" color={color} size={size} focused={focused} tokens={tokens} />
          ),
        }}
      />
      <Tabs.Screen
        name="catalog"
        options={{
          title: 'Catalog',
          tabBarIcon: ({ color, size, focused }) => (
            <TabIcon name="book" color={color} size={size} focused={focused} tokens={tokens} />
          ),
        }}
      />
      <Tabs.Screen
        name="study"
        options={{
          title: 'Study',
          tabBarIcon: ({ color, size, focused }) => (
            <TabIcon name="school" color={color} size={size} focused={focused} tokens={tokens} />
          ),
        }}
      />
      <Tabs.Screen
        name="tasks"
        options={{
          title: 'Tasks',
          tabBarIcon: ({ color, size, focused }) => (
            <TabIcon name="briefcase" color={color} size={size} focused={focused} tokens={tokens} />
          ),
        }}
      />
      <Tabs.Screen
        name="community"
        options={{
          title: 'Community',
          tabBarIcon: ({ color, size, focused }) => (
            <TabIcon name="people" color={color} size={size} focused={focused} tokens={tokens} />
          ),
        }}
      />
      <Tabs.Screen
        name="wallet"
        options={{
          title: 'Wallet',
          tabBarIcon: ({ color, size, focused }) => (
            <TabIcon name="wallet" color={color} size={size} focused={focused} tokens={tokens} />
          ),
        }}
      />
      <Tabs.Screen
        name="profile"
        options={{
          title: 'Profile',
          tabBarIcon: ({ color, size, focused }) => (
            <TabIcon name="person-circle" color={color} size={size} focused={focused} tokens={tokens} />
          ),
        }}
      />
    </Tabs>
  );
}

/**
 * Tab icon with a thin mint underline that appears only when the tab is
 * focused. Subtle way to mark the active tab without redrawing the icon.
 * The underline is purely decorative; the color on the icon already does the
 * primary signaling.
 */
function TabIcon({
  name,
  color,
  size,
  focused,
  tokens,
}: {
  name: keyof typeof Ionicons.glyphMap;
  color: string;
  size: number;
  focused: boolean;
  tokens: Tokens;
}) {
  return (
    <View style={{ alignItems: 'center', justifyContent: 'center' }}>
      <Ionicons name={name} size={size} color={color} />
      {focused ? (
        <View
          style={{
            position: 'absolute',
            bottom: -6,
            width: 14,
            height: 2,
            borderRadius: 1,
            backgroundColor: tokens.mint,
          }}
        />
      ) : null}
    </View>
  );
}

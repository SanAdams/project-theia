import React from "react";
import { NavigationContainer } from "@react-navigation/native";
import { createStackNavigator } from "@react-navigation/stack";
import { SafeAreaProvider } from "react-native-safe-area-context";
import CameraScreen from "./src/screens/CameraScreen";
import ResultsScreen from "./src/screens/ResultsScreen";

export interface InventoryItem {
  name: string;
  cic_code: string;
  count: number;
  barcode_image_url?: string;
}

export type RootStackParamList = {
  Camera: undefined;
  Results: { items: InventoryItem[]; total: number };
};

const Stack = createStackNavigator<RootStackParamList>();

export default function App() {
  return (
    <SafeAreaProvider>
      <NavigationContainer>
        <Stack.Navigator initialRouteName="Camera">
          <Stack.Screen
            name="Camera"
            component={CameraScreen}
            options={{ title: "Project Theia" }}
          />
          <Stack.Screen
            name="Results"
            component={ResultsScreen}
            options={{ title: "Inventory Results" }}
          />
        </Stack.Navigator>
      </NavigationContainer>
    </SafeAreaProvider>
  );
}

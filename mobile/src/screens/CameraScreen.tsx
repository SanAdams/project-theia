import React, { useState } from "react";
import {
  View,
  StyleSheet,
  TouchableOpacity,
  Text,
  ActivityIndicator,
  Alert,
} from "react-native";
import * as ImagePicker from "expo-image-picker";
import { useNavigation } from "@react-navigation/native";
import { StackNavigationProp } from "@react-navigation/stack";
import { RootStackParamList } from "../../App";
import { scanImage } from "../services/api";

type NavigationProp = StackNavigationProp<RootStackParamList, "Camera">;

export default function CameraScreen() {
  const [loading, setLoading] = useState(false);
  const navigation = useNavigation<NavigationProp>();

  const handleCapture = async () => {
    const { status } = await ImagePicker.requestCameraPermissionsAsync();
    if (status !== "granted") {
      Alert.alert(
        "Permission required",
        "Camera access is needed to scan inventory.",
      );
      return;
    }

    const result = await ImagePicker.launchCameraAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      quality: 0.8,
    });

    if (!result.canceled) {
      await processImage(result.assets[0].uri);
    }
  };

  const handlePickFromLibrary = async () => {
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      quality: 0.8,
    });

    if (!result.canceled) {
      await processImage(result.assets[0].uri);
    }
  };

  const processImage = async (uri: string) => {
    setLoading(true);
    try {
      const { items, total_boxes } = await scanImage(uri);
      navigation.navigate("Results", { items, total: total_boxes });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      Alert.alert("Error", `Failed to process image: ${msg}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Scan Freezer Inventory</Text>
      <Text style={styles.subtitle}>
        Take a photo of the boxes in the freezer
      </Text>

      {loading ? (
        <ActivityIndicator size="large" color="#007AFF" style={styles.loader} />
      ) : (
        <>
          <TouchableOpacity
            style={styles.primaryButton}
            onPress={handleCapture}
          >
            <Text style={styles.buttonText}>Take Photo</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.secondaryButton}
            onPress={handlePickFromLibrary}
          >
            <Text style={styles.secondaryButtonText}>Choose from Library</Text>
          </TouchableOpacity>
        </>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    padding: 24,
    backgroundColor: "#F2F2F7",
  },
  title: { fontSize: 24, fontWeight: "700", marginBottom: 8, color: "#1C1C1E" },
  subtitle: {
    fontSize: 15,
    color: "#6C6C70",
    marginBottom: 48,
    textAlign: "center",
  },
  loader: { marginTop: 32 },
  primaryButton: {
    backgroundColor: "#007AFF",
    paddingVertical: 16,
    paddingHorizontal: 48,
    borderRadius: 14,
    marginBottom: 16,
    width: "100%",
    alignItems: "center",
  },
  buttonText: { color: "#fff", fontSize: 17, fontWeight: "600" },
  secondaryButton: { paddingVertical: 16, width: "100%", alignItems: "center" },
  secondaryButtonText: { color: "#007AFF", fontSize: 17 },
});

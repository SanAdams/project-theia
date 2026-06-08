import React, { useState } from "react";
import {
  View,
  StyleSheet,
  TouchableOpacity,
  Text,
  ActivityIndicator,
  Alert,
  Image,
  ScrollView,
} from "react-native";
import * as ImagePicker from "expo-image-picker";
import { useNavigation } from "@react-navigation/native";
import { StackNavigationProp } from "@react-navigation/stack";
import { RootStackParamList } from "../../App";
import { scanImage, ScanResult } from "../services/api";
import { InventoryItem } from "../../App";

type NavigationProp = StackNavigationProp<RootStackParamList, "Camera">;

function mergeResults(results: ScanResult[]): ScanResult {
  const map = new Map<string, InventoryItem>();
  const unknowns: InventoryItem[] = [];
  let total_boxes = 0;
  for (const r of results) {
    total_boxes += r.total_boxes;
    for (const item of r.items) {
      if (item.cic_code === "--") {
        unknowns.push({ ...item });
      } else {
        const existing = map.get(item.cic_code);
        if (existing) existing.count += item.count;
        else map.set(item.cic_code, { ...item });
      }
    }
  }
  return { items: [...Array.from(map.values()), ...unknowns], total_boxes };
}

export default function CameraScreen() {
  const [photoQueue, setPhotoQueue] = useState<
    { uri: string; mimeType?: string }[]
  >([]);
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
      const a = result.assets[0];
      setPhotoQueue((q) => [
        ...q,
        { uri: a.uri, mimeType: a.mimeType ?? undefined },
      ]);
    }
  };

  const handlePickFromLibrary = async () => {
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      quality: 0.8,
      allowsMultipleSelection: true,
    });

    if (!result.canceled) {
      setPhotoQueue((q) => [
        ...q,
        ...result.assets.map((a) => ({
          uri: a.uri,
          mimeType: a.mimeType ?? undefined,
        })),
      ]);
    }
  };

  const handleRemovePhoto = (index: number) => {
    setPhotoQueue((q) => q.filter((_, i) => i !== index));
  };

  const handleScan = async () => {
    setLoading(true);
    try {
      const results = await Promise.all(
        photoQueue.map((item) => scanImage(item.uri, item.mimeType)),
      );
      const { items, total_boxes } = mergeResults(results);
      setPhotoQueue([]);
      navigation.navigate("Results", { items, total: total_boxes });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      Alert.alert("Error", `Failed to process images: ${msg}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Scan Freezer Inventory</Text>
      <Text style={styles.subtitle}>
        Add photos of the boxes in the freezer, then tap Scan
      </Text>

      {photoQueue.length > 0 && (
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          style={styles.queueScroll}
          contentContainerStyle={styles.queueContent}
        >
          {photoQueue.map((item, index) => (
            <View key={index} style={styles.thumbWrapper}>
              <Image source={{ uri: item.uri }} style={styles.thumb} />
              <TouchableOpacity
                style={styles.removeButton}
                onPress={() => handleRemovePhoto(index)}
              >
                <Text style={styles.removeButtonText}>×</Text>
              </TouchableOpacity>
            </View>
          ))}
        </ScrollView>
      )}

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

      {photoQueue.length > 0 && !loading && (
        <TouchableOpacity style={styles.scanButton} onPress={handleScan}>
          <Text style={styles.buttonText}>
            Scan {photoQueue.length} Photo{photoQueue.length !== 1 ? "s" : ""}
          </Text>
        </TouchableOpacity>
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
    marginBottom: 24,
    textAlign: "center",
  },
  queueScroll: { maxHeight: 104, marginBottom: 24 },
  queueContent: { paddingHorizontal: 4, gap: 8 },
  thumbWrapper: { position: "relative" },
  thumb: { width: 80, height: 80, borderRadius: 10, backgroundColor: "#ccc" },
  removeButton: {
    position: "absolute",
    top: -6,
    right: -6,
    width: 22,
    height: 22,
    borderRadius: 11,
    backgroundColor: "#FF3B30",
    alignItems: "center",
    justifyContent: "center",
  },
  removeButtonText: {
    color: "#fff",
    fontSize: 16,
    lineHeight: 20,
    fontWeight: "700",
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
  secondaryButton: { paddingVertical: 16, width: "100%", alignItems: "center" },
  secondaryButtonText: { color: "#007AFF", fontSize: 17 },
  buttonText: { color: "#fff", fontSize: 17, fontWeight: "600" },
  scanButton: {
    backgroundColor: "#34C759",
    paddingVertical: 16,
    paddingHorizontal: 48,
    borderRadius: 14,
    marginTop: 16,
    width: "100%",
    alignItems: "center",
  },
});

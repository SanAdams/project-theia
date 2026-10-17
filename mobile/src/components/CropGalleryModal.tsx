import React, { useState } from "react";
import {
  Modal,
  View,
  Text,
  ScrollView,
  Image,
  TouchableOpacity,
  StyleSheet,
  Platform,
  useWindowDimensions,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { resolvedApiBaseUrl } from "../services/api";

interface Props {
  visible: boolean;
  productName: string;
  cropUrls: string[];
  onClose: () => void;
}

export default function CropGalleryModal({
  visible,
  productName,
  cropUrls,
  onClose,
}: Props) {
  const { width, height } = useWindowDimensions();
  const [pageIdx, setPageIdx] = useState(0);

  // Same web fix as ResultsScreen.tsx: flex:1 maps to CSS flex-basis:0%,
  // which beats an explicit height on web, and the Expo web body defaults
  // to overflow:hidden (clips instead of scrolling) — so the scroller needs
  // an explicit height plus minHeight:0 to actually scroll on web.
  const webScrollerFix =
    Platform.OS === "web"
      ? { height: height * 0.6, flexBasis: "auto" as const, minHeight: 0 }
      : null;

  return (
    <Modal
      visible={visible}
      animationType="slide"
      transparent
      onRequestClose={onClose}
    >
      <View style={styles.backdrop}>
        <View style={styles.sheet}>
          <View style={styles.header}>
            <View style={styles.headerText}>
              <Text style={styles.title}>{productName}</Text>
              {cropUrls.length > 1 && (
                <Text style={styles.count}>
                  {pageIdx + 1} / {cropUrls.length}
                </Text>
              )}
            </View>
            <TouchableOpacity onPress={onClose} accessibilityLabel="Close">
              <Ionicons name="close" size={26} color="#1C1C1E" />
            </TouchableOpacity>
          </View>

          <ScrollView
            horizontal
            pagingEnabled
            showsHorizontalScrollIndicator={false}
            onMomentumScrollEnd={(e) =>
              setPageIdx(Math.round(e.nativeEvent.contentOffset.x / width))
            }
            style={[styles.scroller, webScrollerFix]}
          >
            {cropUrls.map((url, i) => (
              <Image
                key={i}
                source={{ uri: `${resolvedApiBaseUrl}${url}` }}
                style={{ width, height: "100%" }}
                resizeMode="contain"
              />
            ))}
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.5)",
    justifyContent: "flex-end",
  },
  sheet: {
    backgroundColor: "#fff",
    borderTopLeftRadius: 16,
    borderTopRightRadius: 16,
    overflow: "hidden",
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: "#E5E5EA",
  },
  headerText: { flexDirection: "row", alignItems: "baseline" },
  title: { fontSize: 17, fontWeight: "600", color: "#1C1C1E" },
  count: { fontSize: 13, color: "#6C6C70", marginLeft: 8 },
  scroller: { height: 320, backgroundColor: "#F2F2F7" },
});

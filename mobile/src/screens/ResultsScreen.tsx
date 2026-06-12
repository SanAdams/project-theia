import React, { useMemo, useRef, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  Image,
  TouchableOpacity,
  Platform,
  useWindowDimensions,
} from "react-native";
import { useNavigation, useRoute, RouteProp } from "@react-navigation/native";
import { useHeaderHeight } from "@react-navigation/elements";
import { StackNavigationProp } from "@react-navigation/stack";
import { Ionicons } from "@expo/vector-icons";
import { RootStackParamList, InventoryItem } from "../../App";
import { resolvedApiBaseUrl } from "../services/api";

type ResultsRouteProp = RouteProp<RootStackParamList, "Results">;
type NavigationProp = StackNavigationProp<RootStackParamList, "Results">;

const PAGE_SIZE = 10;

export default function ResultsScreen() {
  const route = useRoute<ResultsRouteProp>();
  const navigation = useNavigation<NavigationProp>();
  const { items, total } = route.params;

  const { height: windowHeight } = useWindowDimensions();
  const headerHeight = useHeaderHeight();
  // Web fix: styles.container has flex:1, which react-native-web maps to
  // CSS flex-basis:0%. In CSS, flex-basis beats `height` on the main axis,
  // so a plain height was silently ignored and the screen grew to content
  // size (Yoga on native treats height as authoritative; browsers don't).
  // flexBasis:'auto' lets height count again, maxHeight hard-caps growth,
  // and overflow:'hidden' stops min-height:auto from forcing expansion.
  const webHeightFix =
    Platform.OS === "web"
      ? {
          height: windowHeight - headerHeight,
          maxHeight: windowHeight - headerHeight,
          flexBasis: "auto" as const,
          overflow: "hidden" as const,
        }
      : null;

  const [page, setPage] = useState(0);
  const listRef = useRef<FlatList<InventoryItem>>(null);

  const pageCount = Math.max(1, Math.ceil(items.length / PAGE_SIZE));

  const pageItems = useMemo(
    () => items.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE),
    [items, page],
  );

  const goToPage = (next: number) => {
    const clamped = Math.min(Math.max(next, 0), pageCount - 1);
    if (clamped !== page) {
      setPage(clamped);
      listRef.current?.scrollToOffset({ offset: 0, animated: false });
    }
  };

  return (
    <View style={[styles.container, webHeightFix]}>
      <View style={styles.summaryCard}>
        <Text style={styles.summaryLabel}>Total Boxes Detected</Text>
        <Text style={styles.summaryCount}>{total}</Text>
      </View>

      <FlatList
        ref={listRef}
        data={pageItems}
        keyExtractor={(item, index) => `${item.cic_code}-${index}`}
        style={styles.list}
        ListHeaderComponent={() => (
          <View style={[styles.row, styles.header]}>
            <Text style={[styles.rank, styles.headerText]}>#</Text>
            <Text style={[styles.productCell, styles.headerText]}>Product</Text>
            <Text style={[styles.barcodeCell, styles.headerText]}>Barcode</Text>
            <Text style={[styles.count, styles.headerText]}>Count</Text>
          </View>
        )}
        renderItem={({
          item,
          index,
        }: {
          item: InventoryItem;
          index: number;
        }) => (
          <View style={styles.row}>
            <Text style={styles.rank}>{page * PAGE_SIZE + index + 1}</Text>
            <View style={styles.productCell}>
              <Text style={styles.productName}>{item.name}</Text>
              <Text style={styles.cicCode}>{item.cic_code}</Text>
            </View>
            <View style={styles.barcodeCell}>
              {item.barcode_image_url ? (
                <Image
                  source={{
                    uri: `${resolvedApiBaseUrl}${item.barcode_image_url}`,
                  }}
                  style={styles.barcodeImage}
                  resizeMode="contain"
                />
              ) : (
                <Text style={styles.noBarcode}>—</Text>
              )}
            </View>
            <Text style={styles.count}>{item.count}</Text>
          </View>
        )}
      />

      {pageCount > 1 && (
        <View style={styles.pagination}>
          <TouchableOpacity
            style={[styles.pageButton, page === 0 && styles.pageButtonDisabled]}
            onPress={() => goToPage(page - 1)}
            disabled={page === 0}
            accessibilityLabel="Previous page"
          >
            <Ionicons
              name="chevron-back"
              size={20}
              color={page === 0 ? "#C7C7CC" : "#007AFF"}
            />
          </TouchableOpacity>

          <Text style={styles.pageIndicator}>
            Page {page + 1} of {pageCount}
          </Text>

          <TouchableOpacity
            style={[
              styles.pageButton,
              page === pageCount - 1 && styles.pageButtonDisabled,
            ]}
            onPress={() => goToPage(page + 1)}
            disabled={page === pageCount - 1}
            accessibilityLabel="Next page"
          >
            <Ionicons
              name="chevron-forward"
              size={20}
              color={page === pageCount - 1 ? "#C7C7CC" : "#007AFF"}
            />
          </TouchableOpacity>
        </View>
      )}

      <TouchableOpacity
        style={styles.button}
        onPress={() => navigation.navigate("Camera")}
      >
        <Text style={styles.buttonText}>Scan Another</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#F2F2F7", padding: 16 },
  summaryCard: {
    backgroundColor: "#007AFF",
    borderRadius: 16,
    padding: 24,
    alignItems: "center",
    marginBottom: 16,
  },
  summaryLabel: {
    color: "rgba(255,255,255,0.8)",
    fontSize: 14,
    marginBottom: 4,
  },
  summaryCount: { color: "#fff", fontSize: 48, fontWeight: "700" },
  list: {
    flex: 1,
    // Web: lets the list shrink below its content height so it scrolls
    // internally instead of pushing the pagination bar out of the screen.
    minHeight: 0,
    backgroundColor: "#fff",
    borderRadius: 12,
    marginBottom: 12,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 10,
    paddingHorizontal: 16,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: "#E5E5EA",
  },
  header: {
    backgroundColor: "#F2F2F7",
    borderTopLeftRadius: 12,
    borderTopRightRadius: 12,
  },
  headerText: { fontWeight: "600", color: "#6C6C70", fontSize: 12 },
  rank: { width: 28, color: "#6C6C70", fontSize: 15 },
  productCell: { flex: 1 },
  productName: { fontSize: 15, color: "#1C1C1E" },
  cicCode: { fontSize: 12, color: "#6C6C70", marginTop: 1 },
  barcodeCell: {
    width: 96,
    alignItems: "center",
    justifyContent: "center",
  },
  barcodeImage: { width: 80, height: 40 },
  noBarcode: { color: "#C7C7CC", fontSize: 15 },
  count: {
    width: 48,
    textAlign: "right",
    fontSize: 15,
    fontWeight: "600",
    color: "#1C1C1E",
  },
  pagination: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    backgroundColor: "#fff",
    borderRadius: 12,
    paddingVertical: 6,
    paddingHorizontal: 8,
    marginBottom: 12,
  },
  pageButton: {
    width: 40,
    height: 36,
    alignItems: "center",
    justifyContent: "center",
  },
  pageButtonDisabled: { opacity: 0.5 },
  pageIndicator: { fontSize: 14, fontWeight: "600", color: "#1C1C1E" },
  button: {
    backgroundColor: "#007AFF",
    padding: 16,
    borderRadius: 14,
    alignItems: "center",
  },
  buttonText: { color: "#fff", fontSize: 17, fontWeight: "600" },
});

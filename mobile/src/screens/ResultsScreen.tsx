import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
} from 'react-native';
import { useNavigation, useRoute, RouteProp } from '@react-navigation/native';
import { StackNavigationProp } from '@react-navigation/stack';
import { RootStackParamList, InventoryItem } from '../../App';

type ResultsRouteProp = RouteProp<RootStackParamList, 'Results'>;
type NavigationProp = StackNavigationProp<RootStackParamList, 'Results'>;

export default function ResultsScreen() {
  const route = useRoute<ResultsRouteProp>();
  const navigation = useNavigation<NavigationProp>();
  const { items, total } = route.params;

  return (
    <View style={styles.container}>
      <View style={styles.summaryCard}>
        <Text style={styles.summaryLabel}>Total Boxes Detected</Text>
        <Text style={styles.summaryCount}>{total}</Text>
      </View>

      <FlatList
        data={items}
        keyExtractor={(item) => item.product}
        style={styles.list}
        ListHeaderComponent={() => (
          <View style={[styles.row, styles.header]}>
            <Text style={[styles.rank, styles.headerText]}>#</Text>
            <Text style={[styles.productCell, styles.headerText]}>Product</Text>
            <Text style={[styles.count, styles.headerText]}>Count</Text>
          </View>
        )}
        renderItem={({ item, index }: { item: InventoryItem; index: number }) => (
          <View style={styles.row}>
            <Text style={styles.rank}>{index + 1}</Text>
            <View style={styles.productCell}>
              <Text style={styles.productName}>{item.name}</Text>
              <Text style={styles.cicCode}>{item.cic_code}</Text>
            </View>
            <Text style={styles.count}>{item.count}</Text>
          </View>
        )}
      />

      <TouchableOpacity style={styles.button} onPress={() => navigation.navigate('Camera')}>
        <Text style={styles.buttonText}>Scan Another</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F2F2F7', padding: 16 },
  summaryCard: {
    backgroundColor: '#007AFF',
    borderRadius: 16,
    padding: 24,
    alignItems: 'center',
    marginBottom: 16,
  },
  summaryLabel: { color: 'rgba(255,255,255,0.8)', fontSize: 14, marginBottom: 4 },
  summaryCount: { color: '#fff', fontSize: 48, fontWeight: '700' },
  list: { flex: 1, backgroundColor: '#fff', borderRadius: 12, marginBottom: 16 },
  row: {
    flexDirection: 'row',
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: '#E5E5EA',
  },
  header: {
    backgroundColor: '#F2F2F7',
    borderTopLeftRadius: 12,
    borderTopRightRadius: 12,
  },
  headerText: { fontWeight: '600', color: '#6C6C70', fontSize: 12 },
  rank: { width: 28, color: '#6C6C70', fontSize: 15 },
  productCell: { flex: 1 },
  productName: { fontSize: 15, color: '#1C1C1E' },
  cicCode: { fontSize: 12, color: '#6C6C70', marginTop: 1 },
  count: { width: 48, textAlign: 'right', fontSize: 15, fontWeight: '600', color: '#1C1C1E' },
  button: { backgroundColor: '#007AFF', padding: 16, borderRadius: 14, alignItems: 'center' },
  buttonText: { color: '#fff', fontSize: 17, fontWeight: '600' },
});

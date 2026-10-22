<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { api } from '../api'
import { useI18n } from '../composables/useI18n'
import { formatCurrency, formatCurrencyWithDecimals } from '../utils/currency'

const { t, currentCurrency, currentLocale, translateProductName } = useI18n()

// Budget is always held in USD (the API's currency); only the display is localized
const BUDGET_STEP = 500
const DEFAULT_BUDGET = 10000

const budget = ref(DEFAULT_BUDGET)
const maxBudget = ref(0)
const recommendation = ref(null)
const loading = ref(true)
const error = ref(null)

const placing = ref(false)
const placeError = ref(null)
const placedOrder = ref(null)

// Never below the current budget, or the browser clamps the thumb before max_budget arrives
const sliderMax = computed(() => Math.max(budget.value, Math.ceil(maxBudget.value / BUDGET_STEP) * BUDGET_STEP))
const items = computed(() => recommendation.value?.items ?? [])
const maxLeadTime = computed(() => items.value.reduce((max, item) => Math.max(max, item.lead_time_days), 0))
const canPlaceOrder = computed(() => items.value.length > 0 && !placing.value && !loading.value)

const money = (amount) => formatCurrency(amount, currentCurrency.value)
const unitMoney = (amount) => formatCurrencyWithDecimals(amount, currentCurrency.value, 2)

const formatDate = (dateString) => {
  // Date-only strings parse as UTC midnight; treat them as local dates instead
  const date = new Date(/^\d{4}-\d{2}-\d{2}$/.test(dateString) ? `${dateString}T00:00:00` : dateString)
  if (isNaN(date.getTime())) return dateString
  return date.toLocaleDateString(currentLocale.value === 'ja' ? 'ja-JP' : 'en-US', {
    year: 'numeric', month: 'short', day: 'numeric'
  })
}

const trendBadgeClass = (trend) => ({ increasing: 'success', stable: 'info', decreasing: 'warning' }[trend] || 'info')

// Ignore responses from older requests when the slider moves quickly
let requestId = 0
const loadRecommendations = async () => {
  const thisRequest = ++requestId
  loading.value = true
  error.value = null
  try {
    const data = await api.getRestockRecommendations(budget.value)
    if (thisRequest !== requestId) return
    recommendation.value = data
    maxBudget.value = data.max_budget
  } catch (err) {
    if (thisRequest !== requestId) return
    error.value = t('restocking.loadFailed')
    console.error('Failed to load restock recommendations:', err)
  } finally {
    if (thisRequest === requestId) loading.value = false
  }
}

let debounceTimer = null
watch(budget, () => {
  placedOrder.value = null
  placeError.value = null
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(loadRecommendations, 250)
})

const placeOrder = async () => {
  if (!canPlaceOrder.value) return
  placing.value = true
  placeError.value = null
  try {
    placedOrder.value = await api.createRestockOrder({
      budget: budget.value,
      items: items.value.map(item => ({ item_sku: item.item_sku, quantity: item.recommended_quantity }))
    })
  } catch (err) {
    placeError.value = err.response?.data?.detail
      ? `${t('restocking.orderFailed')}: ${err.response.data.detail}`
      : t('restocking.orderFailed')
    console.error('Failed to place restock order:', err)
  } finally {
    placing.value = false
  }
}

onMounted(loadRecommendations)
onBeforeUnmount(() => clearTimeout(debounceTimer))
</script>

<template>
  <div class="restocking">
    <div class="page-header">
      <h2>{{ t('restocking.title') }}</h2>
      <p>{{ t('restocking.description') }}</p>
    </div>

    <div class="card budget-card">
      <div class="budget-header">
        <label for="budget-slider" class="budget-label">{{ t('restocking.budget') }}</label>
        <span class="budget-value">{{ money(budget) }}</span>
      </div>
      <input
        id="budget-slider"
        v-model.number="budget"
        type="range"
        class="budget-slider"
        min="0"
        :max="sliderMax"
        :step="BUDGET_STEP"
        :aria-valuetext="money(budget)"
      />
      <div class="budget-scale">
        <span>{{ money(0) }}</span>
        <span v-if="maxBudget">{{ t('restocking.budgetHint', { max: money(maxBudget) }) }}</span>
        <span>{{ money(sliderMax) }}</span>
      </div>
    </div>

    <div v-if="error" class="error">{{ error }}</div>
    <template v-else-if="recommendation">
      <div class="stats-grid">
        <div class="stat-card info">
          <div class="stat-label">{{ t('restocking.orderTotal') }}</div>
          <div class="stat-value">{{ money(recommendation.total_cost) }}</div>
        </div>
        <div class="stat-card success">
          <div class="stat-label">{{ t('restocking.remainingBudget') }}</div>
          <div class="stat-value">{{ money(recommendation.remaining_budget) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ t('restocking.itemsSelected') }}</div>
          <div class="stat-value">{{ items.length }}</div>
        </div>
        <div class="stat-card warning">
          <div class="stat-label">{{ t('restocking.maxLeadTime') }}</div>
          <div class="stat-value">{{ t('restocking.days', { count: maxLeadTime }) }}</div>
        </div>
      </div>

      <div class="card" :class="{ stale: loading }">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.recommendedItems') }} ({{ items.length }})</h3>
          <button
            type="button"
            class="place-order-btn"
            :disabled="!canPlaceOrder"
            @click="placeOrder"
          >
            {{ placing ? t('restocking.placingOrder') : t('restocking.placeOrder') }}
          </button>
        </div>

        <div v-if="placedOrder" class="order-result success" role="status">
          <span>{{ t('restocking.orderPlaced', { number: placedOrder.order_number, date: formatDate(placedOrder.expected_delivery) }) }}</span>
          <router-link to="/orders" class="order-result-link">{{ t('restocking.viewOrders') }}</router-link>
        </div>
        <div v-if="placeError" class="order-result danger" role="alert">{{ placeError }}</div>

        <div v-if="items.length === 0" class="empty-state">{{ t('restocking.noRecommendations') }}</div>
        <div v-else class="table-container">
          <table>
            <thead>
              <tr>
                <th>{{ t('restocking.table.sku') }}</th>
                <th>{{ t('restocking.table.item') }}</th>
                <th>{{ t('restocking.table.trend') }}</th>
                <th class="num">{{ t('restocking.table.forecastedDemand') }}</th>
                <th class="num">{{ t('restocking.table.quantity') }}</th>
                <th class="num">{{ t('restocking.table.unitCost') }}</th>
                <th class="num">{{ t('restocking.table.lineCost') }}</th>
                <th class="num">{{ t('restocking.table.leadTime') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in items" :key="item.item_sku">
                <td><strong>{{ item.item_sku }}</strong></td>
                <td>{{ translateProductName(item.item_name) }}</td>
                <td><span :class="['badge', trendBadgeClass(item.trend)]">{{ t(`trends.${item.trend}`) }}</span></td>
                <td class="num">{{ item.forecasted_demand.toLocaleString() }}</td>
                <td class="num">
                  {{ item.recommended_quantity.toLocaleString() }}
                </td>
                <td class="num">{{ unitMoney(item.unit_cost) }}</td>
                <td class="num">{{ money(item.line_cost) }}</td>
                <td class="num">{{ t('restocking.days', { count: item.lead_time_days }) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
    <div v-else-if="loading" class="loading">{{ t('common.loading') }}</div>
  </div>
</template>

<style scoped>
.budget-card {
  padding: 1.25rem 1.5rem;
  margin-bottom: 1.5rem;
}

.budget-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 0.75rem;
}

.budget-label {
  font-size: 0.875rem;
  font-weight: 600;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.budget-value {
  font-size: 1.75rem;
  font-weight: 700;
  color: #0f172a;
}

.budget-slider {
  width: 100%;
  accent-color: #0f172a;
  cursor: pointer;
}

.budget-scale {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  margin-top: 0.5rem;
  font-size: 0.8125rem;
  color: #64748b;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
}

.place-order-btn {
  padding: 0.625rem 1.25rem;
  border: none;
  border-radius: 6px;
  background: #0f172a;
  color: #ffffff;
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s;
}

.place-order-btn:hover:not(:disabled) {
  background: #1e293b;
}

.place-order-btn:disabled {
  background: #cbd5e1;
  cursor: not-allowed;
}

.order-result {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  margin: 0 1.5rem 1rem;
  padding: 0.75rem 1rem;
  border-radius: 6px;
  font-size: 0.875rem;
}

.order-result.success {
  background: #ecfdf5;
  color: #065f46;
  border: 1px solid #a7f3d0;
}

.order-result.danger {
  background: #fef2f2;
  color: #991b1b;
  border: 1px solid #fecaca;
}

.order-result-link {
  color: #065f46;
  font-weight: 600;
  white-space: nowrap;
}

.empty-state {
  padding: 2rem;
  text-align: center;
  color: #64748b;
}

.num {
  text-align: right;
}

.stale {
  opacity: 0.6;
  transition: opacity 0.15s;
}
</style>

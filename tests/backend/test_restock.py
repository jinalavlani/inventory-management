"""
Tests for restocking endpoints (recommendations and submitted orders).
"""
import pytest

import main


@pytest.fixture(autouse=True)
def reset_restock_orders():
    """Submitted orders are in-memory module state; isolate each test."""
    main.restock_orders.clear()
    yield
    main.restock_orders.clear()


class TestRestockRecommendations:
    """Test suite for GET /api/restock/recommendations."""

    def test_recommendations_structure(self, client):
        """Test response shape and per-item fields."""
        response = client.get("/api/restock/recommendations?budget=5000")
        assert response.status_code == 200

        data = response.json()
        for key in ["budget", "total_cost", "remaining_budget", "max_budget", "items"]:
            assert key in data
        assert len(data["items"]) > 0

        item = data["items"][0]
        for key in ["item_sku", "item_name", "trend", "forecasted_demand", "unit_cost",
                    "lead_time_days", "recommended_quantity", "line_cost"]:
            assert key in item

    @pytest.mark.parametrize("budget", [0, 100, 5000, 20000, 1000000])
    def test_recommendations_stay_within_budget(self, client, budget):
        """Test that total cost never exceeds the budget and math is consistent."""
        data = client.get(f"/api/restock/recommendations?budget={budget}").json()

        assert data["total_cost"] <= budget
        assert data["remaining_budget"] == pytest.approx(budget - data["total_cost"], abs=0.01)
        assert data["total_cost"] == pytest.approx(sum(i["line_cost"] for i in data["items"]), abs=0.01)

        for item in data["items"]:
            assert 0 < item["recommended_quantity"] <= item["forecasted_demand"]
            assert item["line_cost"] == pytest.approx(item["recommended_quantity"] * item["unit_cost"], abs=0.01)

    def test_zero_budget_recommends_nothing(self, client):
        """Test that a zero budget returns no items."""
        data = client.get("/api/restock/recommendations?budget=0").json()
        assert data["items"] == []
        assert data["total_cost"] == 0

    def test_max_budget_covers_all_forecast_demand(self, client):
        """Test that the max budget fully covers every priced forecast item."""
        max_budget = client.get("/api/restock/recommendations?budget=0").json()["max_budget"]
        data = client.get(f"/api/restock/recommendations?budget={max_budget}").json()

        forecasts = client.get("/api/demand").json()
        assert len(data["items"]) == len(forecasts)
        for item in data["items"]:
            assert item["recommended_quantity"] == item["forecasted_demand"]

    def test_increasing_trend_prioritized(self, client):
        """Test that increasing-demand items come before stable and decreasing ones."""
        max_budget = client.get("/api/restock/recommendations?budget=0").json()["max_budget"]
        items = client.get(f"/api/restock/recommendations?budget={max_budget}").json()["items"]

        order = {"increasing": 0, "stable": 1, "decreasing": 2}
        ranks = [order[i["trend"]] for i in items]
        assert ranks == sorted(ranks)

    def test_budget_required(self, client):
        """Test that budget is a required query parameter."""
        response = client.get("/api/restock/recommendations")
        assert response.status_code == 422

    def test_negative_budget_rejected(self, client):
        """Test that a negative budget is rejected."""
        response = client.get("/api/restock/recommendations?budget=-1")
        assert response.status_code == 422


class TestRestockOrders:
    """Test suite for /api/restock/orders."""

    def test_no_orders_initially(self, client):
        """Test that there are no submitted orders at start."""
        response = client.get("/api/restock/orders")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_order_from_recommendations(self, client):
        """Test submitting the recommended items as an order."""
        rec = client.get("/api/restock/recommendations?budget=10000").json()
        payload = {
            "budget": 10000,
            "items": [{"item_sku": i["item_sku"], "quantity": i["recommended_quantity"]} for i in rec["items"]],
        }

        response = client.post("/api/restock/orders", json=payload)
        assert response.status_code == 201

        order = response.json()
        assert order["status"] == "Submitted"
        assert order["order_number"].startswith("RST-")
        assert order["total_cost"] == pytest.approx(rec["total_cost"], abs=0.01)
        assert order["lead_time_days"] == max(i["lead_time_days"] for i in rec["items"])
        assert len(order["items"]) == len(rec["items"])

    def test_created_order_is_listed_newest_first(self, client):
        """Test that submitted orders appear in the list, newest first."""
        first = client.post("/api/restock/orders", json={
            "budget": 1000, "items": [{"item_sku": "GSK-203", "quantity": 10}]}).json()
        second = client.post("/api/restock/orders", json={
            "budget": 1000, "items": [{"item_sku": "WDG-001", "quantity": 10}]}).json()

        listed = client.get("/api/restock/orders").json()
        assert [o["id"] for o in listed] == [second["id"], first["id"]]

    def test_expected_delivery_uses_lead_time(self, client):
        """Test that expected delivery = submission date + lead time."""
        from datetime import date, timedelta

        order = client.post("/api/restock/orders", json={
            "budget": 1000, "items": [{"item_sku": "GSK-203", "quantity": 10}]}).json()

        submitted = date.fromisoformat(order["submitted_at"][:10])
        assert order["lead_time_days"] == 5
        assert order["expected_delivery"] == (submitted + timedelta(days=5)).isoformat()

    def test_server_prices_ignore_client(self, client):
        """Test that unit cost comes from server data, not the request."""
        order = client.post("/api/restock/orders", json={
            "budget": 1000,
            "items": [{"item_sku": "GSK-203", "quantity": 10, "unit_cost": 0.01}],
        }).json()
        assert order["items"][0]["unit_cost"] == 2.40
        assert order["total_cost"] == pytest.approx(24.0)

    def test_order_over_budget_rejected(self, client):
        """Test that an order costing more than the budget is rejected."""
        response = client.post("/api/restock/orders", json={
            "budget": 10, "items": [{"item_sku": "MTR-304", "quantity": 1}]})
        assert response.status_code == 400
        assert client.get("/api/restock/orders").json() == []

    def test_unknown_sku_rejected(self, client):
        """Test that an unknown SKU is rejected."""
        response = client.post("/api/restock/orders", json={
            "budget": 1000, "items": [{"item_sku": "NOPE-999", "quantity": 1}]})
        assert response.status_code == 400

    def test_duplicate_sku_rejected(self, client):
        """Test that the same SKU twice in one order is rejected."""
        response = client.post("/api/restock/orders", json={
            "budget": 1000,
            "items": [{"item_sku": "GSK-203", "quantity": 1}, {"item_sku": "GSK-203", "quantity": 2}],
        })
        assert response.status_code == 400

    @pytest.mark.parametrize("payload", [
        {"budget": 1000, "items": []},
        {"budget": 1000, "items": [{"item_sku": "GSK-203", "quantity": 0}]},
        {"budget": 1000, "items": [{"item_sku": "GSK-203", "quantity": -5}]},
        {"budget": -1, "items": [{"item_sku": "GSK-203", "quantity": 1}]},
    ])
    def test_invalid_payload_rejected(self, client, payload):
        """Test validation of empty orders, non-positive quantities and negative budgets."""
        response = client.post("/api/restock/orders", json=payload)
        assert response.status_code == 422

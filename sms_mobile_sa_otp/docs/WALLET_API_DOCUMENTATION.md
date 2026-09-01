# Wallet API Documentation

## Overview

The Wallet API provides functionality for customers to manage their e-wallet balance, view transaction history, and pay for orders using their wallet balance. This document covers all wallet-related endpoints for mobile app integration.

---

## Base URL

```
https://your-odoo-domain.com
```

---

## Authentication

All wallet endpoints require JWT Bearer token authentication.

### Header Format
```
Authorization: Bearer <access_token>
```

### Getting Access Token
Use the `/api/login` endpoint to obtain an access token after successful authentication.

---

## Response Format

All API responses follow this standard format:

### Success Response
```json
{
    "status": "success",
    "message": "Description of the result",
    "data": { ... }
}
```

### Error Response
```json
{
    "status": "failed",
    "message": "Error description",
    "data": {},
    "error_code": "OPTIONAL_ERROR_CODE"
}
```

---

## Error Codes

| HTTP Code | Error Code | Description |
|-----------|------------|-------------|
| 400 | - | Bad Request - Invalid parameters |
| 401 | - | Unauthorized - Invalid or expired token |
| 403 | - | Forbidden - Access denied |
| 404 | - | Not Found - Resource not found |
| 503 | MODULE_NOT_READY | Wallet module not installed |
| 400 | INSUFFICIENT_BALANCE | Not enough wallet balance |

---

## API Endpoints

### 1. Get Wallet Balance

Returns the current wallet balance for the authenticated user.

**Endpoint:** `GET /api/wallet/balance`

**Headers:**
| Header | Required | Description |
|--------|----------|-------------|
| Authorization | Yes | Bearer token |

**Request Example:**
```bash
curl --location 'https://your-domain.com/api/wallet/balance' \
--header 'Authorization: Bearer <access_token>'
```

**Response Example:**
```json
{
    "status": "success",
    "message": "Wallet balance retrieved successfully",
    "data": {
        "wallet_balance": 650.0,
        "currency": "SAR",
        "currency_symbol": "ر.س",
        "partner_id": 47,
        "partner_name": "John Doe"
    }
}
```

**Response Fields:**
| Field | Type | Description |
|-------|------|-------------|
| wallet_balance | float | Current available balance |
| currency | string | Currency code (e.g., SAR, USD) |
| currency_symbol | string | Currency symbol |
| partner_id | integer | Customer ID |
| partner_name | string | Customer name |

---

### 2. Get Wallet History

Returns the transaction history with details of where funds came from and where they were used.

**Endpoint:** `GET /api/wallet/history`

**Headers:**
| Header | Required | Description |
|--------|----------|-------------|
| Authorization | Yes | Bearer token |

**Query Parameters:**
| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| limit | No | 50 | Number of records (max: 100) |
| offset | No | 0 | Records to skip (for pagination) |
| transaction_type | No | all | Filter: `all`, `credit`, `debit` |
| date_from | No | - | Start date (YYYY-MM-DD) |
| date_to | No | - | End date (YYYY-MM-DD) |

**Request Examples:**

```bash
# Get all transactions
curl --location 'https://your-domain.com/api/wallet/history' \
--header 'Authorization: Bearer <access_token>'

# Get only credits with pagination
curl --location 'https://your-domain.com/api/wallet/history?transaction_type=credit&limit=10&offset=0' \
--header 'Authorization: Bearer <access_token>'

# Filter by date range
curl --location 'https://your-domain.com/api/wallet/history?date_from=2025-01-01&date_to=2025-01-31' \
--header 'Authorization: Bearer <access_token>'
```

**Response Example:**
```json
{
    "status": "success",
    "message": "Wallet history retrieved successfully",
    "data": {
        "current_balance": 650.0,
        "currency": "SAR",
        "currency_symbol": "ر.س",
        "total_count": 2,
        "limit": 50,
        "offset": 0,
        "transactions": [
            {
                "id": 2,
                "reference": "WTX/2025/00002",
                "transaction_type": "credit",
                "transaction_type_display": "Credit (Added)",
                "amount": 150.0,
                "currency": "SAR",
                "source_type": "refund",
                "source_type_display": "Order Refund",
                "source_description": "Refund for cancelled order SO123",
                "balance_before": 500.0,
                "balance_after": 650.0,
                "date": "2025-01-18 08:13:51",
                "related_order": {
                    "id": 45,
                    "name": "SO123",
                    "type": "sale_order",
                    "amount_total": 150.0,
                    "state": "cancel"
                },
                "notes": ""
            },
            {
                "id": 1,
                "reference": "WTX/2025/00001",
                "transaction_type": "credit",
                "transaction_type_display": "Credit (Added)",
                "amount": 500.0,
                "currency": "SAR",
                "source_type": "topup",
                "source_type_display": "Wallet Top-up",
                "source_description": "Wallet top-up via credit card",
                "balance_before": 0.0,
                "balance_after": 500.0,
                "date": "2025-01-18 08:10:45",
                "related_order": null,
                "notes": ""
            }
        ]
    }
}
```

**Transaction Types:**
| Type | Display | Description |
|------|---------|-------------|
| credit | Credit (Added) | Money added to wallet |
| debit | Debit (Used) | Money spent from wallet |

**Source Types (where money came from / went to):**
| Source Type | Display | Description |
|-------------|---------|-------------|
| topup | Wallet Top-up | Customer added money to wallet |
| refund | Order Refund | Refund from cancelled order |
| cashback | Cashback | Cashback reward |
| gift | Gift/Voucher | Gift card or voucher credit |
| loyalty | Loyalty Points Conversion | Points converted to wallet |
| promotion | Promotional Credit | Promotional offer credit |
| order_payment | Order Payment | Payment for an order (debit) |
| service_payment | Service Payment | Payment for service (debit) |
| appointment_payment | Appointment Payment | Payment for appointment (debit) |
| manual | Manual Adjustment | Admin adjustment |
| other | Other | Other transactions |

---

### 3. Check Wallet Payment Eligibility

Check if wallet balance is sufficient to pay for an order.

**Endpoint:** `GET /api/wallet/can-pay`

**Headers:**
| Header | Required | Description |
|--------|----------|-------------|
| Authorization | Yes | Bearer token |

**Query Parameters:**
| Parameter | Required | Description |
|-----------|----------|-------------|
| order_amount | Yes* | Amount to check against |
| order_id | Yes* | Sale order ID to get amount from |

*Either `order_amount` OR `order_id` is required (not both)

**Request Examples:**

```bash
# Check by amount
curl --location 'https://your-domain.com/api/wallet/can-pay?order_amount=200' \
--header 'Authorization: Bearer <access_token>'

# Check by order ID
curl --location 'https://your-domain.com/api/wallet/can-pay?order_id=123' \
--header 'Authorization: Bearer <access_token>'
```

**Response Example (Sufficient Balance):**
```json
{
    "status": "success",
    "message": "Wallet payment check completed",
    "data": {
        "can_pay_with_wallet": true,
        "wallet_balance": 650.0,
        "order_amount": 200.0,
        "remaining_balance": 450.0,
        "amount_to_pay_from_wallet": 200.0,
        "amount_remaining_to_pay": 0,
        "currency": "SAR",
        "currency_symbol": "ر.س"
    }
}
```

**Response Example (Insufficient Balance):**
```json
{
    "status": "success",
    "message": "Wallet payment check completed",
    "data": {
        "can_pay_with_wallet": false,
        "wallet_balance": 650.0,
        "order_amount": 1000.0,
        "remaining_balance": 0,
        "amount_to_pay_from_wallet": 650.0,
        "amount_remaining_to_pay": 350.0,
        "currency": "SAR",
        "currency_symbol": "ر.س"
    }
}
```

**Response Fields:**
| Field | Type | Description |
|-------|------|-------------|
| can_pay_with_wallet | boolean | True if wallet can cover full amount |
| wallet_balance | float | Current wallet balance |
| order_amount | float | Order total amount |
| remaining_balance | float | Balance after payment (if sufficient) |
| amount_to_pay_from_wallet | float | Maximum payable from wallet |
| amount_remaining_to_pay | float | Amount still needed (for partial) |

---

### 4. Pay with Wallet

Pay for an order using wallet balance. Requires sufficient balance.

**Endpoint:** `POST /api/wallet/pay`

**Headers:**
| Header | Required | Description |
|--------|----------|-------------|
| Authorization | Yes | Bearer token |
| Content-Type | Yes | application/json |

**Request Body:**
| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| order_id | integer | Yes | - | Sale order ID to pay |
| amount | float | No | Full order amount | Partial payment amount |
| confirm_order | boolean | No | true | Auto-confirm order after payment |

**Request Examples:**

```bash
# Full payment
curl --location 'https://your-domain.com/api/wallet/pay' \
--header 'Authorization: Bearer <access_token>' \
--header 'Content-Type: application/json' \
--data '{
    "order_id": 123
}'

# Partial payment
curl --location 'https://your-domain.com/api/wallet/pay' \
--header 'Authorization: Bearer <access_token>' \
--header 'Content-Type: application/json' \
--data '{
    "order_id": 123,
    "amount": 200.00,
    "confirm_order": true
}'
```

**Success Response:**
```json
{
    "status": "success",
    "message": "Order paid successfully with wallet",
    "data": {
        "transaction_id": 3,
        "transaction_reference": "WTX/2025/00003",
        "amount_paid": 200.0,
        "wallet_balance_before": 650.0,
        "wallet_balance_after": 450.0,
        "currency": "SAR",
        "order": {
            "id": 123,
            "name": "SO001",
            "amount_total": 200.0,
            "state": "sale"
        }
    }
}
```

**Error Response (Insufficient Balance):**
```json
{
    "status": "failed",
    "message": "Insufficient wallet balance",
    "data": {
        "wallet_balance": 100.0,
        "required_amount": 200.0,
        "shortfall": 100.0
    },
    "error_code": "INSUFFICIENT_BALANCE"
}
```

---

### 5. Add Credit to Wallet

Add funds to the wallet (used after successful payment gateway transaction).

**Endpoint:** `POST /api/wallet/add-credit`

**Headers:**
| Header | Required | Description |
|--------|----------|-------------|
| Authorization | Yes | Bearer token |
| Content-Type | Yes | application/json |

**Request Body:**
| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| amount | float | Yes | - | Amount to add |
| source_type | string | No | topup | Source type (see table below) |
| source_description | string | No | - | Custom description |
| payment_reference | string | No | - | External payment reference |

**Valid Source Types:**
- `topup` - Wallet top-up
- `refund` - Order refund
- `cashback` - Cashback reward
- `gift` - Gift/voucher
- `loyalty` - Loyalty points conversion
- `promotion` - Promotional credit
- `manual` - Manual adjustment
- `other` - Other

**Request Example:**
```bash
curl --location 'https://your-domain.com/api/wallet/add-credit' \
--header 'Authorization: Bearer <access_token>' \
--header 'Content-Type: application/json' \
--data '{
    "amount": 100.00,
    "source_type": "topup",
    "source_description": "Wallet top-up via Apple Pay",
    "payment_reference": "PAY-ABC123"
}'
```

**Response Example:**
```json
{
    "status": "success",
    "message": "Wallet credited successfully",
    "data": {
        "transaction_id": 4,
        "transaction_reference": "WTX/2025/00004",
        "amount_credited": 100.0,
        "wallet_balance_before": 450.0,
        "wallet_balance_after": 550.0,
        "currency": "SAR",
        "currency_symbol": "ر.س"
    }
}
```

---

### 6. Get Wallet Summary

Get wallet statistics and summary with breakdown by source type.

**Endpoint:** `GET /api/wallet/summary`

**Headers:**
| Header | Required | Description |
|--------|----------|-------------|
| Authorization | Yes | Bearer token |

**Request Example:**
```bash
curl --location 'https://your-domain.com/api/wallet/summary' \
--header 'Authorization: Bearer <access_token>'
```

**Response Example:**
```json
{
    "status": "success",
    "message": "Wallet summary retrieved successfully",
    "data": {
        "current_balance": 650.0,
        "currency": "SAR",
        "currency_symbol": "ر.س",
        "total_credits": 800.0,
        "total_debits": 150.0,
        "total_transactions": 5,
        "credits_count": 3,
        "debits_count": 2,
        "by_source": {
            "topup": {
                "count": 2,
                "amount": 600.0,
                "type": "credit"
            },
            "refund": {
                "count": 1,
                "amount": 200.0,
                "type": "credit"
            },
            "order_payment": {
                "count": 2,
                "amount": 150.0,
                "type": "debit"
            }
        },
        "recent_transactions": [
            {
                "id": 5,
                "reference": "WTX/2025/00005",
                "transaction_type": "debit",
                "amount": 100.0,
                "source_type": "order_payment",
                "date": "2025-01-18 10:30:00"
            },
            {
                "id": 4,
                "reference": "WTX/2025/00004",
                "transaction_type": "credit",
                "amount": 100.0,
                "source_type": "topup",
                "date": "2025-01-18 09:15:00"
            }
        ]
    }
}
```

---

## Mobile App Integration Guide

### Wallet Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        WALLET FLOW                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐    │
│  │   Top-up     │     │   Refund     │     │   Cashback   │    │
│  │   Payment    │     │   Process    │     │   Reward     │    │
│  └──────┬───────┘     └──────┬───────┘     └──────┬───────┘    │
│         │                    │                    │             │
│         └────────────────────┼────────────────────┘             │
│                              ▼                                   │
│                    ┌─────────────────┐                          │
│                    │  ADD CREDIT     │                          │
│                    │  /wallet/add-   │                          │
│                    │  credit         │                          │
│                    └────────┬────────┘                          │
│                             │                                    │
│                             ▼                                    │
│         ┌───────────────────────────────────────┐               │
│         │           WALLET BALANCE              │               │
│         │         /wallet/balance               │               │
│         └───────────────────┬───────────────────┘               │
│                             │                                    │
│         ┌───────────────────┼───────────────────┐               │
│         ▼                   ▼                   ▼               │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐        │
│  │   History    │   │   Summary    │   │   Can Pay?   │        │
│  │   /wallet/   │   │   /wallet/   │   │   /wallet/   │        │
│  │   history    │   │   summary    │   │   can-pay    │        │
│  └──────────────┘   └──────────────┘   └──────┬───────┘        │
│                                               │                 │
│                                    ┌──────────┴──────────┐      │
│                                    ▼                     ▼      │
│                             ┌───────────┐         ┌───────────┐ │
│                             │ Sufficient│         │Insufficient│ │
│                             │  Balance  │         │  Balance   │ │
│                             └─────┬─────┘         └─────┬─────┘ │
│                                   │                     │       │
│                                   ▼                     ▼       │
│                            ┌───────────┐         ┌───────────┐  │
│                            │  PAY WITH │         │  SHOW     │  │
│                            │  WALLET   │         │  PAYMENT  │  │
│                            │ /wallet/  │         │  OPTIONS  │  │
│                            │   pay     │         └───────────┘  │
│                            └───────────┘                        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Recommended Implementation Steps

#### 1. Display Wallet Balance
Call `/api/wallet/balance` on:
- App launch / Home screen
- Wallet screen load
- After any transaction

```swift
// iOS Example
func fetchWalletBalance() {
    API.get("/api/wallet/balance") { response in
        self.balanceLabel.text = "\(response.data.currency_symbol) \(response.data.wallet_balance)"
    }
}
```

#### 2. Checkout Flow with Wallet Payment

```
1. User proceeds to checkout
2. Call /api/wallet/can-pay?order_amount=<total>
3. If can_pay_with_wallet == true:
   - Show "Pay with Wallet" option
   - Show remaining balance after payment
4. If can_pay_with_wallet == false:
   - Show wallet as partial payment option
   - Show "Use ₹X from wallet" + other payment for rest
5. User confirms wallet payment
6. Call /api/wallet/pay with order_id
7. Show success/failure
```

#### 3. Wallet Top-up Flow

```
1. User chooses to add money
2. Show amount input or preset amounts (100, 500, 1000)
3. Redirect to payment gateway (HyperPay, Apple Pay, etc.)
4. On payment success callback:
   - Call /api/wallet/add-credit with amount and payment reference
5. Show updated balance
```

#### 4. Transaction History UI

Display transactions with:
- Transaction type icon (↑ credit green, ↓ debit red)
- Amount with +/- prefix
- Source description
- Date/time
- Related order link (if available)

---

## Postman Collection

### Environment Variables
```json
{
    "base_url": "https://your-domain.com",
    "access_token": "<your_jwt_token>"
}
```

### Complete cURL Commands

```bash
# 1. Get Wallet Balance
curl --location '{{base_url}}/api/wallet/balance' \
--header 'Authorization: Bearer {{access_token}}'

# 2. Get Wallet History
curl --location '{{base_url}}/api/wallet/history?limit=50&offset=0' \
--header 'Authorization: Bearer {{access_token}}'

# 3. Get Wallet History (Credits Only)
curl --location '{{base_url}}/api/wallet/history?transaction_type=credit' \
--header 'Authorization: Bearer {{access_token}}'

# 4. Get Wallet History (Debits Only)
curl --location '{{base_url}}/api/wallet/history?transaction_type=debit' \
--header 'Authorization: Bearer {{access_token}}'

# 5. Get Wallet History (Date Range)
curl --location '{{base_url}}/api/wallet/history?date_from=2025-01-01&date_to=2025-12-31' \
--header 'Authorization: Bearer {{access_token}}'

# 6. Check Can Pay (by Amount)
curl --location '{{base_url}}/api/wallet/can-pay?order_amount=500' \
--header 'Authorization: Bearer {{access_token}}'

# 7. Check Can Pay (by Order ID)
curl --location '{{base_url}}/api/wallet/can-pay?order_id=123' \
--header 'Authorization: Bearer {{access_token}}'

# 8. Pay with Wallet (Full Payment)
curl --location '{{base_url}}/api/wallet/pay' \
--header 'Authorization: Bearer {{access_token}}' \
--header 'Content-Type: application/json' \
--data '{
    "order_id": 123,
    "confirm_order": true
}'

# 9. Pay with Wallet (Partial Payment)
curl --location '{{base_url}}/api/wallet/pay' \
--header 'Authorization: Bearer {{access_token}}' \
--header 'Content-Type: application/json' \
--data '{
    "order_id": 123,
    "amount": 200.00,
    "confirm_order": true
}'

# 10. Add Credit - Top-up
curl --location '{{base_url}}/api/wallet/add-credit' \
--header 'Authorization: Bearer {{access_token}}' \
--header 'Content-Type: application/json' \
--data '{
    "amount": 500.00,
    "source_type": "topup",
    "source_description": "Wallet top-up via credit card",
    "payment_reference": "PAY-12345"
}'

# 11. Add Credit - Refund
curl --location '{{base_url}}/api/wallet/add-credit' \
--header 'Authorization: Bearer {{access_token}}' \
--header 'Content-Type: application/json' \
--data '{
    "amount": 150.00,
    "source_type": "refund",
    "source_description": "Refund for cancelled order SO456"
}'

# 12. Add Credit - Cashback
curl --location '{{base_url}}/api/wallet/add-credit' \
--header 'Authorization: Bearer {{access_token}}' \
--header 'Content-Type: application/json' \
--data '{
    "amount": 25.00,
    "source_type": "cashback",
    "source_description": "5% cashback on order SO789"
}'

# 13. Get Wallet Summary
curl --location '{{base_url}}/api/wallet/summary' \
--header 'Authorization: Bearer {{access_token}}'
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-01-18 | Initial wallet API release |

---

## Support

For any issues or questions regarding the Wallet API, please contact the backend development team.

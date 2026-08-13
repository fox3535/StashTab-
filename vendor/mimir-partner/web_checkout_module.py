import os
import sys
from log_capture import setup_logger
setup_logger(is_main_process=False)
import math
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify
from database import SessionLocal, InventoryItem, Sale, SyncOutbox, OnlinePullQueue, SystemSettings, ShowPriceCapture, ShowPriceCaptureItem, PendingTrade
from logic import reconcile_databases
from core import CoreManager
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = '*'
    response.headers['Access-Control-Allow-Methods'] = '*'
    return response

# Premium, High-Contrast Bootstrap 5 Dark Mode Template for Full Mobile Management Suite
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="referrer" content="no-referrer">
    <title>The Card Shop - Mobile Management Suite</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.css">
    <style>
        .copy-field { cursor: pointer; transition: opacity 0.2s ease; }
        .copy-field:hover, .copy-field:active { opacity: 0.7; }
        body {
            background-color: #0f172a;
            color: #ffffff;
            font-family: 'Inter', system-ui, -apple-system, sans-serif;
            padding-bottom: 120px;
        }
        .navbar {
            background-color: #1e293b !important;
            border-bottom: 1px solid #334155;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }
        .nav-pills {
            background-color: #1e293b;
            border: 1px solid #334155;
            border-radius: 16px;
            padding: 8px;
        }
        .nav-pills .nav-link {
            color: #cbd5e1;
            border-radius: 12px;
            padding: 10px 16px;
            font-weight: 600;
            transition: all 0.2s ease-in-out;
        }
        .nav-pills .nav-link:hover {
            color: #ffffff;
            background-color: #334155;
        }
        .nav-pills .nav-link.active {
            background-color: #2563eb;
            color: #ffffff;
            box-shadow: 0 4px 12px rgba(37, 99, 235, 0.4);
        }
        .card {
            background-color: #1e293b;
            border: 1px solid #334155;
            border-radius: 16px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            color: #ffffff;
        }
        .card-header {
            border-bottom: 1px solid #334155;
            background-color: #1e293b;
            border-top-left-radius: 16px !important;
            border-top-right-radius: 16px !important;
        }
        .form-control, .form-select {
            background-color: #0f172a;
            border: 1px solid #475569;
            color: #ffffff;
            border-radius: 12px;
            padding: 12px 16px;
            font-weight: 500;
        }
        .form-control:focus, .form-select:focus {
            background-color: #0f172a;
            color: #ffffff;
            border-color: #3b82f6;
            box-shadow: 0 0 0 0.25rem rgba(59, 130, 246, 0.3);
        }
        .form-control::placeholder {
            color: #64748b;
        }
        .btn-primary {
            background-color: #2563eb;
            border-color: #2563eb;
            border-radius: 12px;
            padding: 12px 20px;
            font-weight: 600;
            color: #ffffff;
            box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3);
        }
        .btn-primary:hover {
            background-color: #1d4ed8;
            border-color: #1d4ed8;
            color: #ffffff;
        }
        .btn-success {
            background-color: #10b981;
            border-color: #10b981;
            border-radius: 12px;
            font-weight: 600;
            color: #ffffff;
            box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);
        }
        .btn-success:hover {
            background-color: #059669;
            border-color: #059669;
            color: #ffffff;
        }
        .btn-danger {
            background-color: #ef4444;
            border-color: #ef4444;
            border-radius: 12px;
            font-weight: 600;
            color: #ffffff;
        }
        .btn-warning {
            background-color: #f59e0b;
            border-color: #f59e0b;
            color: #ffffff;
            border-radius: 12px;
            font-weight: 600;
        }
        .btn-info {
            background-color: #06b6d4;
            border-color: #06b6d4;
            color: #ffffff;
            border-radius: 12px;
            font-weight: 600;
        }
        .status-pill {
            background-color: #334155;
            color: #ffffff;
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: 600;
            display: inline-block;
        }
        .modal-content {
            background-color: #1e293b;
            border: 1px solid #475569;
            color: #ffffff;
            border-radius: 20px;
        }
        .modal-header {
            border-bottom: 1px solid #334155;
        }
        .modal-footer {
            border-top: 1px solid #334155;
        }
        .table {
            color: #ffffff;
        }
        .table border-bottom {
            border-color: #334155;
        }
        .card-img-container {
            width: 90px;
            height: 125px;
            flex-shrink: 0;
            overflow: hidden;
            border-radius: 8px;
            border: 1px solid #475569;
            background-color: #0f172a;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .card-img-container img {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }
        #notificationContainer {
            position: fixed;
            top: 80px;
            left: 20px;
            right: 20px;
            margin: 0 auto;
            z-index: 999999;
            max-width: 500px;
            pointer-events: none;
        }
        .online-sale-toast {
            background-color: #ef4444;
            color: #ffffff;
            border-radius: 16px;
            box-shadow: 0 10px 35px rgba(239, 68, 68, 0.6);
            border: 2px solid #f87171;
            padding: 20px;
            margin-bottom: 15px;
            pointer-events: auto;
            animation: slideDown 0.3s ease-in-out;
        }
        @keyframes slideDown {
            from { transform: translateY(-100%); opacity: 0; }
            to { transform: translateY(0); opacity: 1; }
        }
    </style>
</head>
<body>
    <!-- MOBILE ON-SCREEN FLOATING DEBUG CONSOLE -->
    <div id="mobileDebugConsole" style="position: fixed; bottom: 0; left: 0; width: 100%; max-height: 250px; overflow-y: auto; background: rgba(0, 0, 0, 0.95); color: #00ff00; font-family: monospace; font-size: 12px; z-index: 9999999; padding: 10px; border-top: 2px solid #ffcc00; display: none;">
        <div style="display: flex; justify-content: space-between; border-bottom: 1px solid #555; padding-bottom: 5px; margin-bottom: 5px;">
            <span style="color: #ffcc00; font-weight: bold;">📱 Mobile Diagnostic Console</span>
            <button onclick="document.getElementById('mobileDebugConsole').style.display='none'" style="background: #333; color: #fff; border: none; padding: 2px 8px; cursor: pointer;">Close [X]</button>
        </div>
        <div id="debugLogArea"></div>
    </div>
    <script>
        (function() {
            function logToScreen(msg, color) {
                var area = document.getElementById('debugLogArea');
                if (area) {
                    var div = document.createElement('div');
                    div.style.color = color || '#00ff00';
                    div.style.borderBottom = '1px solid #222';
                    div.style.padding = '2px 0';
                    div.innerText = '[' + new Date().toLocaleTimeString() + '] ' + msg;
                    area.insertBefore(div, area.firstChild);
                }
            }
            var oldLog = console.log;
            console.log = function() { oldLog.apply(console, arguments); logToScreen(Array.from(arguments).join(' '), '#00ff00'); };
            var oldWarn = console.warn;
            console.warn = function() { oldWarn.apply(console, arguments); logToScreen('WARN: ' + Array.from(arguments).join(' '), '#ffcc00'); };
            var oldErr = console.error;
            console.error = function() { oldErr.apply(console, arguments); logToScreen('ERR: ' + Array.from(arguments).join(' '), '#ff3333'); };
            window.onerror = function(msg, url, line) {
                logToScreen('FATAL ERR: ' + msg + ' @ ' + url + ':' + line, '#ff0000');
                try {
                    fetch('/api/telemetry', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ error: msg, url: url, line: line })
                    });
                } catch(e){}
                return false;
            };
            window.addEventListener('unhandledrejection', function(event) {
                var errStr = event.reason ? event.reason.stack || event.reason : event;
                logToScreen('PROMISE ERR: ' + errStr, '#ff0000');
                try {
                    fetch('/api/telemetry', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ error: 'Promise Rejection: ' + errStr, url: window.location.href, line: 0 })
                    });
                } catch(e){}
            });
            logToScreen('Console initialized. App running on: ' + window.location.href, '#00ffff');
        })();
    </script>
    <!-- Real-time Online Sale Notification Area -->
    <div id="notificationContainer"></div>

    <nav class="navbar navbar-dark mb-4 py-3">
        <div class="container-fluid justify-content-between align-items-center px-4">
            <span class="navbar-brand mb-0 h1 fs-4 fw-bold d-flex align-items-center text-white">
                <i class="bi bi-suit-spade-fill me-2 text-primary fs-3"></i> Card Shop Mobile Suite
            </span>
            <span class="badge bg-success py-2 px-3 fs-6 rounded-pill"><i class="bi bi-broadcast me-1"></i> ONLINE</span>
        </div>
    </nav>

    <div class="container max-w-xl">
        <!-- Main Navigation Tabs -->
        <ul class="nav nav-pills nav-fill gap-2 mb-4 shadow-sm" id="pills-tab" role="tablist">
            <li class="nav-item" role="presentation">
                <button class="nav-link active" id="pills-checkout-tab" data-bs-toggle="pill" data-bs-target="#pills-checkout" type="button" role="tab"><i class="bi bi-cart-check-fill me-2"></i>Checkout</button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="pills-inventory-tab" data-bs-toggle="pill" data-bs-target="#pills-inventory" type="button" role="tab"><i class="bi bi-box-seam-fill me-2"></i>Inventory</button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link {% if sold_items %}bg-danger text-white fw-bold{% endif %}" id="pills-sold-tab" data-bs-toggle="pill" data-bs-target="#pills-sold" type="button" role="tab">
                    <i class="bi bi-bell-fill me-2"></i>Sold Online 
                    <span id="soldOnlineBadge" class="badge bg-warning text-dark ms-1 {% if not sold_items %}d-none{% endif %}">❗ <span id="soldOnlineCount">{{ sold_items|length }}</span></span>
                </button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="pills-history-tab" data-bs-toggle="pill" data-bs-target="#pills-history" type="button" role="tab"><i class="bi bi-clock-history me-2"></i>History</button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="pills-sync-tab" data-bs-toggle="pill" data-bs-target="#pills-sync" type="button" role="tab"><i class="bi bi-cloud-arrow-up-fill me-2"></i>Shopify Sync</button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="pills-updated-tab" data-bs-toggle="pill" data-bs-target="#pills-updated" type="button" role="tab"><i class="bi bi-currency-exchange me-2"></i>Updated Cards</button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="pills-settings-tab" data-bs-toggle="pill" data-bs-target="#pills-settings" type="button" role="tab"><i class="bi bi-gear-fill me-2"></i>Settings</button>
            </li>
        </ul>

        <!-- Tab Content -->
        <div class="tab-content" id="pills-tabContent">
            
            <!-- 1. LIVE CHECKOUT TAB -->
            <div class="tab-pane fade show active" id="pills-checkout" role="tabpanel">
                <div class="row g-4">
                    <!-- SCANNER BOX -->
                    <div class="col-12 col-lg-7 order-1">
                        <div class="card p-4 shadow-lg border-primary">
                            <h5 class="card-title fw-bold mb-3 text-white"><i class="bi bi-upc-scan me-2 text-primary fs-4"></i>Barcode Scanner & Search</h5>
                            <form id="searchForm" onsubmit="handlePosSearchSubmit(event)">
                                <div class="input-group mb-3">
                                    <select class="form-select text-white bg-dark border-secondary" id="checkoutGameFilter" onchange="filterCheckout(document.getElementById('checkoutSkuInput').value)" style="max-width: 140px;">
                                        <option value="All">All Games</option>
                                        <option value="Pokemon">Pokemon</option>
                                        <option value="One Piece">One Piece</option>
                                    </select>
                                    <input type="text" id="checkoutSkuInput" class="form-control form-control-lg text-white bg-dark border-secondary" placeholder="🔍 Scan barcode or type SKU / Name, then press Enter..." autocomplete="off" autofocus oninput="filterCheckout(this.value)">
                                    <button class="btn btn-primary px-4 fw-bold" type="submit"><i class="bi bi-plus-circle-fill me-2"></i>Add / Search</button>
                                </div>
                            </form>
                            <div id="checkoutAlertArea"></div>
                        </div>
                    </div>

                    <!-- CART & CASH SETTLEMENT PANEL (Sticky on desktop, immediately below scanner on mobile) -->
                    <div class="col-12 col-lg-5 order-2">
                        <div class="card p-4 shadow-lg border-success sticky-top" style="background-color: #0f172a; top: 20px; z-index: 1020;">
                            <h5 class="fw-bold mb-3 text-white d-flex justify-content-between align-items-center">
                                <span><i class="bi bi-cart-check-fill me-2 text-success fs-4"></i>Current Cart</span>
                                <span id="posCartTotalLbl" class="badge bg-success p-2 fs-6">Cart Total: $0.00</span>
                            </h5>
                            <div id="posCartTableArea" class="mb-4">
                                <div class="alert alert-secondary text-center text-white py-3 my-2 fw-bold">🛒 Cart is currently empty. Scan cards or add trades above.</div>
                            </div>
                            <div class="d-flex gap-2 mb-4">
                                <button class="btn btn-warning flex-grow-1 py-2 fw-bold text-dark" onclick="openPlaceholderTradeModal()"><i class="bi bi-credit-card-fill me-2"></i>Add Placeholder Trade</button>
                                <button class="btn btn-outline-secondary py-2 fw-bold text-white" onclick="clearPosCart()"><i class="bi bi-trash-fill me-1"></i>Clear</button>
                            </div>
                            <hr class="border-secondary mb-4">
                            <h5 class="fw-bold mb-3 text-white"><i class="bi bi-cash-stack me-2 text-primary fs-4"></i>Cash Settlement</h5>
                            <div class="mb-3">
                                <label class="form-label text-white fw-bold small">Store Cash Added ($):</label>
                                <input type="number" step="0.01" class="form-control text-white bg-dark border-secondary form-control-lg" id="posStoreCash" placeholder="0.00" onkeyup="updatePosTotals()" onchange="updatePosTotals()">
                            </div>
                            <div class="mb-3">
                                <label class="form-label text-white fw-bold small">Customer Cash Added ($):</label>
                                <input type="number" step="0.01" class="form-control text-white bg-dark border-secondary form-control-lg" id="posCustCash" placeholder="0.00" onkeyup="updatePosTotals()" onchange="updatePosTotals()">
                            </div>
                            <div class="mb-3">
                                <label class="form-label text-danger fw-bold small">Discount Applied ($):</label>
                                <input type="number" step="0.01" class="form-control text-danger bg-dark border-danger form-control-lg" id="posDiscount" placeholder="0.00" onkeyup="updatePosTotals()" onchange="updatePosTotals()">
                            </div>
                            <div class="mb-4">
                                <label class="form-label text-warning fw-bold small">Cash Tendered ($):</label>
                                <input type="number" step="0.01" class="form-control text-warning bg-dark border-warning form-control-lg" id="posTendered" placeholder="0.00" onkeyup="updatePosTotals()" onchange="updatePosTotals()">
                            </div>
                            <div class="p-3 bg-dark rounded border border-secondary mb-4 text-center">
                                <h3 id="posNetDueLbl" class="fw-bold text-success mb-2 fs-3">NET DUE: $0.00</h3>
                                <h5 id="posChangeDueLbl" class="fw-bold text-warning mb-0">Change Due: $0.00</h5>
                            </div>
                            <div class="d-flex flex-column gap-3">
                                <button class="btn btn-success btn-lg w-100 py-3 fw-bold shadow-lg" onclick="processPosCheckout('POS Cash')">
                                    <i class="bi bi-check-circle-fill me-2 fs-5"></i> ✅ Checkout — Cash
                                </button>
                                <button class="btn btn-info btn-lg w-100 py-3 fw-bold shadow-lg text-white" onclick="processPosCheckout('POS Trade')">
                                    <i class="bi bi-arrow-repeat me-2 fs-5"></i> 🔄 Checkout — Trade
                                </button>
                            </div>
                        </div>
                    </div>

                    <!-- CATALOG / SEARCH RESULTS (Below cart on mobile, below scanner on desktop) -->
                    <div class="col-12 col-lg-7 order-3">
                        <div id="checkoutResultsArea" class="d-flex flex-column gap-3">
                            {% for item in items %}
                                <div class="card p-4 card-hover mb-3 checkout-card-item" id="checkout-item-{{ item.sku }}" data-sku="{{ item.sku }}" data-name="{{ item.name|escape }}" data-set="{{ item.set_name|escape or 'Unknown Set' }}" data-price="{{ item.sticker_price or item.price or 0.0 }}" data-stock="{{ item.stock or 0 }}" data-game="{{ item.game|escape }}" data-search="{{ item.sku }} {{ item.name|escape }} {{ item.set_name|escape }}">
                                    <div class="d-flex justify-content-between align-items-center mb-3">
                                        <div class="flex-grow-1">
                                            <h5 class="fw-bold mb-1 text-white">
                                                {% if item.game == 'One Piece' %}
                                                    {% if settings.one_piece_icon_url %}<img src="{{ settings.one_piece_icon_url }}" height="24" class="me-1">{% else %}🏴‍☠️{% endif %}
                                                {% else %}
                                                    {% if settings.pokemon_icon_url %}<img src="{{ settings.pokemon_icon_url }}" height="24" class="me-1">{% else %}⚡{% endif %}
                                                {% endif %}
                                                {{ item.name }}
                                            </h5>
                                            <div class="text-secondary small mb-2">{{ item.set_name or 'Unknown Set' }} | {{ item.sequence_number or '' }} | {{ item.condition or 'NM' }}</div>
                                            <span class="status-pill text-info">Stock: {{ item.stock or 0 }}</span>
                                        </div>
                                        <div class="text-end">
                                            <h3 class="fw-bold text-success mb-1">${{ "%.2f"|format(item.sticker_price or item.price or 0.0) }}</h3>
                                            <div class="text-secondary small">SKU: {{ item.sku }}</div>
                                        </div>
                                    </div>
                                    <button class="btn btn-primary btn-lg w-100 py-3 mt-2 fw-bold" onclick="addSkuToCart('{{ item.sku }}')">
                                        <i class="bi bi-cart-plus-fill me-2 fs-5"></i> ➕ Add to Cart
                                    </button>
                                </div>
                            {% else %}
                                <div class="alert alert-info text-white text-center p-4 fw-bold">No cards found in database.</div>
                            {% endfor %}
                        </div>
                    </div>
                </div>
            </div>

            <!-- 2. INVENTORY MANAGER TAB -->
            <div class="tab-pane fade" id="pills-inventory" role="tabpanel">
                <div class="card mb-4">
                    <div class="card-header p-4 d-flex justify-content-between align-items-center flex-wrap gap-3">
                        <h5 class="fw-bold mb-0 text-white"><i class="bi bi-boxes me-2 text-primary"></i>Database Inventory Manager</h5>
                        <!-- Inventory Action Buttons Submenu -->
                        <div class="d-flex gap-2 flex-wrap">
                            <button class="btn btn-sm btn-info fw-bold" onclick="captureShowPrices()"><i class="bi bi-camera-fill me-1"></i>Capture Show Prices</button>
                            <button class="btn btn-sm btn-warning fw-bold" onclick="verifyShopify()"><i class="bi bi-shield-check me-1"></i>Verify Shopify Status</button>
                            <label class="btn btn-sm btn-success fw-bold mb-0" style="cursor: pointer;">
                                <input type="file" id="reconCsvInput" accept=".csv" style="display: none;" onchange="handleReconUpload(event)">
                                <i class="bi bi-arrow-repeat me-1"></i>Run Recon
                            </label>
                        </div>
                    </div>
                    <div class="card-body p-4">
                        <div class="input-group mb-3">
                            <select class="form-select text-white bg-dark border-secondary" id="inventoryGameFilter" onchange="filterInventory(document.getElementById('inventorySearchInput').value)" style="max-width: 140px;">
                                <option value="All">All Games</option>
                                <option value="Pokemon">Pokemon</option>
                                <option value="One Piece">One Piece</option>
                            </select>
                            <input type="text" id="inventorySearchInput" class="form-control text-white" placeholder="Search by Card Name, Set, or SKU..." oninput="filterInventory(this.value)">
                            <button class="btn btn-primary px-4" onclick="filterInventory(document.getElementById('inventorySearchInput').value)"><i class="bi bi-search"></i></button>
                        </div>
                        <div id="inventoryAlertArea"></div>
                    </div>
                </div>
                <div id="inventoryResultsArea" class="d-flex flex-column gap-3">
                    {% for item in items %}
                        <div class="card p-4 mb-3 inventory-card-item" id="inv-item-{{ item.sku }}" data-game="{{ item.game|escape }}" data-search="{{ item.sku }} {{ item.name|escape }} {{ item.set_name|escape }}">
                            <div class="d-flex justify-content-between align-items-start mb-3">
                                <div class="flex-grow-1">
                                    <h5 class="fw-bold mb-1 text-white" id="inv-name-{{ item.sku }}">
                                        {% if item.game == 'One Piece' %}
                                            {% if settings.one_piece_icon_url %}<img src="{{ settings.one_piece_icon_url }}" height="24" class="me-1">{% else %}🏴‍☠️{% endif %}
                                        {% else %}
                                            {% if settings.pokemon_icon_url %}<img src="{{ settings.pokemon_icon_url }}" height="24" class="me-1">{% else %}⚡{% endif %}
                                        {% endif %}
                                        {{ item.name }}
                                    </h5>
                                    <div class="text-secondary small mb-2">
                                        {{ item.set_name or 'Unknown Set' }} | {{ item.sequence_number or '' }} | {{ item.condition or 'NM' }}
                                    </div>
                                    <div class="d-flex flex-wrap gap-2 mb-3">
                                        <span class="status-pill text-warning">Market: ${{ "%.2f"|format(item.price or 0.0) }}</span>
                                        <span class="status-pill text-success">Sticker: ${{ "%.2f"|format(item.sticker_price or item.price or 0.0) }}</span>
                                        <span class="status-pill text-primary">Paid: ${{ "%.2f"|format(item.cost or 0.0) }}</span>
                                        <span class="status-pill text-info">Stock: {{ item.stock or 0 }}</span>
                                    </div>
                                </div>
                                <div class="text-end">
                                    <button id="edit-btn-{{ item.sku }}" class="btn btn-primary px-4 py-2 fw-bold mb-2 w-100" onclick="toggleInlineEdit('{{ item.sku }}', {{ item.price or 0.0 }}, {{ item.shop_listing_price or item.price or 0.0 }}, {{ item.sticker_price or 0.0 }}, {{ item.stock or 0 }})">
                                        <i class="bi bi-pencil-square me-2"></i> Edit DB
                                    </button>
                                    <div class="text-secondary small mt-1 fw-bold">
                                        SKU: {{ item.sku }}
                                    </div>
                                </div>
                            </div>
                            <!-- Inline Edit Form -->
                            <div id="inline-edit-{{ item.sku }}" class="d-none bg-dark p-4 rounded mt-3 border border-primary shadow-lg">
                                <h6 class="fw-bold text-info mb-3"><i class="bi bi-tools me-2"></i>Inline Quick Edit</h6>
                                <div class="mb-3">
                                    <label class="form-label text-white fw-bold small">Price Paid ($)</label>
                                    <input type="number" step="0.01" class="form-control text-secondary bg-black border-secondary" value="{{ item.cost or 0.0 }}" readonly>
                                </div>
                                <div class="mb-3">
                                    <label class="form-label text-white fw-bold small">Market Price ($)</label>
                                    <input type="number" step="0.01" class="form-control text-white bg-black border-secondary" id="inline-price-{{ item.sku }}" value="{{ item.price or 0.0 }}">
                                </div>
                                <div class="mb-3">
                                    <label class="form-label text-white fw-bold small">Shopify Listing Price ($)</label>
                                    <input type="number" step="0.01" class="form-control text-white bg-black border-secondary" id="inline-shop-price-{{ item.sku }}" value="{{ item.shop_listing_price or item.price or 0.0 }}">
                                </div>
                                <div class="mb-3">
                                    <label class="form-label text-white fw-bold small">Sticker Price ($)</label>
                                    <input type="number" step="0.01" class="form-control text-white bg-black border-secondary" id="inline-sticker-price-{{ item.sku }}" value="{{ item.sticker_price or 0.0 }}">
                                </div>
                                <div class="mb-3">
                                    <label class="form-label text-white fw-bold small">Stock Quantity</label>
                                    <input type="number" class="form-control text-white bg-black border-secondary" id="inline-stock-{{ item.sku }}" value="{{ item.stock or 0 }}">
                                </div>
                                <div class="d-flex gap-2 justify-content-end mt-4">
                                    <button class="btn btn-outline-light px-4 py-2 fw-bold" onclick="toggleInlineEdit('{{ item.sku }}')">Cancel</button>
                                    <button class="btn btn-success px-5 py-2 fw-bold" onclick="saveInlineEdit('{{ item.sku }}')"><i class="bi bi-floppy-fill me-2"></i>Save</button>
                                </div>
                            </div>
                        </div>
                    {% else %}
                        <div class="alert alert-info text-white text-center p-4 fw-bold">No inventory items found in database.</div>
                    {% endfor %}
                </div>
            </div>

            <!-- 3. SOLD ONLINE TAB -->
            <div class="tab-pane fade" id="pills-sold" role="tabpanel">
                <div class="card p-4 mb-4">
                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <h5 class="card-title fw-bold mb-0 text-white"><i class="bi bi-bell-fill me-2 text-danger"></i>Sold Online (Convention Pull List)</h5>
                        <button type="button" class="btn btn-sm btn-outline-light" onclick="window.location.reload()"><i class="bi bi-arrow-clockwise me-1"></i>Refresh</button>
                    </div>
                    <div id="soldAlertArea"></div>
                    <div id="soldOnlineArea" class="d-flex flex-column gap-3">
                        {% for item in sold_items %}
                            <div class="card p-4 border-danger" id="sold-card-{{ item.id }}">
                                <div class="d-flex justify-content-between align-items-center">
                                    <div>
                                        <h5 class="fw-bold mb-1 text-white">{{ item.card_name }}</h5>
                                        <div class="text-secondary small mb-2">{{ item.set_name }} | Condition: {{ item.condition }}</div>
                                        <span class="badge bg-primary p-2 fs-6">Order: {{ item.order_id }}</span>
                                    </div>
                                    <div>
                                        <button type="button" class="btn btn-success px-4 py-2 fw-bold" onclick="markItemPulled({{ item.id }})">✅ Mark as Pulled</button>
                                    </div>
                                </div>
                            </div>
                        {% else %}
                            <div class="alert alert-info text-white text-center p-4 fw-bold">No pending online convention pulls.</div>
                        {% endfor %}
                    </div>
                </div>
            </div>

            <!-- 4. TRANSACTION HISTORY TAB -->
            <div class="tab-pane fade" id="pills-history" role="tabpanel">
                <div class="card p-4 mb-4">
                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <h5 class="card-title fw-bold mb-0 text-white"><i class="bi bi-receipt-cutoff me-2 text-primary"></i>Recent Sales & Transactions</h5>
                        <button class="btn btn-sm btn-outline-light" onclick="window.location.reload()"><i class="bi bi-arrow-clockwise me-1"></i>Refresh</button>
                    </div>
                    <div id="historyTableArea" class="table-responsive">
                        {% if sales %}
                            <table class="table table-dark table-hover align-middle mb-0">
                                <thead>
                                    <tr>
                                        <th>Timestamp</th>
                                        <th>Type</th>
                                        <th>Item Name</th>
                                        <th>SKU</th>
                                        <th>Amount</th>
                                        <th>Profit</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {% for s in sales %}
                                        <tr>
                                            <td class="text-secondary small">{{ s.timestamp }}</td>
                                            <td class="fw-bold text-success">{{ s.transaction_type }}</td>
                                            <td class="fw-bold text-white">{{ s.item_name }}</td>
                                            <td class="font-monospace text-secondary">{{ s.sku }}</td>
                                            <td class="fw-bold text-white">${{ "%.2f"|format(s.sold_price or 0.0) }}</td>
                                            <td class="fw-bold text-success">${{ "%.2f"|format(s.profit or 0.0) }}</td>
                                        </tr>
                                    {% endfor %}
                                </tbody>
                            </table>
                        {% else %}
                            <div class="alert alert-info text-white text-center p-4 fw-bold">No historical transactions found.</div>
                        {% endif %}
                    </div>
                </div>
            </div>

            <!-- 5. SHOPIFY SYNC BOX TAB -->
            <div class="tab-pane fade" id="pills-sync" role="tabpanel">
                <div class="card p-4 mb-4">
                    <div class="d-flex justify-content-between align-items-center mb-4 flex-wrap gap-2">
                        <h5 class="card-title fw-bold mb-0 text-white"><i class="bi bi-cloud-check-fill me-2 text-primary"></i>Shopify Sync Overview</h5>
                        <div class="d-flex gap-2">
                            <button class="btn btn-sm btn-warning fw-bold" onclick="clearSync('pending')"><i class="bi bi-trash-fill me-1"></i>Clear Pending</button>
                            <button class="btn btn-sm btn-danger fw-bold" onclick="clearSync('synced')"><i class="bi bi-stars me-1"></i>Clear Completed</button>
                            <button class="btn btn-sm btn-outline-light" onclick="window.location.reload()"><i class="bi bi-arrow-clockwise"></i></button>
                        </div>
                    </div>
                    <div id="syncTableArea" class="table-responsive">
                        {% if sync_items %}
                            <table class="table table-dark table-hover align-middle mb-0">
                                <thead>
                                    <tr>
                                        <th>Timestamp</th>
                                        <th>Action</th>
                                        <th>SKU</th>
                                        <th>Quantity Change</th>
                                        <th>Status</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {% for item in sync_items %}
                                        <tr>
                                            <td class="text-secondary small">{{ item.timestamp }}</td>
                                            <td class="fw-bold text-uppercase text-warning">{{ item.action_type }}</td>
                                            <td class="font-monospace fw-bold text-white">{{ item.sku }}</td>
                                            <td class="fw-bold text-white">{{ item.quantity_change }}</td>
                                            <td class="fw-bold text-warning">{{ item.sync_status }}</td>
                                        </tr>
                                    {% endfor %}
                                </tbody>
                            </table>
                        {% else %}
                            <div class="alert alert-info text-white text-center p-4 fw-bold">No items pending sync or recently synced.</div>
                        {% endif %}
                    </div>
                </div>
            </div>

            <!-- 5b. UPDATED CARDS TAB -->
            <div class="tab-pane fade" id="pills-updated" role="tabpanel">
                <div class="card p-4 mb-4">
                    <div class="d-flex justify-content-between align-items-center mb-4 flex-wrap gap-2">
        window.addSkuToCart = addSkuToCart;
        window.removeCartItem = removeCartItem;
        window.openPlaceholderTradeModal = openPlaceholderTradeModal;
        window.confirmAddPlaceholderTrade = confirmAddPlaceholderTrade;
        window.removePlaceholderTrade = removePlaceholderTrade;
        window.updateTradeRate = updateTradeRate;
        window.clearPosCart = clearPosCart;
        window.processPosCheckout = processPosCheckout;
        window.captureShowPrices = captureShowPrices;
        window.verifyShopify = verifyShopify;
        window.runRecon = runRecon;
        window.handleReconUpload = handleReconUpload;
        window.clearSync = clearSync;
        window.saveSettings = saveSettings;
        window.approveSingleUpdate = approveSingleUpdate;
        window.rejectSingleUpdate = rejectSingleUpdate;
        window.approveUnder5 = approveUnder5;
        window.forceSyncShopify = forceSyncShopify;
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    session = SessionLocal()
    try:
        items = session.query(InventoryItem).all()

        pull_queue_items = session.query(OnlinePullQueue).filter_by(status='pending_pull').all()
        sold_items = []
        for item in pull_queue_items:
            inv = session.query(InventoryItem).filter_by(sku=item.sku).first()
            sold_items.append({
                "id": item.id,
                "sku": item.sku,
                "order_id": item.order_id,
                "card_name": inv.name if inv else "Unknown Card",
                "set_name": inv.set_name if inv else "Unknown Set",
                "condition": inv.condition if inv else "NM"
            })
            
        sales = session.query(Sale).order_by(Sale.timestamp.desc()).limit(20).all()
        sync_items = session.query(SyncOutbox).order_by(SyncOutbox.timestamp.desc()).limit(20).all()
        settings = session.query(SystemSettings).first()
        if not settings:
            settings = SystemSettings(price_fluctuation_threshold=0.10, resticker_threshold=2.00, buy_percentage=0.70, trade_percentage=0.80)
            session.add(settings)
            session.commit()
        
        updated_cards = session.query(InventoryItem).filter(InventoryItem.needs_update == True, InventoryItem.stock > 0).all()
        rendered = render_template_string(HTML_TEMPLATE, items=items, sold_items=sold_items, sales=sales, sync_items=sync_items, settings=settings, updated_cards=updated_cards)
        session.close()
        return rendered
    except Exception as e:
        session.close()
        return f"Database Error: {e}"

def get_item_image_url(item):
    if getattr(item, 'custom_image_url', None):
        return item.custom_image_url
    if getattr(item, 'image_url', None):
        url = item.image_url.replace('\\', '/')
        if not url.startswith('/') and not url.startswith('http'):
            url = '/' + url
        return url
    thumb_path_png = f"static/scraped_thumbnails/{item.sku}.png"
    if os.path.exists(thumb_path_png):
        return f"/{thumb_path_png}"
    thumb_path_jpg = f"static/scraped_thumbnails/{item.sku}.jpg"
    if os.path.exists(thumb_path_jpg):
        return f"/{thumb_path_jpg}"
    return "https://placehold.co/100x140/1e293b/ffffff?text=No+Image"

def safe_calculate_shop_price(market_price: float, session) -> float:
    try:
        settings = session.query(SystemSettings).first()
        if not settings:
            return market_price
            
        base_price = market_price
        if settings.markup_type == "Percentage (%)":
            base_price = base_price * (1 + (settings.markup_value / 100))
        elif settings.markup_type == "Flat Amount ($)":
            base_price = base_price + settings.markup_value
            
        if settings.rounding_rule == "Round to nearest .99":
            return math.ceil(base_price) - 0.01
        elif settings.rounding_rule == "Round to nearest .50":
            return round(base_price * 2) / 2
        else:
            return round(base_price, 2)
    except:
        return market_price

# --- TELEMETRY API ---
@app.route('/api/telemetry', methods=['POST'])
def api_telemetry():
    try:
        data = request.get_json(silent=True) or request.form or {}
        err_msg = data.get('error', 'Unknown Error')
        url = data.get('url', '')
        line = data.get('line', '')
        print(f"\n{'='*60}\n🚨 [MOBILE BROWSER CRASH TELEMETRY] 🚨\nError: {err_msg}\nURL: {url}\nLine: {line}\n{'='*60}\n", flush=True)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# --- 1. CHECKOUT API ---
@app.route('/api/search', methods=['GET'])
def api_search():
    session = SessionLocal()
    try:
        query = request.args.get('q', '').strip()
        if not query:
            items = session.query(InventoryItem).limit(20).all()
        else:
            items = session.query(InventoryItem).filter(
                (InventoryItem.sku == query) | (InventoryItem.name.ilike(f"%{query}%"))
            ).limit(20).all()

        results = []
        for item in items:
                sp = getattr(item, 'sticker_price', None)
                if sp is None:
                    sp = float(item.price if item.price is not None else 0.0)
                
                results.append({
                    "sku": str(item.sku or ''),
                    "name": str(item.name or 'Unknown Card'),
                    "set_name": str(item.set_name or 'Unknown Set'),
                    "sequence_number": str(item.sequence_number or ''),
                    "condition": str(item.condition or 'NM'),
                    "stock": int(item.stock if item.stock is not None else 0),
                    "price": float(sp),
                    "image_url": get_item_image_url(item)
                })

        session.close()
        return jsonify({"items": results})
    except Exception as e:
        session.close()
        return jsonify({"error": str(e)}), 500

@app.route('/api/checkout', methods=['GET', 'POST'])
def api_checkout():
    session = SessionLocal()
    try:
        data = request.get_json(silent=True) or request.form or request.args or {}
        sku = data.get('sku')
        if not sku:
            session.close()
            return jsonify({"success": False, "message": "SKU is required."}), 400

        item = session.query(InventoryItem).filter(InventoryItem.sku == sku, InventoryItem.stock > 0).first()
        if not item:
            session.close()
            return jsonify({"success": False, "message": "Item out of stock or not found."}), 404

        item.stock -= 1
        
        # Auto-pause if available stock reaches 0
        available_qty = item.stock - (getattr(item, 'paused_stock', 0) or 0)
        if available_qty <= 0 and getattr(item, 'sync_status', '') == 'active':
            item.sync_status = 'paused'

        sp = getattr(item, 'sticker_price', None)
        if sp is None:
            sp = float(item.price if item.price is not None else 0.0)
        sale_price = float(sp)
        cost_basis = float(item.cost if item.cost is not None else 0.0)
        new_sale = Sale(
            item_name=item.name,
            sku=item.sku,
            sold_price=sale_price,
            profit=sale_price - cost_basis,
            transaction_type="Mobile POS",
            trade_in_value=0.0,
            net_revenue=sale_price
        )
        session.add(new_sale)

        outbox = SyncOutbox(
            action_type='stock_update',
            sku=item.sku,
            quantity_change=-1,
            new_price=0.0
        )
        session.add(outbox)

        session.commit()
        remaining = item.stock
        session.close()
        
        try:
            core = CoreManager(None, None, None, start_poller=False)
            core._process_sync_outbox()
        except Exception as e:
            print(f"Checkout sync push error: {e}")

        return jsonify({"success": True, "remaining_stock": remaining})
    except Exception as e:
        session.rollback()
        session.close()
        return jsonify({"success": False, "message": f"Server error: {e}"}), 500

@app.route('/api/placeholder_trade/add', methods=['GET', 'POST'])
def api_placeholder_trade_add():
    session = SessionLocal()
    try:
        data = request.get_json(silent=True) or request.form or request.args or {}
        mkt_val = float(data.get('market_value', 0.0))
        cash_paid = float(data.get('cash_paid', 0.0))

        trade = session.query(PendingTrade).filter_by(status='pending').first()
        if trade:
            trade.total_market_value += mkt_val
            trade.total_cash_paid += cash_paid
        else:
            trade = PendingTrade(total_market_value=mkt_val, total_cash_paid=cash_paid)
            session.add(trade)
        session.commit()
        trade_id = trade.id
        session.close()
        return jsonify({"success": True, "pending_trade_id": trade_id})
    except Exception as e:
        session.rollback()
        session.close()
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/placeholder_trade/remove', methods=['GET', 'POST'])
def api_placeholder_trade_remove():
    session = SessionLocal()
    try:
        data = request.get_json(silent=True) or request.form or request.args or {}
        pt_id = data.get('pending_trade_id')
        mkt_val = float(data.get('market_value', 0.0))
        cash_paid = float(data.get('cash_paid', 0.0))
        if pt_id:
            trade = session.query(PendingTrade).get(pt_id)
            if trade:
                trade.total_market_value = max(0.0, trade.total_market_value - mkt_val)
                trade.total_cash_paid = max(0.0, trade.total_cash_paid - cash_paid)
                if trade.total_market_value == 0 and trade.total_cash_paid == 0:
                    session.delete(trade)
                session.commit()
        session.close()
        return jsonify({"success": True})
    except Exception as e:
        session.rollback()
        session.close()
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/checkout_cart', methods=['GET', 'POST'])
def api_checkout_cart():
    session = SessionLocal()
    try:
        data = request.get_json(silent=True) or request.form or request.args or {}
        transaction_type = data.get('transaction_type', 'POS Cash')
        cart_items = data.get('cart_items', [])
        placeholder_trades = data.get('placeholder_trades', [])
        placeholder_cost = float(data.get('placeholder_cost', 0.0))
        net_due = float(data.get('net_due', 0.0))
        discount = float(data.get('discount', 0.0))

        if placeholder_trades:
            trade = session.query(PendingTrade).filter_by(status='pending').first()
            if not trade:
                trade = PendingTrade(total_market_value=0.0, total_cash_paid=0.0)
                session.add(trade)
            for pt in placeholder_trades:
                trade.total_market_value += float(pt.get('market_value', 0.0))
                trade.total_cash_paid += (float(pt.get('market_value', 0.0)) * float(pt.get('rate', 0.0)))

        cart_total_price = sum(float(item.get('price')) if isinstance(item, dict) and item.get('price') is not None else 0.0 for item in cart_items)

        for item_data in cart_items:
            sku = item_data.get('sku') if isinstance(item_data, dict) else item_data
            sale_price_override = float(item_data.get('price')) if isinstance(item_data, dict) and item_data.get('price') is not None else None
            
            item = session.query(InventoryItem).filter(InventoryItem.sku == sku, InventoryItem.stock > 0).first()
            if item:
                item.stock -= 1
            
            # Auto-pause if available stock reaches 0
            available_qty = item.stock - (getattr(item, 'paused_stock', 0) or 0)
            if available_qty <= 0 and getattr(item, 'sync_status', '') == 'active':
                item.sync_status = 'paused'
                if sale_price_override is not None:
                    sale_price = sale_price_override
                else:
                    sp = getattr(item, 'sticker_price', None)
                    if sp is None:
                        sp = float(item.price if item.price is not None else 0.0)
                    sale_price = float(sp)
                
                if cart_total_price > 0 and discount > 0:
                    item_discount = (sale_price / cart_total_price) * discount
                    sale_price = max(0.0, sale_price - item_discount)

                cost_basis = float(item.cost if item.cost is not None else 0.0)
                new_sale = Sale(
                    item_name=item.name,
                    sku=item.sku,
                    sold_price=sale_price,
                    profit=sale_price - cost_basis,
                    transaction_type=transaction_type,
                    trade_in_value=placeholder_cost,
                    net_revenue=net_due
                )
                session.add(new_sale)
                session.add(SyncOutbox(
                    action_type='stock_update',
                    sku=item.sku,
                    quantity_change=-1,
                    new_price=0.0
                ))

        session.commit()
        session.close()

        # Trigger background Shopify sync
        def _delayed_sync():
            import time as _time
            _time.sleep(3)
            try:
                from core import CoreManager
                core = CoreManager(None, None, None, start_poller=False)
                core._process_sync_outbox()
            except:
                pass
        import threading
        threading.Thread(target=_delayed_sync, daemon=True).start()

        return jsonify({"success": True, "message": f"{transaction_type} complete!"})
    except Exception as e:
        session.rollback()
        session.close()
        return jsonify({"success": False, "message": str(e)}), 500

# --- 2. INVENTORY API ---
@app.route('/api/generate_label/<sku>', methods=['GET'])
def api_generate_label(sku):
    session = SessionLocal()
    try:
        format_type = request.args.get('format', 'QR')
        item = session.query(InventoryItem).filter(InventoryItem.sku == sku).first()
        price_val = float(item.price if item and item.price is not None else 0.0)
        session.close()

        from logic import generate_item_barcode
        generate_item_barcode(sku, market_price=price_val, format=format_type)
        
        import time as _time
        return jsonify({"success": True, "image_url": f"/static/barcodes/{sku}.png?_cb={int(_time.time())}"})
    except Exception as e:
        session.close()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/inventory', methods=['GET'])
def api_inventory():
    session = SessionLocal()
    try:
        query = request.args.get('q', '').strip()
        base_query = session.query(InventoryItem)
        if query:
            base_query = base_query.filter(
                (InventoryItem.sku == query) | 
                (InventoryItem.name.ilike(f"%{query}%")) | 
                (InventoryItem.set_name.ilike(f"%{query}%"))
            )
        items = base_query.limit(50).all()

        results = []
        for item in items:
            try:
                price_val = float(item.price) if item.price is not None else 0.0
            except:
                price_val = 0.0
                
            try:
                shop_price_val = float(item.shop_listing_price) if getattr(item, 'shop_listing_price', None) is not None else safe_calculate_shop_price(price_val, session)
                if shop_price_val is None:
                    shop_price_val = price_val
            except:
                shop_price_val = price_val
                
            try:
                sticker_val = float(item.sticker_price) if getattr(item, 'sticker_price', None) is not None else 0.0
            except:
                sticker_val = 0.0

            results.append({
                "sku": str(item.sku or ''),
                "name": str(item.name or 'Unknown Card'),
                "set_name": str(item.set_name or 'Unknown Set'),
                "sequence_number": str(item.sequence_number or ''),
                "condition": str(item.condition or 'NM'),
                "stock": int(item.stock if item.stock is not None else 0),
                "price": float(price_val),
                "shop_listing_price": float(shop_price_val),
                "sticker_price": float(sticker_val),
                "image_url": get_item_image_url(item)
            })

        session.close()
        return jsonify({"success": True, "items": results})
    except Exception as e:
        session.close()
        return jsonify({"error": str(e)}), 500

@app.route('/api/inventory/update', methods=['GET', 'POST'])
def api_inventory_update():
    session = SessionLocal()
    try:
        data = request.get_json(silent=True) or request.form or request.args or {}
        sku = data.get('sku')
        if not sku:
            session.close()
            return jsonify({"success": False, "message": "SKU is required."}), 400

        item = session.query(InventoryItem).filter(InventoryItem.sku == sku).first()
        if not item:
            session.close()
            return jsonify({"success": False, "message": "Item not found."}), 404

        old_stock = item.stock
        old_price = item.price

        new_price = float(data.get('price', item.price))
        if abs(new_price - (old_price or 0.0)) > 0.001:
            new_shop_price = safe_calculate_shop_price(new_price, session)
        else:
            new_shop_price = float(data.get('shop_listing_price', getattr(item, 'shop_listing_price', None) or safe_calculate_shop_price(new_price, session)))
            
        new_sticker_price = float(data.get('sticker_price', item.sticker_price))
        new_stock = int(data.get('stock', item.stock))

        item.price = new_price
        item.shop_listing_price = new_shop_price
        item.sticker_price = new_sticker_price
        item.stock = new_stock

        if new_stock != old_stock:
            session.add(SyncOutbox(
                action_type='stock_update',
                sku=item.sku,
                quantity_change=new_stock - old_stock,
                new_price=new_shop_price
            ))
        if new_price != old_price:
            session.add(SyncOutbox(
                action_type='price_update',
                sku=item.sku,
                quantity_change=0,
                new_price=new_shop_price
            ))

        session.commit()
        session.close()
        
        try:
            core = CoreManager(None, None, None, start_poller=False)
            core._process_sync_outbox()
        except Exception as e:
            print(f"Update sync push error: {e}")

        return jsonify({"success": True})
    except Exception as e:
        session.rollback()
        session.close()
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/inventory/capture_show_prices', methods=['POST'])
def api_capture_show_prices():
    session = SessionLocal()
    try:
        data = request.get_json()
        capture_name = data.get('name')
        if not capture_name:
            capture_name = f"Show Capture - {datetime.now().strftime('%b %d, %Y')}"

        items = session.query(InventoryItem).filter(InventoryItem.stock > 0).all()
        if not items:
            session.close()
            return jsonify({"success": False, "message": "No in-stock items found to capture."})

        new_cap = ShowPriceCapture(
            name=capture_name,
            timestamp=datetime.now(),
            item_count=len(items),
            total_value=0.0
        )
        session.add(new_cap)
        session.flush()

        total_val = 0.0
        for item in items:
            rounded_price = float(math.ceil(item.price if item.price is not None else 0.0))
            item.sticker_price = rounded_price
            total_val += rounded_price * item.stock
            
            cap_item = ShowPriceCaptureItem(
                capture_id=new_cap.id,
                sku=item.sku,
                sticker_price=rounded_price
            )
            session.add(cap_item)

        new_cap.total_value = total_val
        session.commit()
        session.close()
        return jsonify({"success": True, "message": f"Successfully created price capture '{capture_name}' with {len(items)} items!"})
    except Exception as e:
        session.rollback()
        session.close()
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/inventory/verify_shopify', methods=['POST'])
def api_verify_shopify():
    try:
        core = CoreManager(None, None, None, start_poller=False)
        success, msg = core.verify_shopify_consistency()
        return jsonify({"success": success, "message": msg})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/inventory/run_recon', methods=['POST'])
def api_run_recon():
    if 'file' not in request.files:
        return jsonify({"success": False, "message": "No CSV file uploaded"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"success": False, "message": "Empty filename"}), 400
        
    import os
    import tempfile
    from reconciliation_engine import process_reconciliation
    try:
        temp_dir = tempfile.gettempdir()
        csv_path = os.path.join(temp_dir, file.filename)
        file.save(csv_path)
        
        result = process_reconciliation(csv_path)
        
        unknown_cards = result.get("unknown_cards", [])
        if unknown_cards:
            try:
                from logic import add_item_to_staging
                for card in unknown_cards:
                    staging_data = {
                        "name": card["name"],
                        "set_name": card["set_name"],
                        "sequence_number": card["card_number"],
                        "market_price": card["price"],
                        "card_type": card.get("card_type", "Single"),
                        "variant": card.get("variant", "Normal"),
                        "condition": card.get("condition", "NM"),
                        "quantity": card.get("quantity", 1),
                        "needs_review": True,
                        "confidence_scores": {},
                    }
                    add_item_to_staging(staging_data)
            except Exception as e:
                print(f"[!] Error staging unknown cards: {e}")
                
        prices_updated = result.get("prices_updated", 0)
        removal_list = result.get("removal_list", {})
        add_list = result.get("missing_from_collectr", {})
        
        parts = []
        if prices_updated:
            parts.append(f"• {prices_updated} price update(s) pending in Updated Cards tab")
        if removal_list:
            total_rm = sum(len(v) for v in removal_list.values())
            parts.append(f"• {total_rm} card(s) to remove from Collectr")
        if add_list:
            total_add = sum(len(v) for v in add_list.values())
            parts.append(f"• {total_add} card(s) missing from Collectr")
        if unknown_cards:
            parts.append(f"• {len(unknown_cards)} unknown card(s) sent to Staging")
        if not parts:
            parts.append("• No changes needed — everything is up to date!")
            
        summary_text = "<br>".join(parts)
        
        return jsonify({
            "success": True, 
            "message": f"<b>Collectr Reconciliation Complete!</b><br>{summary_text}",
            "prices_updated": prices_updated
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# --- 3. SOLD ONLINE API ---
@app.route('/api/sold_online', methods=['GET'])
def api_sold_online():
    session = SessionLocal()
    try:
        items = session.query(OnlinePullQueue).filter(OnlinePullQueue.status == 'pending_pull').all()
        results = []
        for item in items:
            inv = session.query(InventoryItem).filter_by(sku=item.sku).first()
            results.append({
                "id": item.id,
                "sku": item.sku,
                "order_id": item.order_id,
                "card_name": inv.name if inv else "Unknown",
                "set_name": inv.set_name if inv else "Unknown",
                "condition": inv.condition if inv else "Unknown"
            })
        session.close()
        return jsonify({"items": results})
    except Exception as e:
        session.close()
        return jsonify({"error": str(e)}), 500

@app.route('/api/sold_online/pull/<int:item_id>', methods=['POST'])
def api_mark_pulled(item_id):
    session = SessionLocal()
    try:
        item = session.query(OnlinePullQueue).filter_by(id=item_id).first()
        if item:
            item.status = 'pulled'
            session.commit()
            session.close()
            try:
                from logic import output_queue
                output_queue.put({'type': 'refresh_sold_online'})
            except Exception:
                pass
            return jsonify({"success": True})
        session.close()
        return jsonify({"success": False, "message": "Not found"}), 404
    except Exception as e:
        session.rollback()
        session.close()
        return jsonify({"success": False, "message": str(e)}), 500

# --- 4. HISTORY API ---
@app.route('/api/history', methods=['GET'])
def api_history():
    session = SessionLocal()
    try:
        sales = session.query(Sale).order_by(Sale.timestamp.desc()).limit(100).all()
        results = []
        for s in sales:
            results.append({
                "timestamp": s.timestamp.strftime("%Y-%m-%d %H:%M"),
                "transaction_type": s.transaction_type,
                "item_name": s.item_name,
                "sku": s.sku,
                "sold_price": float(s.sold_price if s.sold_price > 0 else s.trade_in_value),
                "profit": float(s.profit)
            })
        session.close()
        return jsonify({"sales": results})
    except Exception as e:
        session.close()
        return jsonify({"error": str(e)}), 500

# --- 5. SYNC BOX API ---
@app.route('/api/sync_box', methods=['GET'])
def api_sync_box():
    session = SessionLocal()
    try:
        outbox = session.query(SyncOutbox).order_by(SyncOutbox.timestamp.desc()).limit(100).all()
        results = []
        for item in outbox:
            results.append({
                "timestamp": item.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "action_type": item.action_type,
                "sku": item.sku,
                "quantity_change": item.quantity_change,
                "sync_status": item.sync_status
            })
        session.close()
        return jsonify({"items": results})
    except Exception as e:
        session.close()
        return jsonify({"error": str(e)}), 500

@app.route('/api/sync_box/clear_pending', methods=['POST'])
def api_clear_pending():
    session = SessionLocal()
    try:
        session.query(SyncOutbox).filter(SyncOutbox.sync_status == 'pending').delete(synchronize_session=False)
        session.commit()
        session.close()
        return jsonify({"success": True})
    except Exception as e:
        session.rollback()
        session.close()
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/sync_box/clear_synced', methods=['POST'])
def api_clear_synced():
    session = SessionLocal()
    try:
        session.query(SyncOutbox).filter(SyncOutbox.sync_status == 'synced').delete(synchronize_session=False)
        session.commit()
        session.close()
        return jsonify({"success": True})
    except Exception as e:
        session.rollback()
        session.close()
        return jsonify({"success": False, "message": str(e)}), 500

# --- 6. SETTINGS API ---
@app.route('/api/settings', methods=['GET'])
def api_settings():
    session = SessionLocal()
    try:
        settings = session.query(SystemSettings).first()
        if not settings:
            settings = SystemSettings()
            session.add(settings)
            session.commit()
        res = {
            "price_fluctuation_threshold": float(settings.price_fluctuation_threshold if settings.price_fluctuation_threshold is not None else 0.10),
            "resticker_threshold": float(settings.resticker_threshold if settings.resticker_threshold is not None else 2.00),
            "buy_percentage": float(settings.buy_percentage if settings.buy_percentage is not None else 0.70),
            "trade_percentage": float(settings.trade_percentage if settings.trade_percentage is not None else 0.80)
        }
        session.close()
        return jsonify(res)
    except Exception as e:
        session.close()
        return jsonify({"error": str(e)}), 500

@app.route('/api/settings/update', methods=['POST'])
def api_settings_update():
    session = SessionLocal()
    data = request.get_json()
    try:
        settings = session.query(SystemSettings).first()
        if not settings:
            settings = SystemSettings()
            session.add(settings)

        settings.price_fluctuation_threshold = float(data.get('price_fluctuation_threshold', settings.price_fluctuation_threshold))
        settings.resticker_threshold = float(data.get('resticker_threshold', settings.resticker_threshold))
        settings.buy_percentage = float(data.get('buy_percentage', settings.buy_percentage))
        settings.trade_percentage = float(data.get('trade_percentage', settings.trade_percentage))
        settings.pokemon_icon_url = data.get('pokemon_icon_url', settings.pokemon_icon_url)
        settings.one_piece_icon_url = data.get('one_piece_icon_url', settings.one_piece_icon_url)

        session.commit()
        session.close()
        return jsonify({"success": True})
    except Exception as e:
        session.rollback()
        session.close()
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/updated_cards/approve_single', methods=['POST'])
def api_approve_single_update():
    session = SessionLocal()
    data = request.get_json()
    item_id = data.get('id')
    try:
        item = session.query(InventoryItem).filter_by(id=item_id).first()
        if item:
            item.needs_update = False
            from logic import calculate_shop_price
            shop_price = getattr(item, 'shop_listing_price', None)
            if not shop_price:
                shop_price = calculate_shop_price(item.price)
                item.shop_listing_price = shop_price
            outbox = SyncOutbox(action_type='price_update', sku=item.sku, quantity_change=0, new_price=shop_price)
            session.add(outbox)
            session.commit()
            session.close()
            return jsonify({"success": True})
        session.close()
        return jsonify({"success": False, "message": "Item not found"}), 404
    except Exception as e:
        session.rollback()
        session.close()
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/updated_cards/reject_single', methods=['POST'])
def api_reject_single_update():
    session = SessionLocal()
    data = request.get_json()
    item_id = data.get('id')
    try:
        item = session.query(InventoryItem).filter_by(id=item_id).first()
        if item:
            if getattr(item, 'old_price', None) is not None:
                item.price = item.old_price
                
                from logic import calculate_shop_price, calculate_suggested_price
                settings = session.query(SystemSettings).first()
                rounding_rule = settings.rounding_strategy if settings else "Keep Raw TCG Decimal Payouts"
                
                item.sticker_price = calculate_suggested_price(item.price, rule=rounding_rule)
                shop_price = calculate_shop_price(item.price)
                item.shop_listing_price = shop_price
                
                outbox = SyncOutbox(action_type='price_update', sku=item.sku, quantity_change=0, new_price=shop_price)
                session.add(outbox)
                
            item.needs_update = False
            session.commit()
            session.close()
            return jsonify({"success": True})
        session.close()
        return jsonify({"success": False, "message": "Item not found"}), 404
    except Exception as e:
        session.rollback()
        session.close()
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/updated_cards/approve_under_5', methods=['POST'])
def api_approve_under_5():
    session = SessionLocal()
    try:
        items = session.query(InventoryItem).filter_by(needs_update=True).all()
        approved_count = 0
        from logic import calculate_shop_price
        for item in items:
            old_p = item.old_price if item.old_price is not None else 0.0
            curr_p = item.price if item.price is not None else 0.0
            if abs(curr_p - old_p) < 5.00:
                item.needs_update = False
                shop_price = getattr(item, 'shop_listing_price', None)
                if not shop_price:
                    shop_price = calculate_shop_price(curr_p)
                    item.shop_listing_price = shop_price
                outbox = SyncOutbox(action_type='price_update', sku=item.sku, quantity_change=0, new_price=shop_price)
                session.add(outbox)
                approved_count += 1
        if approved_count > 0:
            session.commit()
        session.close()
        return jsonify({"success": True, "count": approved_count})
    except Exception as e:
        session.rollback()
        session.close()
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/price_updates', methods=['GET'])
def api_get_price_updates():
    session = SessionLocal()
    try:
        items = session.query(InventoryItem).filter_by(needs_update=True).all()
        results = []
        for item in items:
            results.append({
                "id": item.id,
                "sku": str(item.sku or ''),
                "name": str(item.name or 'Unknown Card'),
                "set_name": str(item.set_name or 'Unknown Set'),
                "sequence_number": str(item.sequence_number or ''),
                "condition": str(item.condition or 'NM'),
                "old_price": float(item.old_price) if item.old_price is not None else 0.0,
                "price": float(item.price) if item.price is not None else 0.0,
                "image_url": get_item_image_url(item)
            })
        session.close()
        return jsonify({"success": True, "items": results})
    except Exception as e:
        session.close()
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/force_sync', methods=['POST'])
def api_force_sync():
                "quantity_change": item.quantity_change,
                "sync_status": item.sync_status
            })
        session.close()
        return jsonify({"items": results})
    except Exception as e:
        session.close()
        return jsonify({"error": str(e)}), 500

@app.route('/api/sync_box/clear_pending', methods=['POST'])
def api_clear_pending():
    session = SessionLocal()
    try:
        session.query(SyncOutbox).filter(SyncOutbox.sync_status == 'pending').delete(synchronize_session=False)
        session.commit()
        session.close()
        return jsonify({"success": True})
    except Exception as e:
        session.rollback()
        session.close()
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/sync_box/clear_synced', methods=['POST'])
def api_clear_synced():
    session = SessionLocal()
    try:
        session.query(SyncOutbox).filter(SyncOutbox.sync_status == 'synced').delete(synchronize_session=False)
        session.commit()
        session.close()
        return jsonify({"success": True})
    except Exception as e:
        session.rollback()
        session.close()
        return jsonify({"success": False, "message": str(e)}), 500

# --- 6. SETTINGS API ---
@app.route('/api/settings', methods=['GET'])
def api_settings():
    session = SessionLocal()
    try:
        settings = session.query(SystemSettings).first()
        if not settings:
            settings = SystemSettings()
            session.add(settings)
            session.commit()
        res = {
            "price_fluctuation_threshold": float(settings.price_fluctuation_threshold if settings.price_fluctuation_threshold is not None else 0.10),
            "resticker_threshold": float(settings.resticker_threshold if settings.resticker_threshold is not None else 2.00),
            "buy_percentage": float(settings.buy_percentage if settings.buy_percentage is not None else 0.70),
            "trade_percentage": float(settings.trade_percentage if settings.trade_percentage is not None else 0.80)
        }
        session.close()
        return jsonify(res)
    except Exception as e:
        session.close()
        return jsonify({"error": str(e)}), 500

@app.route('/api/settings/update', methods=['POST'])
def api_settings_update():
    session = SessionLocal()
    data = request.get_json()
    try:
        settings = session.query(SystemSettings).first()
        if not settings:
            settings = SystemSettings()
            session.add(settings)

        settings.price_fluctuation_threshold = float(data.get('price_fluctuation_threshold', settings.price_fluctuation_threshold))
        settings.resticker_threshold = float(data.get('resticker_threshold', settings.resticker_threshold))
        settings.buy_percentage = float(data.get('buy_percentage', settings.buy_percentage))
        settings.trade_percentage = float(data.get('trade_percentage', settings.trade_percentage))
        settings.pokemon_icon_url = data.get('pokemon_icon_url', settings.pokemon_icon_url)
        settings.one_piece_icon_url = data.get('one_piece_icon_url', settings.one_piece_icon_url)

        session.commit()
        session.close()
        return jsonify({"success": True})
    except Exception as e:
        session.rollback()
        session.close()
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/updated_cards/approve_single', methods=['POST'])
def api_approve_single_update():
    session = SessionLocal()
    data = request.get_json()
    item_id = data.get('id')
    try:
        item = session.query(InventoryItem).filter_by(id=item_id).first()
        if item:
            item.needs_update = False
            from logic import calculate_shop_price
            shop_price = getattr(item, 'shop_listing_price', None)
            if not shop_price:
                shop_price = calculate_shop_price(item.price)
                item.shop_listing_price = shop_price
            outbox = SyncOutbox(action_type='price_update', sku=item.sku, quantity_change=0, new_price=shop_price)
            session.add(outbox)
            session.commit()
            session.close()
            return jsonify({"success": True})
        session.close()
        return jsonify({"success": False, "message": "Item not found"}), 404
    except Exception as e:
        session.rollback()
        session.close()
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/updated_cards/reject_single', methods=['POST'])
def api_reject_single_update():
    session = SessionLocal()
    data = request.get_json()
    item_id = data.get('id')
    try:
        item = session.query(InventoryItem).filter_by(id=item_id).first()
        if item:
            if getattr(item, 'old_price', None) is not None:
                item.price = item.old_price
                
                from logic import calculate_shop_price, calculate_suggested_price
                settings = session.query(SystemSettings).first()
                rounding_rule = settings.rounding_strategy if settings else "Keep Raw TCG Decimal Payouts"
                
                item.sticker_price = calculate_suggested_price(item.price, rule=rounding_rule)
                shop_price = calculate_shop_price(item.price)
                item.shop_listing_price = shop_price
                
                outbox = SyncOutbox(action_type='price_update', sku=item.sku, quantity_change=0, new_price=shop_price)
                session.add(outbox)
                
            item.needs_update = False
            session.commit()
            session.close()
            return jsonify({"success": True})
        session.close()
        return jsonify({"success": False, "message": "Item not found"}), 404
    except Exception as e:
        session.rollback()
        session.close()
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/updated_cards/approve_under_5', methods=['POST'])
def api_approve_under_5():
    session = SessionLocal()
    try:
        items = session.query(InventoryItem).filter_by(needs_update=True).all()
        approved_count = 0
        from logic import calculate_shop_price
        for item in items:
            old_p = item.old_price if item.old_price is not None else 0.0
            curr_p = item.price if item.price is not None else 0.0
            if abs(curr_p - old_p) < 5.00:
                item.needs_update = False
                shop_price = getattr(item, 'shop_listing_price', None)
                if not shop_price:
                    shop_price = calculate_shop_price(curr_p)
                    item.shop_listing_price = shop_price
                outbox = SyncOutbox(action_type='price_update', sku=item.sku, quantity_change=0, new_price=shop_price)
                session.add(outbox)
                approved_count += 1
        if approved_count > 0:
            session.commit()
        session.close()
        return jsonify({"success": True, "count": approved_count})
    except Exception as e:
        session.rollback()
        session.close()
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/price_updates', methods=['GET'])
def api_get_price_updates():
    session = SessionLocal()
    try:
        items = session.query(InventoryItem).filter_by(needs_update=True).all()
        results = []
        for item in items:
            results.append({
                "id": item.id,
                "sku": str(item.sku or ''),
                "name": str(item.name or 'Unknown Card'),
                "set_name": str(item.set_name or 'Unknown Set'),
                "sequence_number": str(item.sequence_number or ''),
                "condition": str(item.condition or 'NM'),
                "old_price": float(item.old_price) if item.old_price is not None else 0.0,
                "price": float(item.price) if item.price is not None else 0.0,
                "image_url": get_item_image_url(item)
            })
        session.close()
        return jsonify({"success": True, "items": results})
    except Exception as e:
        session.close()
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/force_sync', methods=['POST'])
def api_force_sync():
    import threading
    def _sync():
        core_manager = CoreManager(None, None, None, start_poller=False)
        core_manager._process_sync_outbox()
    threading.Thread(target=_sync, daemon=True).start()
    return jsonify({"success": True, "message": "Shopify sync has been triggered in the background."})

@app.route('/api/logs', methods=['GET'])
def api_logs():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    log_path = os.path.join(base_dir, "app_logs.txt")
    if not os.path.exists(log_path):
        return jsonify({"logs": []})
    
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        # Return last 100 lines max
        return jsonify({"logs": lines[-100:]})
    except Exception as e:
        return jsonify({"logs": [f"Error reading logs: {e}"]})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)

"""Collectr CSV reconciliation — ported from partner reconciliation_engine.py (2026-08-09)."""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timedelta
from io import StringIO

import pandas as pd
from rapidfuzz import fuzz
from sqlalchemy.orm import Session

from app.logic.pricing import calculate_shop_listing_price
from app.models import InventoryItem, Sale, SystemSettings


def norm_seq(seq: object) -> str:
    if seq is None or (isinstance(seq, float) and pd.isna(seq)) or not seq:
        return ""
    s = str(seq).strip().lower()
    # Split on '/' or '-' and take the first part to handle '119/189' matching '119'
    s = re.split(r"[/\\-]", s)[0]
    return re.sub(r"[^a-z0-9]", "", s)


def is_seq_match(seq1: str, seq2: str) -> bool:
    if not seq1 or not seq2:
        return True
    return seq1 == seq2


def process_reconciliation(
    db: Session,
    shop_id: str,
    csv_content: str,
    since_date: str | None = None,
) -> dict:
    """
    Aggregate Collectr CSV vs all inventory (incl. stock 0).
    Exact name match; qty excess → recent unreconciled sales → removal list.
    Default sales window: 7 days.
    """
    failure: dict = {
        "success": False,
        "removal_list": {},
        "unknown_cards": [],
        "missing_from_collectr": {},
        "prices_updated": 0,
        "updated_items_log": [],
        "to_remove": [],
        "to_add": [],
        "matches_found": 0,
    }

    try:
        df = pd.read_csv(StringIO(csv_content))
    except Exception as exc:
        failure["message"] = f"CSV parse error: {exc}"
        return failure

    required_cols = ["Product Name", "Set", "Card Number"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        failure["message"] = f"Missing columns: {missing_cols}"
        return failure

    cutoff_date: datetime | None
    if since_date:
        try:
            cutoff_date = datetime.strptime(since_date, "%Y-%m-%d")
        except ValueError:
            failure["message"] = "Invalid since_date — use YYYY-MM-DD"
            return failure
    else:
        cutoff_date = datetime.utcnow() - timedelta(days=7)

    settings = (
        db.query(SystemSettings).filter(SystemSettings.shop_id == shop_id).first()
    )

    all_inventory = (
        db.query(InventoryItem).filter(InventoryItem.shop_id == shop_id).all()
    )

    inv_lookup = []
    for inv_item in all_inventory:
        inv_lookup.append(
            {
                "id": inv_item.id,
                "sku": inv_item.sku,
                "orig_name": inv_item.name,
                "orig_num": inv_item.sequence_number,
                "orig_set": inv_item.set_name,
                "stock": inv_item.stock,
                "name": str(inv_item.name).strip().lower(),
                "set_name": str(inv_item.set_name).strip().lower()
                if inv_item.set_name
                else "",
                "sequence_number": str(inv_item.sequence_number).strip().lower()
                if inv_item.sequence_number
                else "",
                "price": float(inv_item.price) if inv_item.price is not None else 0.0,
                "condition": inv_item.condition or "NM",
                "variant": inv_item.variant or "Normal",
                "card_type": inv_item.card_type or "Single",
                "obj": inv_item,
            }
        )

    c_lower_map = {col.lower().strip(): col for col in df.columns}
    price_col = None
    for p in [
        "market price",
        "market value",
        "current value",
        "value",
        "price",
        "unit price",
    ]:
        if p in c_lower_map:
            price_col = c_lower_map[p]
            break
    if not price_col:
        for p in ["market", "value", "price"]:
            for c_lower, col in c_lower_map.items():
                if p in c_lower and "total" not in c_lower:
                    price_col = col
                    break
            if price_col:
                break

    cond_col = c_lower_map.get(
        "condition", c_lower_map.get("card condition", c_lower_map.get("state"))
    )
    var_col = c_lower_map.get(
        "variance", c_lower_map.get("variant", c_lower_map.get("finish"))
    )
    qty_col = c_lower_map.get(
        "quantity", c_lower_map.get("qty", c_lower_map.get("count"))
    )
    graded_col = c_lower_map.get("grade", c_lower_map.get("graded"))
    bgs_col = c_lower_map.get("bgs", c_lower_map.get("bgs grade"))

    csv_aggregated: list[dict] = []
    for _, row in df.iterrows():
        csv_price = 0.0
        if price_col and pd.notna(row.get(price_col)):
            try:
                raw_val = str(row[price_col]).replace(",", "")
                num_match = re.search(r"\d+\.?\d*", raw_val)
                if num_match:
                    csv_price = float(num_match.group())
            except Exception:
                pass

        if csv_price <= 0.0:
            continue

        csv_name = (
            str(row["Product Name"]).strip().lower()
            if pd.notna(row["Product Name"])
            else ""
        )
        csv_set = str(row["Set"]).strip().lower() if pd.notna(row["Set"]) else ""
        csv_num = norm_seq(row["Card Number"])

        raw_cond = (
            str(row[cond_col]).strip()
            if cond_col and pd.notna(row.get(cond_col))
            else "Near Mint"
        )
        raw_cond_lower = raw_cond.lower()
        is_graded = False
        cond_code = "NM"

        if graded_col and pd.notna(row.get(graded_col)):
            g_val = str(row[graded_col]).strip()
            if g_val and g_val.lower() not in [
                "nan",
                "none",
                "null",
                "false",
                "no",
                "",
                "ungraded",
            ]:
                is_graded = True
                if g_val.lower() not in ["yes", "true", "graded"]:
                    cond_code = g_val
                else:
                    if bgs_col and pd.notna(row.get(bgs_col)):
                        b_val = str(row[bgs_col]).strip()
                        if b_val and b_val.lower() not in ["nan", "none", "null", ""]:
                            cond_code = f"BGS {b_val}"
                        else:
                            cond_code = raw_cond
                    else:
                        cond_code = raw_cond

        if not is_graded and any(
            term in raw_cond_lower
            for term in ["psa", "bgs", "cgc", "grade", "gem", "pristine"]
        ):
            is_graded = True
            cond_code = raw_cond

        if not is_graded:
            if "lightly" in raw_cond_lower or raw_cond_lower == "lp":
                cond_code = "LP"
            elif "moderately" in raw_cond_lower or raw_cond_lower == "mp":
                cond_code = "MP"
            elif "heavily" in raw_cond_lower or raw_cond_lower == "hp":
                cond_code = "HP"
            elif "damaged" in raw_cond_lower or raw_cond_lower == "dmg":
                cond_code = "DMG"

        raw_variant = (
            str(row[var_col]).strip()
            if var_col and pd.notna(row.get(var_col))
            else "Normal"
        )
        csv_qty = 1
        if qty_col and pd.notna(row.get(qty_col)):
            try:
                csv_qty = int(row[qty_col])
            except Exception:
                csv_qty = 1

        card_num = (
            str(row["Card Number"]).strip() if pd.notna(row["Card Number"]) else ""
        )
        if str(card_num).lower() == "nan":
            card_num = ""

        card_type = "Graded" if is_graded else ("Sealed" if card_num == "" else "Single")

        csv_aggregated.append(
            {
                "orig_name": str(row["Product Name"]).strip()
                if pd.notna(row["Product Name"])
                else "Unknown",
                "orig_set": str(row["Set"]).strip() if pd.notna(row["Set"]) else "",
                "orig_num": card_num,
                "name": csv_name,
                "set_name": csv_set,
                "sequence_number": csv_num,
                "price": csv_price,
                "condition": cond_code,
                "variant": raw_variant,
                "quantity": csv_qty,
                "card_type": card_type,
                "is_graded": is_graded,
            }
        )

    combined_csv: dict[tuple, dict] = {}
    for row in csv_aggregated:
        key = (row["name"], row["set_name"], row["sequence_number"])
        if key not in combined_csv:
            combined_csv[key] = row.copy()
        else:
            combined_csv[key]["quantity"] += row["quantity"]
            combined_csv[key]["is_graded"] = (
                combined_csv[key]["is_graded"] or row["is_graded"]
            )

    inv_aggregated: dict[tuple, dict] = {}
    for inv in inv_lookup:
        key = (inv["name"], inv["set_name"], norm_seq(inv["orig_num"]))
        if key not in inv_aggregated:
            inv_aggregated[key] = {
                "orig_name": inv["orig_name"],
                "orig_set": inv["orig_set"],
                "orig_num": inv["orig_num"],
                "stock": 0,
                "skus": [],
                "price": inv["price"],
                "card_type": inv["card_type"],
                "items": [],
            }
        inv_aggregated[key]["stock"] += inv["stock"]
        inv_aggregated[key]["skus"].append(inv["sku"])
        inv_aggregated[key]["items"].append(inv)

    removal_list: dict[str, list] = defaultdict(list)
    unknown_cards: list[dict] = []
    missing_from_collectr: dict[str, list] = defaultdict(list)
    updated_items_log: list[str] = []
    prices_updated = 0
    matched_inv_keys: set[tuple] = set()

    for _key, row in combined_csv.items():
        matched_inv = None
        matched_key = None
        for inv_key, inv_data in inv_aggregated.items():
            if inv_key in matched_inv_keys:
                continue

            seq_match = is_seq_match(inv_key[2], row["sequence_number"])
            set_match = (
                fuzz.partial_ratio(inv_key[1], row["set_name"]) >= 70
                if inv_key[1] and row["set_name"]
                else True
            )
            name_match = inv_key[0] == row["name"]

            if seq_match and set_match and name_match:
                matched_inv = inv_data
                matched_key = inv_key
                matched_inv_keys.add(inv_key)
                break

        if matched_inv and matched_key is not None:
            inv_stock = matched_inv["stock"]
            csv_qty = row["quantity"]

            omit_graded = bool(
                settings and getattr(settings, "omit_graded_from_recon", False)
            )
            if not (omit_graded and row["is_graded"]):
                try:
                    for inv in matched_inv["items"]:
                        inv_price = inv["price"]
                        price_diff = abs(inv_price - row["price"])
                        if price_diff >= 0.01:
                            shop_price = calculate_shop_listing_price(
                                db, shop_id, row["price"], inv["card_type"]
                            )
                            log_msg = (
                                f"{inv['sku']} ({inv['orig_name']} {inv['orig_num']}): "
                                f"${inv_price:.2f} -> ${row['price']:.2f} "
                                f"(shop: ${shop_price:.2f})"
                            )
                            updated_items_log.append(log_msg)
                            inv["obj"].old_price = inv_price
                            inv["obj"].price = row["price"]
                            inv["obj"].shop_listing_price = shop_price
                            inv["obj"].needs_update = True
                            prices_updated += 1
                except Exception:
                    pass

            if csv_qty > inv_stock:
                extra_qty = csv_qty - inv_stock
                recent_sales = 0
                if cutoff_date:
                    sales = (
                        db.query(Sale)
                        .filter(
                            Sale.shop_id == shop_id,
                            Sale.sku.in_(matched_inv["skus"]),
                            Sale.is_reconciled.is_(False),
                            Sale.timestamp >= cutoff_date,
                        )
                        .all()
                    )
                    recent_sales = len(sales)

                qty_to_remove = min(recent_sales, extra_qty)
                unaccounted = extra_qty - qty_to_remove

                if qty_to_remove > 0:
                    display_set = matched_inv["orig_set"] or "Unknown Set"
                    removal_list[display_set].append(
                        {
                            "name": matched_inv["orig_name"],
                            "num": matched_inv["orig_num"] or "??",
                            "sku": matched_inv["skus"][0],
                            "skus": matched_inv["skus"],
                            "price": matched_inv["price"],
                            "qty_to_remove": qty_to_remove,
                        }
                    )

                if unaccounted > 0:
                    unknown_cards.append(
                        {
                            "name": matched_inv["orig_name"],
                            "set_name": matched_inv["orig_set"],
                            "card_number": matched_inv["orig_num"],
                            "price": row["price"],
                            "condition": row["condition"],
                            "variant": row["variant"],
                            "quantity": unaccounted,
                            "card_type": row["card_type"],
                            "sku": matched_inv["skus"][0],
                        }
                    )
            elif inv_stock > csv_qty:
                missing_qty = inv_stock - csv_qty
                display_set = matched_inv["orig_set"] or "Unknown Set"
                missing_from_collectr[display_set].append(
                    {
                        "name": matched_inv["orig_name"],
                        "num": matched_inv["orig_num"] or "??",
                        "sku": matched_inv["skus"][0],
                        "missing_qty": missing_qty,
                    }
                )
        else:
            unknown_cards.append(
                {
                    "name": row["orig_name"],
                    "set_name": row["orig_set"],
                    "card_number": row["orig_num"],
                    "price": row["price"],
                    "condition": row["condition"],
                    "variant": row["variant"],
                    "quantity": row["quantity"],
                    "card_type": row["card_type"],
                }
            )

    for inv_key, inv_data in inv_aggregated.items():
        if inv_key not in matched_inv_keys and inv_data["stock"] > 0:
            display_set = inv_data["orig_set"] or "Unknown Set"
            missing_from_collectr[display_set].append(
                {
                    "name": inv_data["orig_name"],
                    "num": inv_data["orig_num"] or "??",
                    "sku": inv_data["skus"][0],
                    "missing_qty": inv_data["stock"],
                }
            )

    if prices_updated > 0:
        db.commit()

    matches_found = sum(len(v) for v in removal_list.values())

    to_remove = [
        {
            "sku": item["sku"],
            "skus": item.get("skus", [item["sku"]]),
            "name": item["name"],
            "set": set_name,
            "num": item["num"],
            "qty_to_remove": item.get("qty_to_remove", 1),
        }
        for set_name, items in removal_list.items()
        for item in items
    ]
    to_add = [
        {
            "name": card["name"],
            "set_name": card.get("set_name", ""),
            "card_number": card.get("card_number", ""),
            "quantity": card.get("quantity", 1),
            "price": card.get("price", 0.0),
        }
        for card in unknown_cards
    ]

    return {
        "success": True,
        "removal_list": dict(removal_list),
        "missing_from_collectr": dict(missing_from_collectr),
        "unknown_cards": unknown_cards,
        "prices_updated": prices_updated,
        "updated_items_log": updated_items_log,
        "matches_found": matches_found,
        "to_remove": to_remove,
        "to_add": to_add,
        "sales_since": cutoff_date.isoformat() if cutoff_date else None,
    }


def mark_removals_reconciled(
    db: Session,
    shop_id: str,
    removal_items: list[dict],
) -> dict:
    """Mark recent unreconciled sales as reconciled after Collectr removals are applied."""
    marked = 0
    for item in removal_items:
        skus = item.get("skus") or ([item["sku"]] if item.get("sku") else [])
        qty = int(item.get("qty_to_remove") or 1)
        if not skus or qty <= 0:
            continue
        sales = (
            db.query(Sale)
            .filter(
                Sale.shop_id == shop_id,
                Sale.sku.in_(skus),
                Sale.is_reconciled.is_(False),
            )
            .order_by(Sale.timestamp.desc())
            .limit(qty)
            .all()
        )
        for sale in sales:
            sale.is_reconciled = True
            marked += 1
    if marked:
        db.commit()
    return {"success": True, "marked": marked}

"""CSV inventory import — ported from partner import_engine.py."""

from __future__ import annotations

import math
import secrets
from io import StringIO

import pandas as pd
from sqlalchemy.orm import Session

from app.models import InventoryItem, StagingItem


def generate_sku() -> str:
    return f"CS-{secrets.token_hex(2).upper()}"


def process_csv_import(
    db: Session,
    shop_id: str,
    csv_content: str,
    *,
    actor_clerk_user_id: str | None = None,
    role: str | None = None,
    upload_id: str | None = None,
    reason_code: str = "csv_correction",
) -> dict:
    try:
        df = pd.read_csv(StringIO(csv_content))
    except Exception as exc:
        return {"success": False, "message": f"CSV parse error: {exc}"}

    df.columns = [str(c).strip() for c in df.columns]
    col_map = {str(c).lower(): str(c) for c in df.columns}

    name_col = col_map.get("product name", col_map.get("name"))
    set_col = col_map.get("set", col_map.get("set name"))
    num_col = col_map.get("card number", col_map.get("number"))
    if not name_col or not set_col:
        return {"success": False, "message": "Missing Product Name or Set column"}

    game_col = col_map.get("game", col_map.get("category"))
    cost_col = col_map.get("cost", col_map.get("price paid", col_map.get("total paid")))
    market_price_col = col_map.get(
        "market price",
        col_map.get("market value", col_map.get("market_value", col_map.get("price"))),
    )
    qty_col = col_map.get("quantity", col_map.get("qty"))
    cond_col = col_map.get("condition", col_map.get("card condition"))
    var_col = col_map.get("variance", col_map.get("variant", col_map.get("rarity")))
    graded_col = col_map.get("grade", col_map.get("graded"))
    bgs_col = col_map.get("bgs", col_map.get("bgs grade"))

    imported = 0
    updated = 0
    sealed_count = 0
    review_count = 0
    errors = 0
    parsed_rows: list[dict] = []

    for index, row in df.iterrows():
        try:
            raw_name = str(row[name_col]).strip() if name_col else "Unknown"
            raw_set = str(row[set_col]).strip() if set_col else "Unknown"
            raw_number = (
                str(row[num_col]).strip()
                if num_col and str(row[num_col]).lower() != "nan"
                else ""
            )

            game = "Pokemon"
            if game_col:
                g_val = str(row[game_col]).strip()
                if g_val and g_val.lower() != "nan":
                    game = g_val

            if game.lower() == "one piece" and raw_number and "-" in raw_number:
                prefix = raw_number.split("-")[0].strip()
                if prefix and prefix not in raw_set:
                    raw_set = f"{raw_set} - {prefix}"

            variant = None
            if var_col:
                var_val = str(row[var_col]).strip()
                if var_val and var_val.lower() != "nan":
                    variant = var_val

            is_sealed = raw_number == "" and not (
                (variant and "don!!" in variant.lower()) or "don!!" in raw_name.lower()
            )

            quantity = 1
            if qty_col:
                try:
                    quantity = int(row[qty_col])
                except (ValueError, TypeError):
                    quantity = 1

            cost_paid = 0.0
            if cost_col:
                try:
                    cost_paid = float(str(row[cost_col]).replace("$", "").replace(",", ""))
                except (ValueError, TypeError):
                    cost_paid = 0.0

            price = 0.0
            if market_price_col:
                try:
                    p_str = str(row[market_price_col]).strip()
                    if p_str.lower() not in ["nan", "none", "null", "", "n/a", "-"]:
                        price = float(p_str.replace("$", "").replace(",", "").replace(" ", ""))
                except (ValueError, TypeError):
                    price = 0.0

            condition = "None (Ungraded)"
            is_graded = False
            if cond_col:
                val = str(row[cond_col]).strip()
                if val and val.lower() not in ["nan", "none", "null", ""]:
                    condition = val
            if graded_col:
                g_val = str(row[graded_col]).strip()
                if g_val and g_val.lower() not in ["nan", "none", "null", "false", "no", "", "ungraded"]:
                    is_graded = True
                    if g_val.lower() not in ["yes", "true", "graded"]:
                        condition = g_val
                    elif bgs_col:
                        b_val = str(row[bgs_col]).strip()
                        if b_val and b_val.lower() not in ["nan", "none", "null", ""]:
                            condition = f"BGS {b_val}"

            if is_sealed:
                card_type = "Sealed"
                sealed_count += 1
            elif is_graded:
                card_type = "Graded"
            else:
                card_type = "Single"
                review_count += 1

            if is_sealed:
                existing = (
                    db.query(InventoryItem)
                    .filter(
                        InventoryItem.shop_id == shop_id,
                        InventoryItem.name == raw_name,
                        InventoryItem.set_name == raw_set,
                        InventoryItem.card_type == "Sealed",
                    )
                    .first()
                )
            else:
                existing = (
                    db.query(InventoryItem)
                    .filter(
                        InventoryItem.shop_id == shop_id,
                        InventoryItem.name == raw_name,
                        InventoryItem.set_name == raw_set,
                        InventoryItem.sequence_number == raw_number,
                        InventoryItem.condition == condition,
                        InventoryItem.game == game,
                    )
                    .first()
                )

            if existing:
                parsed_rows.append({"row_identity": existing.sku, "target": quantity})
                updated += 1
            else:
                imported += 1
        except Exception:
            errors += 1

    quantity_changing = qty_col is not None or bool(parsed_rows) or imported > 0
    if quantity_changing:
        from app.errors import FeatureNotReadyError
        from app.feature_readiness import ensure_inventory_mutations_ready
        from app.inventory_truth.core import ReceiveFrozenError

        try:
            ensure_inventory_mutations_ready(db, shop_id)
        except FeatureNotReadyError:
            db.rollback()
            raise
        except ReceiveFrozenError as exc:
            db.rollback()
            raise FeatureNotReadyError("inventory_truth") from exc

    if imported:
        db.rollback()
        return {
            "success": False,
            "message": "csv contains a new-item quantity row",
            "imported": 0,
            "updated": 0,
        }
    if parsed_rows:
        from app.inventory_truth.core_adjust import (
            AdjustConflict,
            AdjustForbidden,
            AdjustFrozenError,
            AdjustRejected,
            apply_csv_adjustments,
        )

        try:
            apply_csv_adjustments(
                db,
                shop_id=shop_id,
                actor_clerk_user_id=actor_clerk_user_id or "",
                role=role,
                upload_id=upload_id or "",
                rows=parsed_rows,
                default_reason=reason_code,
            )
        except AdjustFrozenError:
            db.rollback()
            from app.errors import FeatureNotReadyError

            raise FeatureNotReadyError("inventory_truth")
        except (AdjustRejected, AdjustConflict, AdjustForbidden) as exc:
            db.rollback()
            return {"success": False, "message": str(exc)}
    else:
        db.commit()
    return {
        "success": True,
        "imported": 0,
        "updated": updated,
        "sealed": sealed_count,
        "needs_review": review_count,
        "errors": errors,
        "total_rows": len(df),
    }


def patch_conditions_from_csv(db: Session, shop_id: str, csv_content: str) -> dict:
    """Update condition/card_type/game on existing inventory from Collectr CSV."""
    try:
        df = pd.read_csv(StringIO(csv_content))
    except Exception as exc:
        return {"success": False, "message": f"CSV parse error: {exc}", "updated": 0, "not_found": 0}

    df.columns = [str(c).strip() for c in df.columns]
    col_map = {str(c).lower(): str(c) for c in df.columns}

    name_col = col_map.get("product name", col_map.get("name"))
    set_col = col_map.get("set", col_map.get("set name"))
    num_col = col_map.get("card number", col_map.get("number"))
    game_col = col_map.get("game", col_map.get("category"))
    if not name_col or not set_col:
        return {"success": False, "message": "Missing name or set columns", "updated": 0, "not_found": 0}

    updated_count = 0
    not_found_count = 0

    for index, row in df.iterrows():
        try:
            raw_name = str(row[name_col]).strip() if name_col else "Unknown"
            raw_set = str(row[set_col]).strip() if set_col else "Unknown"
            raw_number = (
                str(row[num_col]).strip()
                if num_col and str(row[num_col]).lower() != "nan"
                else ""
            )
            variant = None
            var_col = col_map.get("variance", col_map.get("variant", col_map.get("rarity")))
            if var_col:
                var_val = str(row[var_col]).strip()
                if var_val and var_val.lower() != "nan":
                    variant = var_val

            is_sealed = raw_number == "" and not (
                (variant and "don!!" in variant.lower()) or ("don!!" in raw_name.lower())
            )

            game = "Pokemon"
            if game_col:
                g_val = str(row[game_col]).strip()
                if g_val and g_val.lower() != "nan":
                    game = g_val

            if game.lower() == "one piece" and raw_number and "-" in raw_number:
                prefix = raw_number.split("-")[0].strip()
                if prefix and prefix not in raw_set:
                    raw_set = f"{raw_set} - {prefix}"

            condition = "None (Ungraded)"
            is_graded = False

            cond_col = col_map.get(
                "condition", col_map.get("card condition", col_map.get("state"))
            )
            if cond_col:
                val = str(row[cond_col]).strip()
                if val and val.lower() not in ["nan", "none", "null", ""]:
                    condition = val

            graded_col = col_map.get("grade", col_map.get("graded"))
            if graded_col:
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
                        condition = g_val
                    else:
                        bgs_col = col_map.get("bgs", col_map.get("bgs grade"))
                        if bgs_col:
                            b_val = str(row[bgs_col]).strip()
                            if b_val and b_val.lower() not in ["nan", "none", "null", ""]:
                                condition = f"BGS {b_val}"

            if is_sealed:
                card_type = "Sealed"
            elif is_graded:
                card_type = "Graded"
            else:
                card_type = "Single"

            items = (
                db.query(InventoryItem)
                .filter(
                    InventoryItem.shop_id == shop_id,
                    InventoryItem.name == raw_name,
                    InventoryItem.set_name == raw_set,
                    InventoryItem.sequence_number == raw_number,
                )
                .all()
            )

            if items:
                for item in items:
                    item.condition = condition
                    item.card_type = card_type
                    item.game = game
                updated_count += len(items)
            else:
                not_found_count += 1
        except Exception:
            not_found_count += 1

    db.commit()
    return {
        "success": True,
        "updated": updated_count,
        "not_found": not_found_count,
        "total_rows": len(df),
    }

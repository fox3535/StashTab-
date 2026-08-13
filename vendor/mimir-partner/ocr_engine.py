import os
import re
import cv2
import numpy as np
import easyocr
import difflib
from typing import List, Dict, Any, Tuple, Optional
from rapidfuzz import process, fuzz

KNOWN_TERMS = [
    "Holofoil", "Reverse Holofoil", "Secret Rare", "Ultra Rare", "Full Art", 
    "Near Mint", "Lightly Played", "Moderately Played", "Heavily Played", "Damaged",
    "Standard", "Pokemon", "Magic: The Gathering", "Yu-Gi-Oh!", "Flesh and Blood", 
    "One Piece", "Lorcana", "Ascended Heroes"
]

# Global reader instance to prevent re-initialization on every scan row
_reader = None

def get_reader():
    global _reader
    if _reader is None:
        print("[*] Initializing EasyOCR Reader...")
        _reader = easyocr.Reader(['en'])
    return _reader

KEYWORDS = ["Variant", "Type", "Condition", "Quantity"]

class RowParser:
    """
    Decoupled parsing engine responsible for structural row image processing and value extraction
    using EasyOCR, CLAHE image enhancement, card artwork masking, and fuzzy matching.
    """
    def __init__(self):
        self.reader = get_reader()
        self.known_sets = self.load_known_sets()

    def load_known_sets(self) -> List[str]:
        """Loads the curated set names from set_names.txt, set_names_ja.txt, and set_names_zh.txt."""
        base_path = os.path.dirname(os.path.abspath(__file__))
        files = {
            "English": "set_names.txt",
            "Japanese": "set_names_ja.txt",
            "Chinese": "set_names_zh.txt"
        }
        
        all_sets = []
        for lang, filename in files.items():
            file_path = os.path.join(base_path, filename)
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        lang_sets = [line.strip() for line in f if line.strip()]
                    all_sets.extend(lang_sets)
                    print(f"[OCR] Loaded {len(lang_sets)} known {lang} set names.")
                except Exception as e:
                    print(f"[OCR] Error reading {filename}: {e}")
            else:
                print(f"[OCR] Warning: {filename} ({lang}) not found at {file_path}")
                
        # Deduplicate while preserving order if possible (standard list conversion)
        seen = set()
        deduped_sets = []
        for s in all_sets:
            s_lower = s.lower()
            if s_lower not in seen:
                seen.add(s_lower)
                deduped_sets.append(s)
        return deduped_sets

    def fuzzy_correct_set_name(self, set_name: str) -> str:
        """
        Fuzzy matches the extracted set name against known sets.
        If a good match is found (confidence >= 60%), use it.
        Otherwise, fall back to cleaning/sanitizing.
        """
        if not set_name or set_name == "Unknown":
            return set_name

        # Clean the string for matching: remove card type words
        clean_name = set_name.strip()
        clean_name = re.sub(r'^(pok\w*|magic|yu-?gi|lorcana|flesh\s*and\s*blood|one\s*piece)\b', '', clean_name, flags=re.IGNORECASE).strip()
        
        # If the string became empty, it means OCR only read the card type (e.g. 'Pokenknn')
        # We should return Unknown rather than assigning the card type as the set name.
        if not clean_name:
            return "Unknown"

        # Try to find a match using rapidfuzz
        if self.known_sets:
            match = process.extractOne(clean_name, self.known_sets, scorer=fuzz.WRatio)
            if match:
                matched_name, score = match[0], match[1]
                print(f"[OCR] Fuzzy set matching: '{clean_name}' vs '{matched_name}' -> score {score:.1f}%")
                # Threshold raised to 90 to prevent near-misses like 'Destined Rivals' -> 'Rising Rivals'
                if score >= 90:
                    print(f"[OCR] Corrected set name: '{set_name}' -> '{matched_name}'")
                    return matched_name
                else:
                    print(f"[OCR] Fuzzy match below threshold ({score:.0f}% < 90%) - keeping original: '{clean_name}'")

        # Fallback to sanitizing (like Pokemon check)
        return self.sanitize_set_name(clean_name)

    def preprocess_for_ocr(self, roi_img: np.ndarray) -> np.ndarray:
        """Applies 3x upscaling, grayscale, and thresholding for high-fidelity OCR."""
        h, w = roi_img.shape[:2]
        # 3x upscale using INTER_CUBIC
        roi_img = cv2.resize(roi_img, (w * 3, h * 3), interpolation=cv2.INTER_CUBIC)
        gray = cv2.cvtColor(roi_img, cv2.COLOR_BGR2GRAY)
        
        # Thresholding
        _, thresholded = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return thresholded

    def extract_price_spatial(self, ocr_results: List[Any], image_width: int, image_height: int) -> Tuple[float, float]:
        """
        Spatially isolates the market price by anchoring to the 'Set Price Paid' label.
        """
        words = []
        for res in ocr_results:
            bbox, text, conf = res
            if conf > 0.085:  # Lowered from 0.10 by 15%
                top_y = min([p[1] for p in bbox])
                bottom_y = max([p[1] for p in bbox])
                left_x = min([p[0] for p in bbox])
                right_x = max([p[0] for p in bbox])
                words.append({
                    'text': text.strip(), 
                    'conf': conf, 
                    'top_y': top_y, 
                    'bottom_y': bottom_y, 
                    'left_x': left_x, 
                    'right_x': right_x
                })
                
        # 1. Find the Anchor
        anchor_y = None
        for i in range(len(words) - 1):
            w1 = words[i]['text'].lower()
            w2 = words[i+1]['text'].lower()
            if w1 == 'set' and (w2 == 'price' or w2 == 'paid'):
                anchor_y = words[i]['top_y']
                break
                
        if anchor_y is None:
            # Fallback to scanning the middle 50%
            anchor_y = image_height * 0.8
            
        candidates = []
        # 2. Find Candidate Prices
        price_regex = re.compile(r'([\$S5]?\d{1,3}(?:,\d{3})*\.\d{2})', re.IGNORECASE)
        for w in words:
            match = price_regex.search(w['text'])
            if match:
                candidates.append((w, match.group(1)))
                
        # 3. Spatial Filtering
        valid_candidates = []
        for w, match_str in candidates:
            # Vertical: candidate's bottom Y-coordinate must be less than (above) the anchor's top Y-coordinate
            if w['bottom_y'] <= anchor_y + 15: # 15px buffer
                # Horizontal: roughly in the middle of the row (between 30% and 70%)
                center_x = (w['left_x'] + w['right_x']) / 2
                if image_width * 0.3 <= center_x <= image_width * 0.7:
                    valid_candidates.append((w, match_str))
                    
        # 4. Sanitize and Return
        if not valid_candidates:
            return 0.0, 100.0
            
        # Take the closest valid candidate to the anchor
        valid_candidates.sort(key=lambda c: abs(anchor_y - c[0]['bottom_y']))
        best_w, best_str = valid_candidates[0]
        
        # Clean price string
        clean_match = re.search(r'[\$S5]?(\d{1,3}(?:,\d{3})*\.\d{2})', best_str, re.IGNORECASE)
        if clean_match:
            raw_str = clean_match.group(1).replace(',', '')
        else:
            # Strip any garbled prefix chars (e.g. '2H4 790.90' -> '790.90')
            # Find the rightmost occurrence of digits+dot+digits pattern
            fallback = re.search(r'(\d{1,3}(?:,\d{3})*\.\d{2})\s*$', best_str)
            if fallback:
                raw_str = fallback.group(1).replace(',', '')
            else:
                raw_str = re.sub(r'[^0-9.]', '', best_str)
            
        try:
            val = float(raw_str)
            # Sanity check: reject anything over $10,000 or negative
            if val <= 0.0 or val > 10000.0:
                return 0.0, 100.0
            return val, best_w['conf'] * 100.0
        except ValueError:
            return 0.0, 100.0

    def detect_card_art_and_mask(self, roi_img: np.ndarray) -> Tuple[np.ndarray, Optional[Tuple[int, int, int, int]]]:
        """Detects the card thumbnail artwork and masks it to pure black to reduce OCR noise."""
        masked_img = roi_img.copy()
        h, w = roi_img.shape[:2]
        
        # Search in the left 40% of the row where the thumbnail resides
        search_area = roi_img[:, :int(w * 0.4)]
        gray = cv2.cvtColor(search_area, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        art_bbox = None
        if contours:
            contours = sorted(contours, key=cv2.contourArea, reverse=True)
            for cnt in contours:
                ax, ay, aw, ah = cv2.boundingRect(cnt)
                # Filter for a valid square/rectangular artwork box size
                if aw > 50 and ah > 50 and ah < h * 0.95:
                    art_bbox = (ax, ay, aw, ah)
                    cv2.rectangle(masked_img, (ax, ay), (ax + aw, ay + ah), (0, 0, 0), -1)
                    break
        return masked_img, art_bbox

    def parse_results(self, ocr_results: List[Any]) -> Tuple[Dict[str, Any], Dict[str, float]]:
        """Complex coordinate-based parser with fuzzy keyword matching."""
        data: Dict[str, Any] = {
            "Card Name": "Unknown",
            "Card Type": "Unknown",
            "Set Name": "Unknown",
            "Set Number": "Unknown",
            "Price": 0.0,
            "Variant": "Standard",
            "Type": "None (Ungraded)",
            "Condition": "Near Mint",
            "Quantity": 1
        }
        
        conf_scores = {
            "name": 100.0,
            "set_name": 100.0,
            "market_price": 100.0
        }
        
        if not ocr_results:
            return data, conf_scores
        
        # Filter high-confidence words and track their visual Y-coordinate
        words = []
        for res in ocr_results:
            bbox, text, conf = res
            if conf > 0.05:  # Lowered from 0.20 by 15% (absolute)
                words.append({'text': text.strip(), 'bbox': bbox, 'y': bbox[0][1], 'conf': conf})

        if not words:
            return data, conf_scores
        
        # Group word text fragments into horizontal lines by matching Y coordinates
        words.sort(key=lambda x: x['y'])
        lines = []
        if words:
            current_line = [words[0]]
            for i in range(1, len(words)):
                if abs(words[i]['y'] - current_line[-1]['y']) < 20:
                    current_line.append(words[i])
                else:
                    current_line.sort(key=lambda x: x['bbox'][0][0])
                    lines.append(current_line)
                    current_line = [words[i]]
            lines.append(current_line)

        text_lines = [" ".join([w['text'] for w in line]) for line in lines]
        full_text = "\n".join(text_lines)

        # Helper to compute average confidence of a line scaled to 0-100
        def get_line_conf(l):
            confs = [w['conf'] for w in l]
            return (sum(confs) / len(confs)) * 100.0 if confs else 100.0

        # 1. Card Name Extraction (first text line that is not a metadata label or set info line)
        name_line_idx = -1
        currency_pattern = re.compile(r'^[\$S5zZ7]?\s*(?:9)?\d+[\.,]\d{2}$')
        exclude_kws = ["variant", "condition", "quantity", "quantlty", "conditlon", "price paid", "adding to:", "total collection"]

        # Define these patterns here so they can be shared by the name parser AND set parser below.
        # EasyOCR commonly misreads '\u2022' as '.', ",'" etc.
        BULLET_RE = re.compile(r"\s*[\u2022\u00b7]\s*")
        # Matches a set info line: starts with a known card type word, ends with a set number.
        # EasyOCR garbles "Pokemon" as "Pokcion", "Pokenon", etc. \u2014 match any "pok..." word.
        SET_LINE_RE = re.compile(
            r'(?:pok\w*|magic|yu-?gi|lorcana|flesh|one\s*piece)'  # garble-tolerant card type
            r'.+?'
            r'(\d+(?:/\d+)?)\s*$',  # ends with a set number
            re.IGNORECASE
        )
        for idx, line_str in enumerate(text_lines):
            line_lower = line_str.lower()
            # Skip known metadata keywords
            if any(k in line_lower for k in exclude_kws):
                continue
            # Skip currency amounts
            if currency_pattern.match(line_str.strip()):
                continue
            # Skip set info lines (e.g. "Pokemon Sun Moon Promo SM169") — these always
            # start with a known card type word and end with a set number pattern
            if SET_LINE_RE.search(line_str):
                continue
            if len(line_str) > 3:
                data["Card Name"] = line_str
                name_line_idx = idx
                break

        if name_line_idx != -1:
            # Sanitize common OCR typos in card names
            name = data["Card Name"]
            name = name.replace("'$", "'s")
            data["Card Name"] = name
            
            conf_scores["name"] = get_line_conf(lines[name_line_idx])

        # DEBUG: Print all raw OCR text lines so we can trace set detection
        print(f"[OCR] Raw text lines ({len(text_lines)}):")
        for i, tl in enumerate(text_lines):
            print(f"  [{i}] {repr(tl)}")

        # 3. Set Info Extraction
        # Format is always: "CardType \u2022 Set Name \u2022 Set Number"
        # Set Name can be multi-word and may contain numbers/colons (e.g. "SV: 151")
        # We split on bullet chars only and take: [0]=type, [1:-1]=set name parts, [-1]=set number
        # 
        # BULLET_RE and SET_LINE_RE are defined above (before the name parser) so they're available here too.

        set_line_idx = -1
        for idx, line_str in enumerate(text_lines):
            if idx == name_line_idx:
                continue
            # Primary: actual bullet character present
            if BULLET_RE.search(line_str):
                set_line_idx = idx
                print(f"[OCR] Found bullet set line at [{idx}]: {repr(line_str)}")
                break
            # Fallback: line starts with a known card type and ends with a number
            if SET_LINE_RE.search(line_str):
                set_line_idx = idx
                print(f"[OCR] Found keyword set line at [{idx}]: {repr(line_str)}")
                break

        if set_line_idx != -1:
            line_str = text_lines[set_line_idx]
            conf_scores["set_name"] = get_line_conf(lines[set_line_idx])
            parts = [p.strip() for p in BULLET_RE.split(line_str) if p.strip()]
            print(f"[OCR] Set line parts after bullet split: {parts}")
            # parts = ["Pokemon", "Shining Legends", "78"]  or  ["Pokemon", "SV: 151", "123/198"]
            if len(parts) >= 3:
                data["Card Type"] = parts[0].title()
                data["Set Name"] = " ".join(parts[1:-1])  # everything between first and last bullet
                data["Set Number"] = parts[-1]
            elif len(parts) == 2:
                # Missing card type: ["Set Name", "Set Number"]
                data["Set Name"] = parts[0]
                data["Set Number"] = parts[1]
            elif len(parts) == 1:
                # Only one part — try to parse "Pokemon Ascended Heroes 290/217" without bullets
                # by matching: known-type, then set name, then trailing number
                m_full = re.match(
                    r'^(pokemon|magic|yu-?gi|lorcana|flesh\s*and\s*blood|one\s*piece)\s+'
                    r'(.+?)\s+'
                    r'(\d+(?:/\d+)?)\s*$',
                    parts[0], re.IGNORECASE
                )
                if m_full:
                    data["Card Type"] = m_full.group(1).title()
                    data["Set Name"] = m_full.group(2).strip()
                    data["Set Number"] = m_full.group(3)
                    print(f"[OCR] Parsed single-part set line: type={data['Card Type']} set={data['Set Name']} num={data['Set Number']}")
                else:
                    # Last resort: extract trailing number as set number
                    m = re.search(r'(\d+(?:/\d+)?)\s*$', parts[0])
                    if m:
                        data["Set Number"] = m.group(1)
                        data["Set Name"] = parts[0][:m.start()].strip()
                    else:
                        data["Set Name"] = parts[0]
        else:
            print(f"[OCR] No set line found via bullet or keyword. Trying number fallback.")
            # Fallback: search for a set number pattern (e.g. "78", "290/217") in full text
            set_number_match = re.search(r'\b(\d{1,4}/\d{1,4}|\d{1,4})\b', full_text)
            if set_number_match:
                data["Set Number"] = set_number_match.group(1)
                print(f"[OCR] Fallback set number: {data['Set Number']}")


        # Filter out layout junk noise
        junk = [
            "review your matches", "total:", "matched scans", "add to portfolio", 
            "3 matched", "set price paid", "price paid", "variant", "condition", 
            "conditlon", "quantity", "quantlty", "type none", "ungraded"
        ]
        name_lower = data["Card Name"].lower()
        if any(kw in name_lower for kw in junk) or len(data["Card Name"]) < 2 or re.search(r'\d+:\d+', data["Card Name"]):
            data["Card Name"] = "Unknown"

        if data["Card Name"] == "Unknown":
            return data, conf_scores

        # 4. Zonal Metadata Keywords (Fuzzy match lines for Variant, Condition, Quantity)
        for line in lines:
            for kw in KEYWORDS:
                best_match = process.extractOne(kw, [w['text'] for w in line], scorer=fuzz.WRatio)
                if best_match and best_match[1] > 70:
                    kw_index = -1
                    for idx, w in enumerate(line):
                        if w['text'] == best_match[0]:
                            kw_index = idx
                            break
                    if kw_index != -1 and kw_index < len(line) - 1:
                        val = " ".join([w['text'] for w in line[kw_index+1:]])
                        if kw == "Quantity":
                            q_m = re.search(r'\d+', val)
                            if q_m:
                                data["Quantity"] = int(q_m.group())
                        elif kw == "Type":
                            if "none" in val.lower() or "ungraded" in val.lower():
                                data["Type"] = "None (Ungraded)"
                            elif val.strip().startswith("N") and len(val.strip()) < 5:
                                # OCR hallucination fix: 'Nol', 'Nor', 'No' -> 'None (Ungraded)'
                                data["Type"] = "None (Ungraded)"
                            else:
                                data["Type"] = val
                        else:
                            data[kw] = val
                            
        # 5. Standardize Condition using fuzzy matching
        raw_cond = data.get("Condition", "Near Mint")
        if raw_cond != "Near Mint":
            standard_conditions = ["Near Mint", "Lightly Played", "Moderately Played", "Heavily Played", "Damaged"]
            best_cond = process.extractOne(raw_cond, standard_conditions, scorer=fuzz.WRatio)
            if best_cond and best_cond[1] > 60:
                data["Condition"] = best_cond[0]
            else:
                lower_cond = raw_cond.lower()
                if 'mint' in lower_cond:
                    data["Condition"] = "Near Mint"
                elif 'light' in lower_cond or 'lp' in lower_cond:
                    data["Condition"] = "Lightly Played"
                elif 'mod' in lower_cond or 'mp' in lower_cond:
                    data["Condition"] = "Moderately Played"
                elif 'heav' in lower_cond or 'hp' in lower_cond:
                    data["Condition"] = "Heavily Played"
                elif 'dam' in lower_cond:
                    data["Condition"] = "Damaged"
                else:
                    data["Condition"] = "Near Mint"
                    
        # 6. Apply difflib fuzzy dictionary matcher for categorical fields
        for key in ["Variant", "Condition", "Type", "Card Type"]:
            if key in data and data[key] not in ["Unknown", "Standard", "Near Mint"]:
                extracted = data[key]
                matches = difflib.get_close_matches(extracted, KNOWN_TERMS, n=1, cutoff=0.6)
                if matches:
                    data[key] = matches[0]
                    
        return data, conf_scores

    def sanitize_set_name(self, set_name: str) -> str:
        """
        Applies cleanup on extracted set_name to handle common OCR typos of 'Pokémon'.
        """
        if not set_name:
            return set_name
        set_name_lower = set_name.lower()
        if 'pok' in set_name_lower:
            return 'pokemon'
        return set_name

    def parse_row_data(self, row_cv_img: np.ndarray) -> Optional[Dict[str, Any]]:
        """
        Orchestrates structural processing, EasyOCR read execution, and schema parsing.
        """
        try:
            # Step A: Mask out thumbnail card artwork to prevent OCR confusion
            masked_roi, art_bbox = self.detect_card_art_and_mask(row_cv_img)
            
            # Step B: Upscale, enhance contrast, and sharpen image
            processed_roi = self.preprocess_for_ocr(masked_roi)
            
            # Step C: Run EasyOCR reading
            results = self.reader.readtext(processed_roi, detail=1)
            
            # Step D: Map text segments to schema keys
            parsed_data, conf_scores = self.parse_results(results)
            
            # Apply set name sanitization and fuzzy matching
            if "Set Name" in parsed_data:
                parsed_data["Set Name"] = self.fuzzy_correct_set_name(parsed_data["Set Name"])
            
            # Step D.2: Spatial Price Extraction (Center Anchor)
            price_val, price_conf = self.extract_price_spatial(results, processed_roi.shape[1], processed_roi.shape[0])
            if price_val > 0.0:
                parsed_data["Price"] = price_val
                conf_scores["market_price"] = price_conf
            
            # Step E: Validation - only reject if name is truly unknown
            final_name = parsed_data.get("Card Name", "Unknown Card").strip()
            final_price = parsed_data.get("Price", 0.0)
            
            if not final_name or final_name == "Unknown" or final_name == "Unknown Card":
                return None
            
            # Allow the row even if OCR fails to find a price; API can backfill it later.
            
            # Step F: Construct final output dictionary matching staging layout expectation
            return {
                "name": final_name,
                "set_name": parsed_data.get("Set Name", "Unknown Set"),
                "sequence_number": parsed_data.get("Set Number", "000"),
                "market_price": final_price,
                "variant": parsed_data.get("Variant", "Standard"),
                "card_type": parsed_data.get("Type", "None (Ungraded)"),
                "condition": parsed_data.get("Condition", "Near Mint"),
                "quantity": parsed_data.get("Quantity", 1),
                "confidence_scores": conf_scores,
                "art_bbox": art_bbox
            }
        except Exception as e:
            print(f"[!] EasyOCR row parsing failed: {e}")
            return None


class RowSegmenter:
    """
    Segmenter responsible for finding bounding boxes of card rows in the capture image.
    Uses horizontal projection analysis to find row separator lines betwe    """
    @staticmethod
    def detect_card_boxes(image: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """
        Identifies card row bounding boxes by detecting the dark horizontal separator
        lines between card rows in dark-background list UIs (e.g. TCGPlayer).

        Strategy:
          - Find rows where mean brightness is near-zero (pure black = separator/background)
          - Merge nearby dark bands (so the header area with multiple small gaps
            doesn't produce dozens of false cut points)
          - Card ROIs are the regions between these merged dark separator zones
        """
        DARK_THRESHOLD = 5.0   # mean brightness below this = separator row
        MERGE_GAP_PX   = 20    # dark bands closer than this px are merged into one zone

        h_img, w_img = image.shape[:2]
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Smooth mean brightness per row (3-row window to suppress single-pixel noise)
        mean_proj = np.mean(gray, axis=1)
        kernel = np.ones(3) / 3
        smooth = np.convolve(mean_proj, kernel, mode='same')

        # ── Step 1: collect raw dark bands ───────────────────────────────────
        raw_dark = []
        in_dark = False
        dark_start = 0
        for y in range(h_img):
            if smooth[y] < DARK_THRESHOLD and not in_dark:
                dark_start = y
                in_dark = True
            elif smooth[y] >= DARK_THRESHOLD and in_dark:
                raw_dark.append((dark_start, y))
                in_dark = False
        if in_dark:
            raw_dark.append((dark_start, h_img))

        # ── Step 2: merge adjacent dark bands ────────────────────────────────
        merged = []
        for s, e in raw_dark:
            if merged and s - merged[-1][1] <= MERGE_GAP_PX:
                merged[-1] = (merged[-1][0], e)
            else:
                merged.append([s, e])

        sep_centers = [int((s + e) / 2) for s, e in merged]

        # ── Step 3: build ROIs between separator centers ──────────────────────
        boundaries = [0] + sep_centers + [h_img]
        all_rois = []
        for i in range(len(boundaries) - 1):
            y_start = boundaries[i]
            y_end   = boundaries[i + 1]
            row_h   = y_end - y_start

            # Normal card rows: 100–430px tall
            # Top-edge partial: allow >= 50px if it starts at y=0
            is_top_row = (y_start == 0)
            if (100 <= row_h <= 430) or (is_top_row and 50 <= row_h <= 430):
                all_rois.append((0, y_start, w_img, row_h))

        # ── Fallback: equal-height slicing ───────────────────────────────────
        if not all_rois:
            estimated_row_h = max(100, min(200, h_img // 4))
            for y_start in range(0, h_img - estimated_row_h // 2, estimated_row_h):
                row_h = min(estimated_row_h, h_img - y_start)
                if row_h >= 100:
                    all_rois.append((0, y_start, w_img, row_h))

        all_rois.sort(key=lambda b: b[1])
        return all_rois

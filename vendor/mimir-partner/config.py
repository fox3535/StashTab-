import os

ENVIRONMENT = "PRODUCTION"  # Set to "PRODUCTION" or "TEST"
USE_API_PRICE = False  # Toggle to prefer API pricing over OCR
DEBUG_MODE = False    # Toggle noisy print statements
AUTO_PRINT_LABELS = False # Toggle automatic label printing

# Shopify Integration Flags
SYNC_TO_SHOPIFY = True
REQUIRE_IMAGE_APPROVAL = True

# Currency Conversion
USD_TO_CAD_RATE = 1.43  # Adjust this to change the API USD -> CAD markup

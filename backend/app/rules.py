from dataclasses import dataclass

INCOME = "Income"
NOT_SPENDING = "Transfers & Card Payments"

SOFTWARE = "Software & Subscriptions"
TRAVEL = "Travel"
MEALS = "Meals"
OFFICE = "Office Supplies"
ADVERTISING = "Advertising"
TELECOM = "Phone & Internet"
FEES = "Interest & Bank Fees"

EXPENSE_CATEGORIES = (SOFTWARE, TRAVEL, MEALS, OFFICE, ADVERTISING, TELECOM, FEES)
ALL_CATEGORIES = EXPENSE_CATEGORIES + (INCOME, NOT_SPENDING)

# Below this confidence the brain asks instead of guessing.
REVIEW_THRESHOLD = 0.8


@dataclass(frozen=True)
class Rule:
    category: str
    patterns: tuple[str, ...]  # whole-word phrases matched against the normalized merchant
    confidence: float
    note: str = ""  # shown to the user when the rule is not confident enough
    money_in_only: bool = False


RULES: tuple[Rule, ...] = (
    Rule(SOFTWARE, (
        "ADOBE", "ZOOM", "GITHUB", "FIGMA", "SLACK", "NOTION", "DROPBOX", "CANVA",
        "OPENAI", "ATLASSIAN", "DIGITALOCEAN", "NAMECHEAP", "GODADDY", "AMAZON WEB SERVICES",
    ), 0.95),
    Rule(TRAVEL, (
        "UBER TRIP", "LYFT", "DELTA AIR", "UNITED AIRLINES", "AMERICAN AIRLINES",
        "SOUTHWEST AIRLINES", "MARRIOTT", "HILTON", "AIRBNB", "HERTZ", "AVIS", "AMTRAK",
    ), 0.95),
    Rule(OFFICE, ("STAPLES", "OFFICE DEPOT", "OFFICEMAX"), 0.95),
    Rule(ADVERTISING, ("GOOGLE ADS", "FACEBK ADS", "META ADS", "LINKEDIN ADS"), 0.95),
    Rule(TELECOM, ("VERIZON", "COMCAST", "T MOBILE", "AT&T"), 0.85),
    Rule(FEES, (
        "INTEREST CHARGE", "LATE FEE", "ANNUAL FEE", "FINANCE CHARGE", "FOREIGN TRANSACTION FEE",
    ), 0.95),
    # Deliberately below the threshold: these are always reviewed.
    Rule(MEALS, ("CAFE", "COFFEE", "RESTAURANT", "DINER", "PIZZA", "BISTRO", "GRILL", "BAKERY"), 0.7,
         "Meals are only deductible with a business purpose, so please confirm."),
    Rule(MEALS, ("UBER EATS", "DOORDASH", "GRUBHUB"), 0.6,
         "Food delivery could be personal or business."),
    Rule(OFFICE, ("AMAZON",), 0.5,
         "Amazon purchases could be business or personal."),
    # Not spending.
    Rule(NOT_SPENDING, (
        "TRANSFER TO SAVINGS", "TRANSFER FROM SAVINGS", "TRANSFER TO CHECKING",
        "TRANSFER FROM CHECKING", "INTERNAL TRANSFER", "PAYMENT THANK YOU", "AUTOPAY",
        "AUTOMATIC PAYMENT",
    ), 0.95),
    Rule(NOT_SPENDING, ("TRANSFER TO", "TRANSFER FROM"), 0.6,
         "A transfer to or from someone could be a contractor payment, a client payment "
         "or just moving your own money."),
    # Only counts when money comes in.
    Rule(INCOME, (
        "CLIENT PAYMENT", "INVOICE", "STRIPE PAYOUT", "STRIPE TRANSFER", "PAYONEER", "DIRECT DEPOSIT",
    ), 0.9, money_in_only=True),
)
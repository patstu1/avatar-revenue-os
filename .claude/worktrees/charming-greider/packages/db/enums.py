import enum


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


class DecisionMode(str, enum.Enum):
    FULL_AUTO = "full_auto"
    GUARDED_AUTO = "guarded_auto"
    MANUAL_OVERRIDE = "manual_override"


class ActorType(str, enum.Enum):
    SYSTEM = "system"
    HUMAN = "human"
    HYBRID = "hybrid"


class Platform(str, enum.Enum):
    YOUTUBE = "youtube"
    TIKTOK = "tiktok"
    INSTAGRAM = "instagram"
    TWITTER = "twitter"
    X = "x"
    REDDIT = "reddit"
    FACEBOOK = "facebook"
    LINKEDIN = "linkedin"
    PINTEREST = "pinterest"
    SNAPCHAT = "snapchat"
    THREADS = "threads"
    RUMBLE = "rumble"
    TWITCH = "twitch"
    KICK = "kick"
    WHATSAPP = "whatsapp"
    QUORA = "quora"
    CLAPPER = "clapper"
    LEMON8 = "lemon8"
    BEREAL = "bereal"
    BLUESKY = "bluesky"
    MASTODON = "mastodon"
    WECHAT = "wechat"
    SPOTIFY = "spotify"
    APPLE_PODCASTS = "apple_podcasts"
    EMAIL_NEWSLETTER = "email_newsletter"
    BLOG = "blog"
    SEO_AUTHORITY = "seo_authority"
    TELEGRAM = "telegram"
    DISCORD = "discord"
    MEDIUM = "medium"
    SUBSTACK = "substack"


class AccountType(str, enum.Enum):
    ORGANIC = "organic"
    PAID = "paid"
    HYBRID = "hybrid"


class ContentType(str, enum.Enum):
    SHORT_VIDEO = "short_video"
    LONG_VIDEO = "long_video"
    STATIC_IMAGE = "static_image"
    CAROUSEL = "carousel"
    TEXT_POST = "text_post"
    STORY = "story"
    LIVE_STREAM = "live_stream"


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class ApprovalStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVISION_REQUESTED = "revision_requested"


class SignalStrength(str, enum.Enum):
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    INSUFFICIENT = "insufficient"


class ConfidenceLevel(str, enum.Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INSUFFICIENT = "insufficient"


class RecommendedAction(str, enum.Enum):
    SCALE = "scale"
    MAINTAIN = "maintain"
    REDUCE = "reduce"
    SUPPRESS = "suppress"
    MONITOR = "monitor"
    EXPERIMENT = "experiment"


class BottleneckType(str, enum.Enum):
    WEAK_OPPORTUNITY_SELECTION = "weak_opportunity_selection"
    WEAK_HOOK_RETENTION = "weak_hook_retention"
    WEAK_CTR = "weak_ctr"
    WEAK_OFFER_FIT = "weak_offer_fit"
    WEAK_LANDING_PAGE = "weak_landing_page"
    WEAK_CONVERSION = "weak_conversion"
    WEAK_AOV = "weak_aov"
    WEAK_LTV = "weak_ltv"
    WEAK_SCALE_CAPACITY = "weak_scale_capacity"
    AUDIENCE_FATIGUE = "audience_fatigue"
    CONTENT_SIMILARITY = "content_similarity"
    PLATFORM_MISMATCH = "platform_mismatch"
    TRUST_DEFICIT = "trust_deficit"
    MONETIZATION_MISMATCH = "monetization_mismatch"


class ProviderType(str, enum.Enum):
    AVATAR = "avatar"
    VOICE = "voice"
    LLM = "llm"
    IMAGE = "image"
    VIDEO = "video"
    ANALYTICS = "analytics"


class MonetizationMethod(str, enum.Enum):
    AFFILIATE = "affiliate"
    ADSENSE = "adsense"
    SPONSOR = "sponsor"
    PRODUCT = "product"
    COURSE = "course"
    MEMBERSHIP = "membership"
    CONSULTING = "consulting"
    LEAD_GEN = "lead_gen"


class DecisionType(str, enum.Enum):
    OPPORTUNITY = "opportunity"
    MONETIZATION = "monetization"
    PUBLISH = "publish"
    SUPPRESSION = "suppression"
    SCALE = "scale"
    ALLOCATION = "allocation"
    EXPANSION = "expansion"


class QAStatus(str, enum.Enum):
    PASS = "pass"
    FAIL = "fail"
    REVIEW = "review"
    OVERRIDE = "override"


class SuppressionReason(str, enum.Enum):
    LOW_PROFIT = "low_profit"
    COMPLIANCE_RISK = "compliance_risk"
    SATURATION = "saturation"
    FATIGUE = "fatigue"
    ORIGINALITY_LOW = "originality_low"
    CANNIBALIZATION = "cannibalization"
    PLATFORM_RISK = "platform_risk"
    MANUAL = "manual"


class HealthStatus(str, enum.Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    SUSPENDED = "suspended"


class SignalClassification(str, enum.Enum):
    SCALE = "scale"
    MAINTAIN = "maintain"
    MONITOR = "monitor"
    INSUFFICIENT_SIGNAL = "insufficient_signal"
    BACKLOG = "backlog"
    SUPPRESS = "suppress"


class ExperimentStatus(str, enum.Enum):
    DRAFT = "draft"
    RUNNING = "running"
    COMPLETED = "completed"
    STOPPED = "stopped"
    INCONCLUSIVE = "inconclusive"


# ---------------------------------------------------------------------------
# Cinema Studio enums
# ---------------------------------------------------------------------------

class CameraShot(str, enum.Enum):
    EXTREME_CLOSE_UP = "extreme_close_up"
    CLOSE_UP = "close_up"
    MEDIUM_CLOSE_UP = "medium_close_up"
    MEDIUM = "medium"
    MEDIUM_WIDE = "medium_wide"
    WIDE = "wide"
    EXTREME_WIDE = "extreme_wide"
    OVER_SHOULDER = "over_shoulder"
    POV = "pov"
    AERIAL = "aerial"
    LOW_ANGLE = "low_angle"
    HIGH_ANGLE = "high_angle"
    DUTCH_ANGLE = "dutch_angle"


class CameraMovement(str, enum.Enum):
    STATIC = "static"
    PAN = "pan"
    TILT = "tilt"
    DOLLY = "dolly"
    TRACKING = "tracking"
    CRANE = "crane"
    HANDHELD = "handheld"
    STEADICAM = "steadicam"
    ZOOM = "zoom"
    WHIP_PAN = "whip_pan"
    ORBIT = "orbit"


class SceneLighting(str, enum.Enum):
    NATURAL = "natural"
    GOLDEN_HOUR = "golden_hour"
    BLUE_HOUR = "blue_hour"
    STUDIO = "studio"
    DRAMATIC = "dramatic"
    NEON = "neon"
    LOW_KEY = "low_key"
    HIGH_KEY = "high_key"
    SILHOUETTE = "silhouette"
    PRACTICAL = "practical"
    MOONLIGHT = "moonlight"


class SceneMood(str, enum.Enum):
    CINEMATIC = "cinematic"
    ENERGETIC = "energetic"
    CALM = "calm"
    MYSTERIOUS = "mysterious"
    DARK = "dark"
    ROMANTIC = "romantic"
    EPIC = "epic"
    NOSTALGIC = "nostalgic"
    PLAYFUL = "playful"
    TENSE = "tense"
    DREAMY = "dreamy"
    DOCUMENTARY = "documentary"


class SceneStatus(str, enum.Enum):
    DRAFT = "draft"
    READY = "ready"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class StudioGenerationStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Canonical Lifecycle Enums — shared across the operating system
# These define the universal state vocabulary for major object classes.
# ---------------------------------------------------------------------------


class ContentLifecycle(str, enum.Enum):
    """Unified content item lifecycle — from idea to tracked performance."""
    DRAFT = "draft"
    BRIEF_READY = "brief_ready"
    GENERATING = "generating"
    GENERATED = "generated"
    QA_REVIEW = "qa_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    TRACKING = "tracking"
    UNDERPERFORMING = "underperforming"
    ARCHIVED = "archived"
    FAILED = "failed"


class AccountLifecycle(str, enum.Enum):
    """Creator account lifecycle — from creation to maturity."""
    ONBOARDING = "onboarding"
    ACTIVE = "active"
    WARMING = "warming"
    READY = "ready"
    PRODUCING = "producing"
    SCALING = "scaling"
    MATURE = "mature"
    DEGRADED = "degraded"
    RECOVERING = "recovering"
    SUSPENDED = "suspended"


class OfferLifecycleStatus(str, enum.Enum):
    """Offer lifecycle — from draft through performance-based transitions."""
    DRAFT = "draft"
    TESTING = "testing"
    ACTIVE = "active"
    PROMOTED = "promoted"
    DECLINING = "declining"
    PAUSED = "paused"
    RETIRED = "retired"


class BrandLifecycle(str, enum.Enum):
    """Brand lifecycle — from setup to full operation."""
    SETUP = "setup"
    ONBOARDING = "onboarding"
    ACTIVE = "active"
    PRODUCING = "producing"
    SCALING = "scaling"
    MATURE = "mature"
    PAUSED = "paused"


class EventDomain(str, enum.Enum):
    """Top-level system event domains mapping to OS layers."""
    CONTENT = "content"
    PUBLISHING = "publishing"
    MONETIZATION = "monetization"
    INTELLIGENCE = "intelligence"
    ORCHESTRATION = "orchestration"
    GOVERNANCE = "governance"
    RECOVERY = "recovery"
    ACCOUNT = "account"
    BRAND = "brand"
    SYSTEM = "system"


class EventSeverity(str, enum.Enum):
    """Event severity for control layer prioritization."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ActionPriority(str, enum.Enum):
    """Operator action priority."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ActionCategory(str, enum.Enum):
    """Categories of operator actions for the control layer."""
    BLOCKER = "blocker"
    APPROVAL = "approval"
    OPPORTUNITY = "opportunity"
    FAILURE = "failure"
    HEALTH = "health"
    MONETIZATION = "monetization"
    GOVERNANCE = "governance"


class ActionStatus(str, enum.Enum):
    """Status of an operator action."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DISMISSED = "dismissed"
    EXPIRED = "expired"


class PublishPolicyTier(str, enum.Enum):
    """Outcome tiers for the publish policy engine."""
    AUTO_PUBLISH = "auto_publish"
    SAMPLE_REVIEW = "sample_review"
    MANUAL_APPROVAL = "manual_approval"
    BLOCK = "block"

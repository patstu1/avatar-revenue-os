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
    FACEBOOK = "facebook"
    LINKEDIN = "linkedin"
    PINTEREST = "pinterest"
    SNAPCHAT = "snapchat"
    THREADS = "threads"


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
